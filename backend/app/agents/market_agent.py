"""Market agent: comments on price action of held assets."""

from app.agents.base import Agent, AgentContext, render_portfolio_for_prompt


SYSTEM = """Eres un analista de mercados. Analizas la evolución diaria de los activos de la cartera del usuario.

Reglas:
- Eres conciso y técnico, sin promesas.
- No das consejos de compra/venta concretos.
- Usas datos provistos, sin inventar precios.
- Respondes en español.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Resumen general del día (2-3 frases)"},
        "movers": {
            "type": "array",
            "description": "Top 3 movimientos del día por % absoluto",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "day_change_pct": {"type": "number"},
                    "comment": {"type": "string"},
                },
                "required": ["ticker", "day_change_pct", "comment"],
            },
        },
        "watch": {
            "type": "array",
            "description": "Activos de la cartera a vigilar y por qué",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["ticker", "reason"],
            },
        },
    },
    "required": ["summary", "movers", "watch"],
}


class MarketAgent(Agent):
    name = "market"
    model_tier = "agent"
    system_prompt = SYSTEM
    response_schema = SCHEMA

    def build_user_prompt(self, context: AgentContext) -> str:
        rendered = render_portfolio_for_prompt(context.portfolio)
        return (
            "Analiza los movimientos de hoy en la cartera del usuario.\n\n"
            f"{rendered}\n\n"
            "Devuelve un JSON con: summary, movers (top 3 por |day_change_pct|), watch (lo que vigilar)."
        )
