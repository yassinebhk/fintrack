"""Pipeline: curated YouTube finance channels → new videos → transcript →
LLM summary → Telegram + DB cache for the web."""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
from loguru import logger

from app.llm import LLMMessage, get_llm_client
from app.services.creators.sources import CREATORS, NEWSLETTERS

YT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

# Persisted via JsonCache (survives redeploys).
_DB_KEY_SUMMARIES = "creators_summaries"   # list of last N summaries
_DB_KEY_SEEN = "creators_seen_ids"          # {channel_id: [video_ids]}
_DB_KEY_RESOLVED = "creators_resolved"      # {handle: channel_id}
_MAX_SUMMARIES = 30
_MAX_SEEN_PER_CHANNEL = 50
_MAX_TRANSCRIPT_CHARS = 18000  # truncate very long videos before sending to LLM


class CreatorsService:
    async def _load(self, key: str, default):
        try:
            from sqlalchemy import select

            from app.db import session_scope
            from app.models import JsonCache

            async with session_scope() as s:
                row = (await s.execute(select(JsonCache).where(JsonCache.key == key))).scalar_one_or_none()
            return row.payload if row and row.payload else default
        except Exception as exc:
            logger.debug("creators: load {} failed: {}", key, exc)
            return default

    async def _save(self, key: str, payload) -> None:
        try:
            from app.db import session_scope, upsert_insert
            from app.models import JsonCache

            stmt = upsert_insert()(JsonCache).values(
                key=key, payload=payload, updated_at=datetime.now(timezone.utc)
            ).on_conflict_do_update(
                index_elements=["key"],
                set_={"payload": payload, "updated_at": datetime.now(timezone.utc)},
            )
            async with session_scope() as s:
                await s.execute(stmt)
        except Exception as exc:
            logger.warning("creators: save {} failed: {}", key, exc)

    # ---------- handle → channel_id ----------
    async def _resolve_channel_id(self, creator: dict, resolved_cache: dict) -> str | None:
        """Prefer the pre-verified channel_id from sources; otherwise resolve the
        handle via yt-dlp (reliable across YouTube's HTML changes). Cached in DB."""
        if creator.get("channel_id"):
            return creator["channel_id"]
        handle = creator.get("handle", "")
        cached = resolved_cache.get(handle)
        if cached:
            return cached
        try:
            def _resolve() -> str | None:
                import yt_dlp
                opts = {"quiet": True, "skip_download": True, "extract_flat": True,
                         "playlist_items": "1", "no_warnings": True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/{handle}", download=False)
                    return info.get("channel_id") or info.get("id")
            cid = await asyncio.get_event_loop().run_in_executor(None, _resolve)
            if cid:
                resolved_cache[handle] = cid
                return cid
        except Exception as exc:
            logger.warning("creators: resolve {} failed: {}", handle, exc)
        return None

    # ---------- RSS → recent video entries ----------
    async def _fetch_channel_rss(self, channel_id: str) -> list[dict]:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get(url, headers=YT_HEADERS)
                if r.status_code != 200:
                    return []
                root = ET.fromstring(r.text)
                ns = {"a": "http://www.w3.org/2005/Atom",
                      "yt": "http://www.youtube.com/xml/schemas/2015",
                      "media": "http://search.yahoo.com/mrss/"}
                entries = []
                for e in root.findall("a:entry", ns):
                    vid = e.findtext("yt:videoId", default="", namespaces=ns)
                    title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
                    link = ""
                    link_el = e.find("a:link", ns)
                    if link_el is not None:
                        link = link_el.attrib.get("href", "")
                    published = e.findtext("a:published", default="", namespaces=ns)
                    # The RSS already carries the video's description (no need for yt-dlp
                    # to fetch it, which the cloud IP often gets rate-limited on).
                    desc = ""
                    group = e.find("media:group", ns)
                    if group is not None:
                        desc = (group.findtext("media:description", default="", namespaces=ns) or "").strip()
                    if vid:
                        entries.append({"video_id": vid, "title": title, "url": link,
                                          "published": published, "description": desc})
                return entries
        except Exception as exc:
            logger.warning("creators: rss {} failed: {}", channel_id, exc)
            return []

    @staticmethod
    def _clean_vtt(vtt: str) -> str:
        """Strip VTT tags, drop cue/timestamp lines, dedupe the line repeats that
        auto-captions produce (each cue overlaps with the next on screen)."""
        text = re.sub(r"<[^>]+>", "", vtt)
        out, recent = [], []
        for raw in text.splitlines():
            l = raw.strip()
            if not l or "-->" in l or l.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
                continue
            if l in recent:
                continue
            recent.append(l)
            if len(recent) > 6:
                recent.pop(0)
            out.append(l)
        return " ".join(out)

    def _get_video_context(self, video_id: str, langs: list[str], rss_desc: str = "", rss_title: str = "") -> dict | None:
        """Try transcript first; if YouTube blocks the captions endpoint (common from
        cloud IPs), fall back to the video's description + title — much shorter but
        still summarizable. Returns {source, text, title} or None."""
        try:
            import yt_dlp
        except Exception as exc:
            logger.debug("yt-dlp missing: {}", exc)
            return None

        info = {}
        try:
            opts = {"quiet": True, "skip_download": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False) or {}
        except Exception as exc:
            # Don't bail — we still have RSS description as fallback.
            logger.debug("creators: yt-dlp info {} failed: {}", video_id, exc)

        title = info.get("title") or rss_title

        # 1) Try transcript via VTT subtitles.
        wanted = list(langs) + [f"{l}-419" for l in langs] + ["es", "es-419", "en", "en-US", "en-GB"]
        wanted = list(dict.fromkeys(wanted))
        for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
            for lang in wanted:
                tracks = source.get(lang)
                if not tracks:
                    continue
                url = next((t["url"] for t in tracks if t.get("ext") == "vtt"), tracks[0].get("url"))
                if not url:
                    continue
                try:
                    with httpx.Client(timeout=20.0) as c:
                        r = c.get(url)
                    if r.status_code != 200 or not r.text:
                        continue
                    text = self._clean_vtt(r.text)
                    if text and len(text) > 200:
                        return {"source": "transcript", "text": text[:_MAX_TRANSCRIPT_CHARS], "title": title}
                except Exception:
                    continue

        # 2) Fallback to the video's own description. Prefer yt-dlp's (richer); if
        #    that failed too (cloud-IP rate limits), use the description embedded in
        #    YouTube's RSS feed (always reachable from anywhere).
        desc = ((info or {}).get("description") or "").strip()
        tags = (info or {}).get("tags") or []
        if not desc or len(desc) < 80:
            desc = (rss_desc or "").strip()
        if desc and len(desc) > 80:
            text = desc
            if tags:
                text += "\n\nTags: " + ", ".join(tags[:15])
            return {"source": "description", "text": text[:_MAX_TRANSCRIPT_CHARS], "title": title or rss_title}
        return None

    # ---------- LLM summary ----------
    async def _summarize(self, creator: dict, video_title: str, context_text: str,
                          source: str = "transcript") -> dict | None:
        source_label = "transcript completo" if source == "transcript" else "DESCRIPCIÓN del vídeo (no el transcript)"
        system = (
            "Eres analista financiero. Resumes el contenido de un vídeo de un divulgador con "
            "neutralidad y rigor para que el lector pueda usarlo como insumo de mercado, NO como recomendación.\n"
            "REGLAS ANTI-ALUCINACIÓN:\n"
            "- Usa SOLO lo que aparezca en el texto que te paso. No inventes cifras ni hechos.\n"
            f"- Te paso un {source_label}; si es solo la descripción, di al final 'Resumen basado en la descripción del vídeo, no en el transcript completo'.\n"
            "- Tono: profesional, español, conciso.\n"
            "- Marca claramente que es OPINIÓN del autor, no consejo de inversión.\n"
            "- Si hay claims fuertes (predicciones, niveles concretos), reporta como 'según el autor…'."
        )
        user = (
            f"Divulgador: {creator['name']} ({creator['lang']}) · enfoque: {creator['focus']}\n"
            f"Título del vídeo: {video_title}\n"
            f"Fuente: {source_label}\n\n"
            f"Contenido:\n{context_text}\n\n"
            "Devuelve estrictamente este formato Markdown:\n"
            "## Tesis principal\n"
            "(1-2 frases)\n\n"
            "## Puntos clave\n"
            "- (3-5 bullets, en español, con la palabra ‘según el autor’ cuando proceda)\n\n"
            "## Activos / sectores mencionados\n"
            "- (lista corta; vacío si no menciona)\n\n"
            "## Tono general del autor\n"
            "(alcista / bajista / neutral, y por qué en una frase)\n\n"
            "## Aviso\n"
            "Es opinión del divulgador, no recomendación de inversión."
        )
        try:
            client = get_llm_client()
            resp = await client.generate(
                [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
                max_tokens=900, temperature=0.3,
            )
            md = (resp.text or "").strip()
            if not md:
                return None
            return {"summary_markdown": md, "model": resp.model}
        except Exception as exc:
            logger.warning("creators: LLM summary failed: {}", exc)
            self._last_llm_error = str(exc)[:300]  # surfaced in refresh diagnostics
            return None

    # ---------- Telegram delivery ----------
    async def _notify(self, creator: dict, entry: dict, summary_md: str) -> None:
        try:
            from app.services.notifications.telegram import (
                TelegramNotifier,
                html_escape,
            )

            n = TelegramNotifier()
            # Compact HTML for Telegram (no Markdown headings — convert briefly)
            body = summary_md
            body = re.sub(r"^## (.+)$", r"<b>\1</b>", body, flags=re.MULTILINE)
            # Telegram supports a small HTML subset; strip anything risky.
            body = re.sub(r"</?(?!b|i|u|s|a|code|pre)[a-z]+[^>]*>", "", body)
            head = (
                f"🎙️ <b>{html_escape(creator['name'])}</b> ({creator['lang'].upper()})\n"
                f"<i>{html_escape(creator['focus'])}</i>\n"
                f"📺 <a href=\"{entry['url']}\">{html_escape(entry['title'])}</a>\n\n"
            )
            msg = (head + body)[:3800]
            await n.send_html(msg)
        except Exception as exc:
            logger.warning("creators: telegram delivery failed: {}", exc)

    # ---------- newsletters (Substack / Wordpress / Blogger RSS) ----------
    async def _fetch_newsletter_entries(self, feed_url: str) -> list[dict]:
        """Parse a finance newsletter RSS/Atom feed. Returns entries with id, title,
        url, published, and (where present) the embedded content/excerpt."""
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
                r = await c.get(feed_url, headers=YT_HEADERS)
            if r.status_code != 200:
                return []
            root = ET.fromstring(r.text)
        except Exception as exc:
            logger.warning("creators: newsletter feed {} failed: {}", feed_url, exc)
            return []

        out: list[dict] = []
        # Both RSS 2.0 (item) and Atom (entry).
        nodes = root.findall(".//{*}item") + root.findall(".//{*}entry")
        for n in nodes:
            title = (n.findtext("{*}title") or "").strip()
            # link: <link>URL</link> in RSS; <link href="URL"/> in Atom.
            link = (n.findtext("{*}link") or "").strip()
            if not link:
                link_el = n.find("{*}link")
                if link_el is not None:
                    link = link_el.attrib.get("href", "")
            # id / guid (avoid empty)
            entry_id = (n.findtext("{*}guid") or n.findtext("{*}id") or link).strip()
            published = (n.findtext("{*}pubDate") or n.findtext("{*}published") or
                         n.findtext("{*}updated") or "").strip()
            # Body: try (in order) content:encoded, content, description, summary.
            body = ""
            for tag in ("{http://purl.org/rss/1.0/modules/content/}encoded",
                        "{*}content", "{*}description", "{*}summary"):
                t = n.find(tag)
                if t is not None and (t.text or ""):
                    body = t.text or ""
                    break
            if title and entry_id:
                out.append({"id": entry_id, "title": title, "url": link,
                             "published": published, "html": body})
        return out

    def _html_to_text(self, html: str) -> str:
        """Strip tags + collapse whitespace. Conservative — keeps it lightweight."""
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"</p>", "\n\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"&#39;", "'", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    async def _fetch_article(self, url: str) -> str | None:
        """If the RSS excerpt is too short, fetch the article page and extract text."""
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as c:
                r = await c.get(url, headers=YT_HEADERS)
            if r.status_code != 200 or not r.text:
                return None
            return self._html_to_text(r.text)
        except Exception as exc:
            logger.debug("creators: article fetch {} failed: {}", url, exc)
            return None

    async def _process_newsletters(self, summaries: list[dict], seen_map: dict,
                                     processed: list[dict], skipped: list[dict],
                                     new_count: int, max_llm_calls: int,
                                     deliver: bool) -> int:
        for nl in NEWSLETTERS:
            if new_count >= max_llm_calls:
                break
            key = nl["feed"]
            try:
                entries = await self._fetch_newsletter_entries(key)
                if not entries:
                    skipped.append({"creator": nl["name"], "reason": "feed vacío o no parseable"})
                    continue
                seen = set(seen_map.get(key, []))
                fresh = [e for e in entries if e["id"] not in seen][:1]
                if not seen and fresh:
                    fresh = [entries[0]]
                    seen.update(e["id"] for e in entries[1:])
                    seen_map[key] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]

                for e in fresh:
                    if new_count >= max_llm_calls:
                        break
                    # Pull text: RSS body if rich, else fetch the article URL.
                    text = self._html_to_text(e.get("html", ""))
                    if len(text) < 1200 and e.get("url"):
                        full = await self._fetch_article(e["url"])
                        if full and len(full) > len(text):
                            text = full
                    if not text or len(text) < 400:
                        skipped.append({"creator": nl["name"], "video_id": e["id"][:80],
                                          "title": e["title"][:80],
                                          "reason": "artículo vacío o demasiado corto"})
                        seen.add(e["id"]); seen_map[key] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]
                        continue
                    text = text[:_MAX_TRANSCRIPT_CHARS]
                    fake_creator = {"name": nl["name"], "lang": nl["lang"], "focus": nl["focus"]}
                    summary = await self._summarize(fake_creator, e["title"], text, source="transcript")
                    if not summary:
                        skipped.append({"creator": nl["name"], "title": e["title"][:80],
                                          "reason": "fallo del LLM: " + (getattr(self, "_last_llm_error", "") or "?")})
                        continue
                    item = {
                        "creator": nl["name"], "handle": "(newsletter)", "lang": nl["lang"],
                        "focus": nl["focus"], "kind": "newsletter",
                        "video_id": e["id"], "title": e["title"], "url": e["url"],
                        "published": e["published"],
                        "summary_markdown": summary["summary_markdown"],
                        "source": "article", "model": summary["model"],
                        "added_at": datetime.now(timezone.utc).isoformat(),
                    }
                    summaries.insert(0, item)
                    processed.append(item)
                    new_count += 1
                    seen.add(e["id"]); seen_map[key] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]
                    if deliver:
                        await self._notify_newsletter(nl, e, summary["summary_markdown"])
            except Exception as exc:
                logger.error("creators: newsletter {} failed: {}", key, exc)
                skipped.append({"creator": nl["name"], "reason": f"error: {str(exc)[:80]}"})
        return new_count

    async def _notify_newsletter(self, nl: dict, entry: dict, summary_md: str) -> None:
        try:
            from app.services.notifications.telegram import (
                TelegramNotifier,
                html_escape,
            )

            body = re.sub(r"^## (.+)$", r"<b>\1</b>", summary_md, flags=re.MULTILINE)
            body = re.sub(r"</?(?!b|i|u|s|a|code|pre)[a-z]+[^>]*>", "", body)
            head = (
                f"📰 <b>{html_escape(nl['name'])}</b> ({nl['lang'].upper()})\n"
                f"<i>{html_escape(nl['focus'])}</i>\n"
                f"🔗 <a href=\"{entry['url']}\">{html_escape(entry['title'])}</a>\n\n"
            )
            await TelegramNotifier().send_html((head + body)[:3800])
        except Exception as exc:
            logger.warning("creators: newsletter telegram delivery failed: {}", exc)

    # ---------- public entry point ----------
    async def check_and_process(self, *, max_new_per_channel: int = 1,
                                  max_llm_calls: int = 8, deliver: bool = True) -> dict:
        """Pull RSS for each curated channel; for each genuinely new video, fetch
        the transcript, summarize via LLM, deliver to Telegram, and append to the
        cached summaries shown in the UI. Idempotent — uses DB to remember seen IDs."""
        resolved: dict = await self._load(_DB_KEY_RESOLVED, {})
        seen_map: dict = await self._load(_DB_KEY_SEEN, {})
        summaries: list = await self._load(_DB_KEY_SUMMARIES, [])

        new_count = 0
        processed: list[dict] = []
        skipped: list[dict] = []  # diagnostic per video (transcript fail, llm fail, …)
        for creator in CREATORS:
            if new_count >= max_llm_calls:
                break
            try:
                cid = await self._resolve_channel_id(creator, resolved)
                if not cid:
                    logger.info("creators: cannot resolve {}", creator["handle"])
                    skipped.append({"creator": creator["name"], "reason": "channel_id no resuelto"})
                    continue
                entries = await self._fetch_channel_rss(cid)
                if not entries:
                    skipped.append({"creator": creator["name"], "reason": "RSS vacío"})
                    continue
                seen = set(seen_map.get(cid, []))
                fresh = [e for e in entries if e["video_id"] not in seen][:max_new_per_channel]
                # First run for this channel → don't backfill the whole feed, but only
                # the latest video. Mark the older entries seen immediately. The latest
                # gets marked only after we ATTEMPT it (so a transient transcript failure
                # doesn't lose it forever).
                if not seen and fresh:
                    fresh = [entries[0]]
                    seen.update(e["video_id"] for e in entries[1:])
                    seen_map[cid] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]

                for e in fresh:
                    if new_count >= max_llm_calls:
                        logger.info("creators: hit global cap of {} LLM calls; deferring rest", max_llm_calls)
                        break
                    langs = ["es"] if creator["lang"] == "es" else ["en"]
                    ctx = await asyncio.get_event_loop().run_in_executor(
                        None, self._get_video_context, e["video_id"], langs,
                        e.get("description", ""), e.get("title", ""),
                    )
                    if not ctx or not ctx.get("text") or len(ctx["text"]) < 80:
                        logger.info("creators: skipping {} (no context)", e["video_id"])
                        skipped.append({"creator": creator["name"], "video_id": e["video_id"],
                                          "title": e["title"][:80],
                                          "reason": "ni transcript ni descripción"})
                        seen.add(e["video_id"])  # don't keep retrying an empty video
                        seen_map[cid] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]
                        continue
                    summary = await self._summarize(creator, e["title"], ctx["text"], source=ctx["source"])
                    if not summary:
                        skipped.append({"creator": creator["name"], "video_id": e["video_id"],
                                          "title": e["title"][:80], "reason": "fallo del LLM: " + (getattr(self, "_last_llm_error", "") or "?")})
                        continue  # leave unseen so next cycle can retry
                    item = {
                        "creator": creator["name"],
                        "handle": creator["handle"],
                        "lang": creator["lang"],
                        "focus": creator["focus"],
                        "video_id": e["video_id"],
                        "title": e["title"],
                        "url": e["url"],
                        "published": e["published"],
                        "summary_markdown": summary["summary_markdown"],
                        "source": ctx["source"],
                        "model": summary["model"],
                        "added_at": datetime.now(timezone.utc).isoformat(),
                    }
                    summaries.insert(0, item)
                    processed.append(item)
                    new_count += 1
                    seen.add(e["video_id"])
                    seen_map[cid] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]
                    if deliver:
                        await self._notify(creator, e, summary["summary_markdown"])
            except Exception as exc:
                logger.error("creators: channel {} pipeline failed: {}", creator["handle"], exc)
                skipped.append({"creator": creator["name"], "reason": f"error pipeline: {str(exc)[:80]}"})

        # Now run the newsletter feeds (Substack / Wordpress / Blogger RSS).
        new_count = await self._process_newsletters(
            summaries, seen_map, processed, skipped, new_count, max_llm_calls, deliver,
        )

        summaries = summaries[:_MAX_SUMMARIES]
        await self._save(_DB_KEY_RESOLVED, resolved)
        await self._save(_DB_KEY_SEEN, seen_map)
        await self._save(_DB_KEY_SUMMARIES, summaries)
        logger.info("creators: processed {} new videos (skipped {})", new_count, len(skipped))
        return {
            "new_videos": new_count,
            "processed": processed,
            "skipped": skipped,
            "total_cached": len(summaries),
        }

    async def latest(self, limit: int = 20) -> list[dict]:
        return (await self._load(_DB_KEY_SUMMARIES, []))[:limit]

    # ---------- collaboration with GitHub Actions ----------
    # Render's IP can't fetch YouTube transcripts (rate-limited). A GH-Actions
    # workflow does it on its runner (not blocked) and POSTs the transcript here.
    async def list_pending_transcripts(self) -> list[dict]:
        """One pending video per curated YouTube channel (the latest unseen). The
        workflow uses this list to know which transcripts to fetch + post back."""
        seen_map = await self._load(_DB_KEY_SEEN, {})
        pending: list[dict] = []
        for creator in CREATORS:
            cid = creator.get("channel_id")
            if not cid:
                continue
            entries = await self._fetch_channel_rss(cid)
            if not entries:
                continue
            seen = set(seen_map.get(cid, []))
            fresh = [e for e in entries if e["video_id"] not in seen][:1]
            if not seen and entries:
                fresh = [entries[0]]  # first run for this channel → latest only
            for e in fresh:
                pending.append({
                    "creator_name": creator["name"], "lang": creator["lang"],
                    "focus": creator["focus"], "channel_id": cid,
                    "video_id": e["video_id"], "title": e["title"], "url": e["url"],
                })
        return pending

    async def ingest_transcript(self, *, channel_id: str, video_id: str, transcript: str,
                                  title: str = "", url: str = "", deliver: bool = True) -> dict:
        """Receive a transcript fetched by an external worker (GH Action), summarize
        it via the LLM, persist it and (optionally) deliver to Telegram."""
        creator = next((c for c in CREATORS if (c.get("channel_id") or "") == channel_id), None)
        if not creator:
            return {"status": "creator_not_found"}
        text = (transcript or "").strip()
        if len(text) < 400:
            return {"status": "transcript_too_short", "length": len(text)}
        text = text[:_MAX_TRANSCRIPT_CHARS]

        summaries = await self._load(_DB_KEY_SUMMARIES, [])
        if any(s.get("video_id") == video_id for s in summaries):
            return {"status": "already_summarized"}

        summary = await self._summarize(creator, title or video_id, text, source="transcript")
        if not summary:
            return {"status": "llm_failed"}

        item = {
            "creator": creator["name"], "handle": creator.get("handle", ""),
            "lang": creator["lang"], "focus": creator["focus"],
            "video_id": video_id, "title": title, "url": url,
            "summary_markdown": summary["summary_markdown"],
            "source": "transcript", "model": summary["model"],
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        summaries.insert(0, item)
        summaries = summaries[:_MAX_SUMMARIES]
        seen_map = await self._load(_DB_KEY_SEEN, {})
        seen = set(seen_map.get(channel_id, []))
        seen.add(video_id)
        seen_map[channel_id] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]
        await self._save(_DB_KEY_SUMMARIES, summaries)
        await self._save(_DB_KEY_SEEN, seen_map)

        if deliver:
            await self._notify(creator, {"title": title or video_id, "url": url}, summary["summary_markdown"])
        return {"status": "ok", "summary_chars": len(summary["summary_markdown"])}
