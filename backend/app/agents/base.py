"""Base class for analyst agents.

Each agent:
  1) Receives an `AgentContext` (portfolio snapshot + ad-hoc data).
  2) Builds its user prompt from the context.
  3) Calls the configured LLM (Gemini Flash by default) with a JSON schema.
  4) Persists the run into `agent_runs` for audit.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.db import session_scope
from app.llm import LLMMessage, get_llm_client
from app.models.agent_run import AgentRun


@dataclass
class AgentContext:
    portfolio: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    agent: str
    model: str
    output: dict
    text: str
    tokens_input: int
    tokens_output: int
    duration_ms: int


class Agent:
    name: str = "base"
    model_tier: str = "agent"  # "orchestrator" | "agent" | "cheap"
    system_prompt: str = ""
    response_schema: dict | None = None

    def get_model(self) -> str | None:
        from app.config import get_settings

        s = get_settings()
        if self.model_tier == "orchestrator":
            return s.gemini_model_orchestrator
        if self.model_tier == "cheap":
            return s.gemini_model_cheap
        return s.gemini_model_agent

    def build_user_prompt(self, context: AgentContext) -> str:
        """Override per agent."""
        raise NotImplementedError

    max_tokens: int = 2048

    async def run(self, context: AgentContext) -> AgentResult:
        client = get_llm_client()
        user_prompt = self.build_user_prompt(context)
        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        started = time.perf_counter()
        try:
            resp = await client.generate(
                messages,
                model=self.get_model(),
                max_tokens=self.max_tokens,
                temperature=0.3,
                json_schema=self.response_schema,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            output = resp.structured or self._safe_json(resp.text)
            await self._log(
                status="ok",
                model=resp.model,
                tokens_in=resp.tokens_input,
                tokens_out=resp.tokens_output,
                cache_read=resp.cache_read_tokens,
                duration_ms=duration_ms,
                inputs=context.extras,
                summary=resp.text[:512],
            )
            return AgentResult(
                agent=self.name,
                model=resp.model,
                output=output,
                text=resp.text,
                tokens_input=resp.tokens_input,
                tokens_output=resp.tokens_output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception("agent {} failed", self.name)
            await self._log(
                status="error",
                model=self.get_model() or "?",
                tokens_in=0,
                tokens_out=0,
                cache_read=0,
                duration_ms=duration_ms,
                inputs=context.extras,
                summary="",
                error=str(exc),
            )
            raise

    def _safe_json(self, text: str) -> dict:
        if not text:
            return {}
        # Strip markdown code fences if the model wrapped JSON in them
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            # Drop the language hint (e.g. ```json\n)
            if "\n" in cleaned:
                first, rest = cleaned.split("\n", 1)
                if first.lower().strip() in {"json", "", "javascript"}:
                    cleaned = rest
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Try to locate the first JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            chunk = cleaned[start : end + 1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                logger.warning("agent {}: could not parse JSON chunk", self.name)
        return {"raw_text": text}

    async def _log(
        self,
        *,
        status: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cache_read: int,
        duration_ms: int,
        inputs: dict,
        summary: str,
        error: str | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                row = AgentRun(
                    agent_name=self.name,
                    model=model,
                    status=status,
                    inputs=inputs,
                    output_summary=summary,
                    error_message=error,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    cache_read_tokens=cache_read,
                    duration_ms=duration_ms,
                    started_at=datetime.now(timezone.utc),
                )
                session.add(row)
        except Exception as exc:
            logger.warning("could not persist agent_run for {}: {}", self.name, exc)


def render_portfolio_for_prompt(portfolio: dict, max_positions: int = 20) -> str:
    """Compact textual rendering of the portfolio for inclusion in prompts."""
    lines: list[str] = []
    lines.append(
        f"Total value: {portfolio.get('total_value', 0):.2f} {portfolio.get('base_currency', 'EUR')}"
        f" | P/L: {portfolio.get('total_gain_loss', 0):+.2f} ({portfolio.get('total_gain_loss_pct', 0):+.2f}%)"
        f" | Daily change: {portfolio.get('daily_change', 0):+.2f} ({portfolio.get('daily_change_pct', 0):+.2f}%)"
    )
    lines.append("")
    lines.append("Positions:")
    for pos in (portfolio.get("positions") or [])[:max_positions]:
        lines.append(
            f"  - {pos['ticker']} ({pos.get('type', '?')}, {pos.get('broker', '?')}): "
            f"qty={pos.get('quantity'):.6g} @ {pos.get('current_price'):.4g} {pos.get('currency', '')} "
            f"| value={pos.get('market_value_base', 0):.2f} "
            f"| P/L={pos.get('gain_loss_pct', 0):+.2f}% "
            f"| weight={pos.get('weight', 0):.1f}% "
            f"| day={pos.get('day_change_pct', 0):+.2f}%"
        )
    by_type = portfolio.get("by_type") or {}
    if by_type:
        lines.append("")
        lines.append("Distribution by asset type:")
        for t, info in by_type.items():
            lines.append(f"  - {t}: {info.get('weight', 0):.1f}% ({info.get('value', 0):.2f})")
    return "\n".join(lines)
