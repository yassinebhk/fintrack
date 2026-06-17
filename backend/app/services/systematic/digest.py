"""Clean, self-explanatory Telegram digest for the systematic paper portfolio."""

from __future__ import annotations

from app.services.systematic import paper
from app.services.systematic.buyable import buyable_meta


async def telegram_digest() -> str:
    from app.services.notifications.telegram import html_escape
    r = await paper.report()
    meta = buyable_meta()

    lines = [
        "🤖 <b>Sistema FinTrack</b> · cartera sistemática (papel, sin dinero real)",
        "<i>Elige ETFs/fondos/cripto por señales cuantitativas, los pondera por riesgo "
        "y mide si bate a comprar MSCI World a secas. Pasa a real solo si lo demuestra.</i>",
        "━━━━━━━━━━━━━━",
    ]

    if r.get("status", "").startswith("sin marcas") or not r.get("marks"):
        lines.append("📈 <b>Rendimiento:</b> arrancando — aún sin curva de valor.")
    else:
        a = r["alpha_pct"]
        lines += [
            f"📈 <b>Rendimiento</b> (desde inicio · {r['days']}d)",
            f"• Cartera <b>{r['return_pct']:+}%</b> vs MSCI World {r['benchmark_return_pct']:+}% "
            f"→ alpha <b>{a:+}%</b> {'✅' if a > 0 else '❌'}",
            f"• Sharpe {r['sharpe']} vs {r['benchmark_sharpe']} (benchmark) "
            f"<i>— rentabilidad por unidad de riesgo</i>",
            f"• PSR <b>{int((r['psr'] or 0)*100)}%</b> <i>— probabilidad de que el edge sea real, "
            f"no suerte (queremos ≥75%)</i>",
            f"• Máx. caída: {r['max_drawdown_pct']}%",
        ]

    holdings = r.get("holdings", {})
    if holdings:
        rows = sorted(holdings.items(), key=lambda kv: kv[1], reverse=True)
        tbl = [f"{'ACTIVO':<12}{'PESO':>6}"]
        for tk, w in rows:
            nm = (meta.get(tk, {}).get("name") or tk).replace("&", "y")[:12]
            tbl.append(f"{nm:<12}{w*100:>5.0f}%")
        inv = r.get("invested_pct", sum(holdings.values()) * 100)
        lines += ["", f"🧺 <b>Cartera actual</b> (régimen {r.get('regime','?')}, "
                  f"invertido {inv:.0f}%, resto liquidez):",
                  "<pre>" + html_escape("\n".join(tbl)) + "</pre>"]
    elif r.get("note"):
        lines += ["", f"🧺 {html_escape(r['note'])}"]

    rd = r.get("readiness", {})
    lines += ["", f"🚦 <b>¿Listo para dinero real?</b> {'SÍ ✅' if rd.get('ready') else 'NO ❌'}",
              f"<i>{html_escape(rd.get('verdict',''))}. Bar: ≥8 semanas, batir al MSCI World en "
              "retorno y Sharpe, PSR≥75%, y sin desplome. Hasta entonces, solo papel.</i>"]
    return "\n".join(lines)
