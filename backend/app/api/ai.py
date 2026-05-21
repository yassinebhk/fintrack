"""AI chat endpoint — uses Gemini via the unified LLM client.

Provider precedence: Gemini → Groq fallback → static config message.
"""

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

from app.config import get_settings
from app.llm import LLMMessage, get_llm_client
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api/ai", tags=["ai"])
_portfolio = PortfolioService()

AI_SYSTEM_PROMPT = """Eres FinBot, un asesor financiero virtual experto y pedagógico.

Reglas:
- Hablas SIEMPRE en español.
- Eres amable, cercano y didáctico.
- Explicas conceptos complejos de forma simple.
- Nunca recomiendas comprar/vender tickers concretos (regulación).
- Recomiendas diversificación y horizonte a largo plazo.
- Si te preguntan sobre la cartera del usuario, la analizas de forma educativa.
- Si la pregunta toca inversión, añades un disclaimer breve al final.
"""

CONFIG_MSG = (
    "¡Hola! Soy FinBot, tu asesor financiero virtual.\n\n"
    "Aún no tengo configurada ninguna API key de LLM. Para activarme, "
    "el administrador necesita definir GEMINI_API_KEY (o GROQ_API_KEY) en las "
    "variables de entorno del servidor.\n\n"
    "Mientras tanto puedes explorar la sección 'Aprender' o ver tus posiciones."
)


class AIQuestion(BaseModel):
    question: str
    include_portfolio: bool = True


def _build_portfolio_context(portfolio: dict) -> str:
    lines = [
        "DATOS DE LA CARTERA DEL USUARIO:",
        f"- Valor total: {portfolio.get('total_value', 0):.2f} {portfolio.get('base_currency', 'EUR')}",
        f"- Ganancia/Pérdida total: {portfolio.get('total_gain_loss', 0):+.2f} ({portfolio.get('total_gain_loss_pct', 0):+.2f}%)",
        f"- Cambio hoy: {portfolio.get('daily_change', 0):+.2f} ({portfolio.get('daily_change_pct', 0):+.2f}%)",
        "",
        "POSICIONES:",
    ]
    for pos in (portfolio.get("positions") or [])[:15]:
        lines.append(
            f"- {pos['ticker']} ({pos.get('type', '?')}): {pos.get('quantity'):.6g} unidades, "
            f"P/L: {pos.get('gain_loss_pct', 0):+.1f}%, Peso: {pos.get('weight', 0):.1f}%"
        )
    by_type = portfolio.get("by_type") or {}
    if by_type:
        lines.append("")
        lines.append("DISTRIBUCIÓN POR TIPO:")
        for t, info in by_type.items():
            lines.append(f"- {t}: {info.get('weight', 0):.1f}%")
    return "\n".join(lines)


@router.post("/chat")
async def ai_chat(question: AIQuestion) -> dict:
    settings = get_settings()
    if not settings.has_gemini and not settings.has_groq:
        return {"response": CONFIG_MSG, "model": "none", "tokens_used": 0}

    context = ""
    if question.include_portfolio:
        try:
            p = await _portfolio.calculate_portfolio()
            context = _build_portfolio_context(p)
        except Exception as exc:
            logger.warning("could not build portfolio context: {}", exc)

    user_msg = f"{context}\n\nPREGUNTA DEL USUARIO: {question.question}" if context else question.question

    try:
        client = get_llm_client()
        resp = await client.generate(
            [
                LLMMessage(role="system", content=AI_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_msg),
            ],
            max_tokens=1500,
            temperature=0.7,
        )
        return {
            "response": resp.text,
            "model": resp.model,
            "tokens_used": resp.tokens_input + resp.tokens_output,
        }
    except Exception as exc:
        logger.exception("ai chat failed")
        return {
            "response": f"Lo siento, hubo un error procesando tu pregunta: {exc}. Intenta de nuevo en unos segundos.",
            "model": "error",
            "tokens_used": 0,
        }
