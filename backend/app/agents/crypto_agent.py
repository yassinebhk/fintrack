"""Crypto agent: BTC dominance, funding rates, sentiment around held coins."""

from app.agents.base import Agent, AgentContext


SYSTEM = """Eres un analista de criptomonedas. Evalúas el contexto cripto general y cómo afecta a los activos que el usuario tiene en cartera.

Reglas:
- Solo comentas sobre cripto, no equities.
- Eres factual, sin promesas.
- Respondes en español.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "regime": {"type": "string", "enum": ["risk_on", "risk_off", "neutral"]},
        "headline": {"type": "string"},
        "btc_view": {"type": "string", "description": "Comentario sobre BTC (1-2 frases)"},
        "alt_view": {"type": "string", "description": "Comentario sobre el resto de cripto en cartera"},
        "watch": {
            "type": "array",
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
    "required": ["regime", "headline", "btc_view", "alt_view", "watch"],
}


class CryptoAgent(Agent):
    name = "crypto"
    model_tier = "agent"
    system_prompt = SYSTEM
    response_schema = SCHEMA

    def build_user_prompt(self, context: AgentContext) -> str:
        portfolio = context.portfolio
        crypto_positions = [p for p in portfolio.get("positions", []) if p.get("type") == "crypto"]
        if not crypto_positions:
            return "El usuario no tiene posiciones cripto. Devuelve regime=neutral, headline corta, btc_view/alt_view vacíos y watch=[]."
        lines = ["Posiciones cripto del usuario:"]
        for p in crypto_positions:
            lines.append(
                f"  - {p['ticker']} qty={p['quantity']:.6g} @ {p['current_price']:.6g} "
                f"| day={p['day_change_pct']:+.2f}% | P/L total={p['gain_loss_pct']:+.2f}%"
            )
        market_extras = context.extras.get("crypto_market", {})
        if market_extras:
            lines.append("")
            lines.append("Contexto de mercado:")
            for k, v in market_extras.items():
                lines.append(f"  - {k}: {v}")
        lines.append("")
        lines.append("Devuelve un JSON con regime, headline, btc_view, alt_view, watch.")
        return "\n".join(lines)
