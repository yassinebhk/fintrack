"""Risk agent: concentration, drawdown, allocation drift."""

from app.agents.base import Agent, AgentContext, render_portfolio_for_prompt


SYSTEM = """Eres un risk manager. Evalúas la cartera del usuario buscando riesgos no obvios.

Reglas:
- Foco en concentración por activo, por broker, por tipo, por moneda.
- Comentas drawdown actual y volatilidad implícita por la composición.
- Detectas correlaciones evidentes (ej. cartera 90% cripto).
- No das tickers concretos a comprar.
- Respondes en español.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "headline": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                    "description": {"type": "string"},
                    "metric": {"type": "string"},
                },
                "required": ["kind", "severity", "description"],
            },
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Sugerencias genéricas de gestión de riesgo (sin tickers)",
        },
    },
    "required": ["risk_level", "headline", "issues", "suggestions"],
}


class RiskAgent(Agent):
    name = "risk"
    model_tier = "agent"
    system_prompt = SYSTEM
    response_schema = SCHEMA

    def build_user_prompt(self, context: AgentContext) -> str:
        portfolio = context.portfolio
        rendered = render_portfolio_for_prompt(portfolio)
        kpis = portfolio.get("kpis", {})
        kpi_lines = [
            f"  - CAGR: {kpis.get('cagr', 0):.2f}%",
            f"  - Max drawdown: {kpis.get('max_drawdown', 0):.2f}% (fecha: {kpis.get('max_drawdown_date')})",
            f"  - Volatilidad anualizada: {kpis.get('volatility', 0):.2f}%",
            f"  - Sharpe: {kpis.get('sharpe_ratio', 0):.2f}",
            f"  - Días registrados: {kpis.get('days_tracked', 0)}",
        ]
        return (
            "Evalúa el riesgo de la siguiente cartera. Identifica concentraciones, "
            "deriva de tipos correlados, y sugiere acciones genéricas.\n\n"
            f"{rendered}\n\nKPIs:\n" + "\n".join(kpi_lines)
        )
