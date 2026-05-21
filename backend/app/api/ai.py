"""AI chat endpoint — placeholder until Fase 2.2 wires the Gemini multi-agent stack."""

import httpx
from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

from app.config import get_settings
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api/ai", tags=["ai"])
_portfolio = PortfolioService()

AI_SYSTEM_PROMPT = """Eres un asesor financiero experto y educador. Tu nombre es FinBot.

IMPORTANTE:
- Hablas SIEMPRE en español.
- Eres amable, cercano y pedagógico.
- Explicas conceptos complejos de forma simple.
- Nunca das consejos específicos de compra/venta.
- Recomiendas diversificación y horizonte a largo plazo.
- Si te preguntan sobre la cartera del usuario, analizas sus posiciones de forma educativa.
- Termina con un disclaimer cuando hables de inversión.
"""

CONFIG_MSG = """¡Hola! Soy FinBot, tu asesor financiero virtual.

Estoy temporalmente en modo de transición: el equipo multi-agente con Gemini llega en la siguiente fase.
Mientras tanto, puedes explorar la sección "Aprender" o ver el briefing diario en la página "Hoy" (próximamente).
"""


class AIQuestion(BaseModel):
    question: str
    include_portfolio: bool = True


@router.post("/chat")
async def ai_chat(question: AIQuestion) -> dict:
    settings = get_settings()
    if not settings.has_groq and not settings.has_gemini:
        return {"response": CONFIG_MSG, "model": "none", "tokens_used": 0}

    context = ""
    if question.include_portfolio:
        try:
            p = await _portfolio.calculate_portfolio()
            context = (
                f"DATOS DE LA CARTERA DEL USUARIO:\n"
                f"- Valor total: {p['total_value']:.2f} {p['base_currency']}\n"
                f"- Ganancia/Pérdida total: {p['total_gain_loss']:.2f} ({p['total_gain_loss_pct']:.2f}%)\n"
                f"- Cambio hoy: {p['daily_change']:.2f} ({p['daily_change_pct']:.2f}%)\n\nPOSICIONES:\n"
            )
            for pos in p["positions"][:15]:
                context += (
                    f"- {pos['ticker']} ({pos['type']}): {pos['quantity']} unidades, "
                    f"P/L: {pos['gain_loss_pct']:.1f}%, Peso: {pos['weight']:.1f}%\n"
                )
        except Exception as exc:
            logger.warning("could not build portfolio context: {}", exc)

    # Quick Groq path until the Gemini agent stack lands in Fase 2.2.
    if settings.has_groq:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": AI_SYSTEM_PROMPT},
                            {"role": "user", "content": f"{context}\n\nPREGUNTA: {question.question}"},
                        ],
                        "max_tokens": 1500,
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "response": data["choices"][0]["message"]["content"],
                    "model": "llama-3.3-70b-versatile",
                    "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                }
        except Exception as exc:
            logger.error("groq chat error: {}", exc)
            return {"response": f"Error temporal en FinBot: {exc}", "model": "error", "tokens_used": 0}

    # If only gemini is configured, fall back to a placeholder until Fase 2.2.
    return {"response": CONFIG_MSG, "model": "gemini-pending-fase2", "tokens_used": 0}
