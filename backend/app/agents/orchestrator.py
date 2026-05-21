"""Orchestrator: consumes all specialist outputs and writes the user-facing briefing."""

import json

from app.agents.base import Agent, AgentContext, render_portfolio_for_prompt


SYSTEM = """Eres el orquestador de un equipo de analistas financieros (Market, News, Risk, Crypto).

Recibes:
- El snapshot actual de la cartera del usuario.
- Las conclusiones de los analistas (en JSON).

Tu trabajo:
1. Producir un briefing diario en español, claro y accionable.
2. Decir qué pasó en la cartera del usuario, qué pasó en mercados y qué vigilar hoy.
3. Sugerir UNA acción razonable (DCA / no hacer nada / revisar X / esperar). Nunca tickers concretos a comprar/vender.
4. Mantener tono honesto: si hay poco que decir, dilo. No inventes.
5. Incluir un disclaimer breve al final.

Formato esperado: JSON con headline, sections (lista de {title, body}), suggested_action, disclaimer.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Titular de hoy (1 frase)"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["title", "body"],
            },
            "description": "Secciones: Cartera ayer / Lo que pasó en mercados / Qué vigilar hoy",
        },
        "suggested_action": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": ["dca", "rebalance", "hold", "watch", "review_risk", "none"]},
                "rationale": {"type": "string"},
            },
            "required": ["label", "rationale"],
        },
        "disclaimer": {"type": "string"},
    },
    "required": ["headline", "sections", "suggested_action", "disclaimer"],
}


class OrchestratorAgent(Agent):
    name = "orchestrator"
    model_tier = "orchestrator"
    system_prompt = SYSTEM
    response_schema = SCHEMA
    max_tokens = 4096

    def build_user_prompt(self, context: AgentContext) -> str:
        portfolio = context.portfolio
        sub_results = context.extras.get("sub_results", {})
        rendered_portfolio = render_portfolio_for_prompt(portfolio)
        rendered_subs = json.dumps(sub_results, ensure_ascii=False, indent=2)
        return (
            "Genera el briefing diario.\n\n"
            "## Snapshot de cartera\n"
            f"{rendered_portfolio}\n\n"
            "## Conclusiones de los analistas\n"
            f"{rendered_subs}\n\n"
            "## Instrucciones\n"
            "- 3 secciones (Cartera, Mercados, Qué vigilar).\n"
            "- 1 acción sugerida con label de la enumeración.\n"
            "- Disclaimer breve sobre que esto es educativo, no asesoramiento."
        )
