"""Analyst agent — the 'market analyst' that finds opportunities the user doesn't know about.

Grounded on real sector/theme momentum + macro + the user's portfolio. Proposes
concrete opportunities (themes, ETFs, funds like Robeco Smart Energy / Horos Value
when they fit) each with a full overview: what it is, why now, risks, and fit.
"""

from app.agents.base import Agent, AgentContext, render_portfolio_for_prompt


SYSTEM = """Eres un analista de inversiones profesional que trabaja para el usuario. Cada día revisas
el mercado y le traes 2-4 OPORTUNIDADES concretas que probablemente desconoce, como haría un gestor.

Tienes:
- Datos REALES de momentum de sectores/temas (retornos a 1m/3m/1y, posición en rango anual).
- SEÑALES TÉCNICAS objetivas calculadas por la librería `ta` (RSI, MACD, tendencia SMA, Bollinger),
  incluidas en cada tema como [técnico: ...]. Son DATOS, no opinión: úsalas para el timing (RSI<30
  sobreventa = posible entrada; RSI>70 sobrecompra = cuidado; tendencia/MACD confirman dirección).
- Titulares de NOTICIAS recientes con su sentimiento (Bloomberg, Reuters, FT, CoinDesk, Expansión...).
- Contexto macro (tipos, inflación).
- La cartera actual del usuario (para detectar qué le falta y evitar redundancias).

Reglas:
0. EQUILIBRIO MOMENTUM vs VALOR (MUY IMPORTANTE): no recomiendes solo lo que está en máximos. Propón un MIX:
   - 1-2 ideas de MOMENTUM (tendencia fuerte, de la lista CALIENTES) — pero advierte si están caras/extendidas.
   - 1-2 ideas de VALOR/CONTRARIAN (de la lista EN CORRECCIÓN/zona baja, o fondos value): activos sólidos
     caídos o rezagados con catalizador y potencial de recuperación a meses. Comprar barato con criterio,
     no solo perseguir lo que ya subió. Si algo está en mínimos pero el negocio es bueno, explícalo.
   Un buen gestor combina ambas; evita que TODAS tus ideas estén en máximos.
1. Propón oportunidades CONCRETAS y variadas: pueden ser temas/sectores, ETFs (UCITS si es para Europa),
   o fondos gestionados conocidos (p.ej. Robeco Smart Energy, Horos Value Internacional, Fundsmith,
   Baelo, Seilern...) cuando encajen.
2. Para CADA oportunidad da un overview completo: qué es, en qué invierte, por qué es interesante AHORA
   (liga tu razón a los datos de momentum/macro Y a las noticias recientes cuando sean relevantes),
   riesgos, y cómo encaja en la cartera del usuario. Si una noticia reciente respalda o desaconseja una
   idea, menciónalo.
3. Prioriza la DIVERSIFICACIÓN: si el usuario está muy concentrado (ej. mucho cripto), valora ideas que
   compensen ese riesgo.
4. Marca tu nivel de convicción (alta/media/baja) y sé honesto: si algo está caro o en máximos, dilo.
5. Distingue DATO (lo que sabes por los números) de OPINIÓN/análisis (tu criterio).
6. NO prometas rentabilidades ni des órdenes de compra. Es análisis educativo.
7. Responde en español, claro y para leer en el móvil.
8. SÉ CONCISO: cada campo (what_it_is, why_now, risks, fit) en 1-2 frases. Propón 3 oportunidades
   (no más) para no extenderte. La brevedad es importante.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "market_summary": {"type": "string", "description": "2-3 frases sobre el régimen de mercado hoy según los datos"},
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la oportunidad (fondo/ETF/tema)"},
                    "kind": {"type": "string", "enum": ["tema", "etf", "fondo", "sector"]},
                    "approach": {"type": "string", "enum": ["momentum", "valor", "contrarian"],
                                 "description": "momentum=tendencia fuerte/máximos; valor/contrarian=barato o caído con potencial"},
                    "ticker_or_isin": {"type": "string", "description": "Ticker/ISIN si lo conoces, vacío si no"},
                    "what_it_is": {"type": "string", "description": "Qué es y en qué invierte (overview)"},
                    "why_now": {"type": "string", "description": "Por qué es interesante ahora, ligado a datos"},
                    "risks": {"type": "string", "description": "Riesgos principales"},
                    "fit": {"type": "string", "description": "Cómo encaja en la cartera del usuario"},
                    "conviction": {"type": "string", "enum": ["alta", "media", "baja"]},
                },
                "required": ["name", "kind", "approach", "what_it_is", "why_now", "risks", "fit", "conviction"],
            },
        },
        "disclaimer": {"type": "string"},
    },
    "required": ["market_summary", "opportunities", "disclaimer"],
}


class AnalystAgent(Agent):
    name = "analyst"
    model_tier = "agent"
    system_prompt = SYSTEM
    response_schema = SCHEMA
    # Gemini 2.5 Flash spends a big chunk of the budget on internal "thinking";
    # give it plenty of headroom so the JSON output isn't truncated mid-array.
    max_tokens = 8192

    def build_user_prompt(self, context: AgentContext) -> str:
        themes_str = context.extras.get("themes_str", "(sin datos de sectores)")
        macro = context.extras.get("macro", {}) or {}
        portfolio = context.portfolio or {}

        macro_lines = []
        for s in (macro.get("us", []) or [])[:4]:
            macro_lines.append(f"  - {s.get('label')}: {s.get('value')} {s.get('unit','')}")
        for s in (macro.get("eu", []) or [])[:3]:
            macro_lines.append(f"  - {s.get('label')}: {s.get('value')} {s.get('unit','')}")
        macro_str = "\n".join(macro_lines) if macro_lines else "  (sin datos macro)"

        rendered_portfolio = render_portfolio_for_prompt(portfolio)
        news_str = context.extras.get("news_str", "") or "(sin titulares)"

        return (
            "## Datos de mercado (momentum real de sectores/temas)\n"
            f"{themes_str}\n\n"
            "## Noticias recientes\n"
            f"{news_str}\n\n"
            "## Macro\n"
            f"{macro_str}\n\n"
            "## Cartera actual del usuario\n"
            f"{rendered_portfolio}\n\n"
            "## Tu tarea\n"
            "Propón 2-4 oportunidades concretas que el usuario probablemente desconoce, cada una con "
            "overview completo (what_it_is, why_now ligado a los datos Y noticias, risks, fit con su cartera, "
            "conviction). Cuando una noticia reciente sea relevante para una idea, menciónala. "
            "Prioriza diversificar su riesgo actual. Distingue dato de opinión."
        )
