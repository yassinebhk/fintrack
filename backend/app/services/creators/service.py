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
from app.services.creators.sources import CREATORS

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
                      "yt": "http://www.youtube.com/xml/schemas/2015"}
                entries = []
                for e in root.findall("a:entry", ns):
                    vid = e.findtext("yt:videoId", default="", namespaces=ns)
                    title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
                    link = ""
                    link_el = e.find("a:link", ns)
                    if link_el is not None:
                        link = link_el.attrib.get("href", "")
                    published = e.findtext("a:published", default="", namespaces=ns)
                    if vid:
                        entries.append({"video_id": vid, "title": title, "url": link, "published": published})
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

    def _get_transcript(self, video_id: str, langs: list[str]) -> str | None:
        """Robust transcript extraction via yt-dlp (auto-captions fallback). Cleans
        VTT and dedupes consecutive line repeats. Returns None if no captions exist."""
        try:
            import yt_dlp
        except Exception as exc:
            logger.debug("yt-dlp missing: {}", exc)
            return None

        try:
            opts = {"quiet": True, "skip_download": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            wanted = list(langs) + [f"{l}-419" for l in langs] + ["es", "es-419", "en", "en-US", "en-GB"]
            wanted = list(dict.fromkeys(wanted))  # dedupe, preserve order
            # Prefer manual subs; fall back to auto-generated.
            for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
                for lang in wanted:
                    tracks = source.get(lang)
                    if not tracks:
                        continue
                    url = next((t["url"] for t in tracks if t.get("ext") == "vtt"), tracks[0].get("url"))
                    if not url:
                        continue
                    with httpx.Client(timeout=20.0) as c:
                        r = c.get(url)
                    if r.status_code != 200 or not r.text:
                        continue
                    text = self._clean_vtt(r.text)
                    if text and len(text) > 200:
                        return text[:_MAX_TRANSCRIPT_CHARS]
        except Exception as exc:
            logger.debug("creators: transcript {} unavailable: {}", video_id, exc)
        return None

    # ---------- LLM summary ----------
    async def _summarize(self, creator: dict, video_title: str, transcript: str) -> dict | None:
        system = (
            "Eres analista financiero. Resumes un vídeo de un divulgador con neutralidad "
            "y rigor para que el lector pueda usarlo como insumo de mercado, NO como recomendación.\n"
            "REGLAS:\n"
            "- Usa SOLO lo que esté en el transcript. No inventes cifras ni hechos.\n"
            "- Tono: profesional, español, conciso.\n"
            "- Marca claramente que es OPINIÓN del autor, no consejo de inversión.\n"
            "- Si hay claims fuertes (predicciones, niveles concretos), reporta como 'el autor afirma…' o 'según el autor…'."
        )
        user = (
            f"Divulgador: {creator['name']} ({creator['lang']}) · enfoque: {creator['focus']}\n"
            f"Título del vídeo: {video_title}\n\n"
            f"Transcript (puede estar truncado):\n{transcript}\n\n"
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

    # ---------- public entry point ----------
    async def check_and_process(self, *, max_new_per_channel: int = 1,
                                  max_llm_calls: int = 4, deliver: bool = True) -> dict:
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
                    transcript = await asyncio.get_event_loop().run_in_executor(
                        None, self._get_transcript, e["video_id"], langs
                    )
                    if not transcript or len(transcript) < 400:
                        logger.info("creators: skipping {} (no transcript)", e["video_id"])
                        skipped.append({"creator": creator["name"], "video_id": e["video_id"],
                                          "title": e["title"][:80], "reason": "transcript no disponible"})
                        seen.add(e["video_id"])  # don't keep retrying a captionless video
                        seen_map[cid] = list(seen)[-_MAX_SEEN_PER_CHANNEL:]
                        continue
                    summary = await self._summarize(creator, e["title"], transcript)
                    if not summary:
                        skipped.append({"creator": creator["name"], "video_id": e["video_id"],
                                          "title": e["title"][:80], "reason": "fallo del LLM"})
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
