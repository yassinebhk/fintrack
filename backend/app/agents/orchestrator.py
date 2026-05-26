"""Orchestrator: consumes all specialist outputs and writes the user-facing briefing."""

import json

from app.agents.base import Agent, AgentContext, render_portfolio_for_prompt


SYSTEM = """Eres el orquestador de un equipo de analistas financieros (Market, News, Risk, Crypto).

Recibes:
- El snapshot actual de la cartera del usuario.
- Las conclusiones de los analistas (en JSON).

Tu trabajo:
1. Producir un briefing diario en español, claro y accionable, OPTIMIZADO PARA MÓVIL.
2. Decir qué pasó en la cartera del usuario, qué pasó en mercados y qué vigilar hoy.
3. Sugerir UNA acción razonable (DCA / no hacer nada / revisar X / esperar). Nunca tickers concretos a comprar/vender.
4. Mantener tono honesto: si hay poco que decir, dilo. No inventes.
5. Incluir un disclaimer breve al final.

REGLAS DE FORMATO (críticas — esto se lee en Telegram en el móvil):
- Cada sección tiene un `body` de UNA frase corta (máx 25 palabras) como intro.
- Y un `bullets` con 2-4 puntos cortos (cada bullet ≤ 18 palabras, sin punto al final).
- Los bullets son frases completas autónomas, NO empiecen con conector ("y", "pero", "además").
- Habla directamente al usuario en español (tú, no usted).
- Cifras: usa formato compacto ("+2.21 €", "+0.61%"), nunca decimales largos.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Titular de hoy (1 frase, máx 15 palabras)"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Título corto (2-4 palabras)"},
                    "body": {"type": "string", "description": "Intro de UNA frase corta (máx 25 palabras)"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-4 puntos clave, cada uno ≤ 18 palabras, sin punto final",
                    },
                },
                "required": ["title", "body", "bullets"],
            },
            "description": "3 secciones: Cartera ayer / Mercados / Qué vigilar hoy",
        },
        "suggested_action": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": ["dca", "rebalance", "hold", "watch", "review_risk", "none"]},
                "rationale": {"type": "string", "description": "1 frase corta (máx 25 palabras)"},
            },
            "required": ["label", "rationale"],
        },
        "disclaimer": {"type": "string", "description": "1 frase breve, no más de 20 palabras"},
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
