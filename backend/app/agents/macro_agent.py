"""Macro agent: contextualizes the portfolio with US + EU macro data and the next economic releases."""

from app.agents.base import Agent, AgentContext


SYSTEM = """Eres un analista macroeconómico. Tienes acceso a indicadores reales de USA (FRED) y zona euro (BCE) más el calendario de próximos eventos.

Reglas:
- Comentas lo que de verdad puede mover la cartera del usuario (inflación, tipos, paro, yields).
- Eres conciso: 2-3 ideas máximo.
- Cuando menciones un dato, di la cifra y compárala con la previa.
- No haces predicciones cerradas; describes el régimen.
- Respondes en español.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "regime": {
            "type": "string",
            "enum": ["risk_on", "risk_off", "neutral"],
            "description": "Régimen macro implícito",
        },
        "headline": {"type": "string", "description": "1 frase resumen"},
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Inflación / Tipos / Empleo / Yields / FX / Volatilidad"},
                    "comment": {"type": "string", "description": "Dato + interpretación corta"},
                },
                "required": ["topic", "comment"],
            },
        },
        "upcoming": {
            "type": "array",
            "description": "Eventos relevantes en los próximos 7 días",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "event": {"type": "string"},
                    "why_matters": {"type": "string"},
                },
                "required": ["date", "event"],
            },
        },
    },
    "required": ["regime", "headline", "highlights"],
}


class MacroAgent(Agent):
    name = "macro"
    model_tier = "agent"
    system_prompt = SYSTEM
    response_schema = SCHEMA

    def build_user_prompt(self, context: AgentContext) -> str:
        macro = context.extras.get("macro", {}) or {}
        us = macro.get("us", []) or []
        eu = macro.get("eu", []) or []
        upcoming = macro.get("upcoming", []) or []

        lines = ["## Datos macro USA (FRED)"]
        if us:
            for s in us:
                change = ""
                if s.get("change") is not None:
                    change = f" (cambio: {s['change']:+.3f})"
                lines.append(f"- {s.get('label', s.get('series_id'))}: {s.get('value')} {s.get('unit', '')} @ {s.get('date')}{change}")
        else:
            lines.append("- (sin datos: FRED no respondió o FRED_API_KEY no configurada)")

        lines.append("")
        lines.append("## Datos macro Zona Euro (BCE)")
        if eu:
            for s in eu:
                change = ""
                if s.get("change") is not None:
                    change = f" (cambio: {s['change']:+.3f})"
                lines.append(f"- {s.get('label', s.get('series_id'))}: {s.get('value')} {s.get('unit', '')} @ {s.get('date')}{change}")
        else:
            lines.append("- (sin datos)")

        lines.append("")
        lines.append("## Próximos eventos macro (próximos 7 días)")
        if upcoming:
            for ev in upcoming:
                lines.append(f"- {ev.get('date')}: {ev.get('name')} ({ev.get('region')}, impacto {ev.get('impact')})")
        else:
            lines.append("- (sin eventos relevantes próximos)")

        lines.append("")
        lines.append("## Cartera del usuario (alto nivel)")
        by_type = (context.portfolio or {}).get("by_type", {}) or {}
        for t, info in by_type.items():
            lines.append(f"- {t}: {info.get('weight', 0):.1f}% ({info.get('value', 0):.2f})")

        lines.append("")
        lines.append(
            "Devuelve JSON con regime, headline, highlights (2-3 puntos) y upcoming (eventos relevantes para esta cartera)."
        )
        return "\n".join(lines)
