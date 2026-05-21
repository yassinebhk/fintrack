"""News agent: digests RSS feed items and links to held assets."""

from app.agents.base import Agent, AgentContext


SYSTEM = """Eres un analista de noticias financieras. Recibes titulares y los conectas con los activos de la cartera del usuario.

Reglas:
- Detectas el sentimiento (bullish/bearish/neutral) de cada noticia relevante.
- Identificas qué activos de la cartera están directa o indirectamente afectados.
- Eres breve y factual.
- Respondes en español.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "source": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                    "impact": {"type": "string", "enum": ["high", "medium", "low"]},
                    "affected_tickers": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
                "required": ["title", "sentiment", "impact", "affected_tickers", "rationale"],
            },
        },
        "headline": {"type": "string", "description": "Resumen 1-frase de lo más importante del día"},
    },
    "required": ["items", "headline"],
}


class NewsAgent(Agent):
    name = "news"
    model_tier = "cheap"  # Flash-Lite is enough for sentiment + extraction
    system_prompt = SYSTEM
    response_schema = SCHEMA

    def build_user_prompt(self, context: AgentContext) -> str:
        portfolio_tickers = sorted({p["ticker"] for p in context.portfolio.get("positions", [])})
        news_items = context.extras.get("news", [])[:30]

        lines = ["Tickers en cartera: " + ", ".join(portfolio_tickers), "", "Noticias recientes:"]
        for n in news_items:
            lines.append(
                f"- [{n.get('source', '?')}] {n.get('title', '')[:200]} "
                f"(impactedAssets={n.get('impactedAssets', [])}, impact={n.get('impact', 'neutral')})"
            )
        lines.append("")
        lines.append(
            "Filtra solo lo relevante para la cartera y devuelve un JSON con `items` y un `headline` global."
        )
        return "\n".join(lines)
