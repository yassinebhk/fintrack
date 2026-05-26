"""FRED API client — US macro indicators (free, requires API key for full access).

Without FRED_API_KEY the service falls back to fredgraph CSV endpoints which are public
but rate-limited; useful for occasional briefing context.
"""

import csv
import io
from datetime import datetime, timedelta

import httpx
from loguru import logger

from app.config import get_settings


# Curated set of US macro series we care about for the briefing
SERIES = {
    "CPIAUCSL": {"label": "CPI (todos urbanos)", "unit": "índice 1982-84=100", "freq": "monthly"},
    "CPILFESL": {"label": "Core CPI", "unit": "índice", "freq": "monthly"},
    "UNRATE":   {"label": "Tasa de desempleo", "unit": "%", "freq": "monthly"},
    "DFF":      {"label": "Fed Funds rate", "unit": "%", "freq": "daily"},
    "DGS10":    {"label": "10Y Treasury yield", "unit": "%", "freq": "daily"},
    "DGS2":     {"label": "2Y Treasury yield", "unit": "%", "freq": "daily"},
    "VIXCLS":   {"label": "VIX", "unit": "índice", "freq": "daily"},
    "DEXUSEU":  {"label": "USD/EUR spot", "unit": "ratio", "freq": "daily"},
}


class FREDClient:
    BASE_URL = "https://api.stlouisfed.org/fred"
    FRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.fred_api_key
        self._cache: dict[str, dict] = {}
        self._cache_expiry: dict[str, datetime] = {}
        self._ttl = timedelta(hours=6)

    def _fresh(self, series_id: str) -> bool:
        return series_id in self._cache_expiry and datetime.now() < self._cache_expiry[series_id]

    async def get_latest(self, series_id: str) -> dict | None:
        """Most-recent observation of a series. Returns {date, value, label, unit} or None."""
        if self._fresh(series_id):
            return self._cache[series_id]

        try:
            if self.api_key:
                payload = await self._fetch_with_key(series_id)
            else:
                payload = await self._fetch_fredgraph(series_id)
        except Exception as exc:
            logger.warning("FRED fetch failed for {}: {}", series_id, exc)
            return None

        if payload:
            meta = SERIES.get(series_id, {})
            payload["label"] = meta.get("label", series_id)
            payload["unit"] = meta.get("unit", "")
            self._cache[series_id] = payload
            self._cache_expiry[series_id] = datetime.now() + self._ttl
        return payload

    async def _fetch_with_key(self, series_id: str) -> dict | None:
        url = f"{self.BASE_URL}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 2,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        obs = data.get("observations", [])
        if not obs:
            return None
        latest = obs[0]
        prev = obs[1] if len(obs) > 1 else None
        try:
            value = float(latest["value"])
            prev_value = float(prev["value"]) if prev and prev["value"] not in (".", "") else None
        except (ValueError, TypeError):
            return None
        return {
            "series_id": series_id,
            "date": latest["date"],
            "value": value,
            "previous_value": prev_value,
            "change": (value - prev_value) if prev_value is not None else None,
        }

    async def _fetch_fredgraph(self, series_id: str) -> dict | None:
        """Public CSV endpoint (no key). Used as fallback."""
        params = {"id": series_id}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.FRAPH_URL, params=params)
            resp.raise_for_status()
            text = resp.text
        reader = csv.DictReader(io.StringIO(text))
        rows = [r for r in reader if r.get(series_id) not in (".", "", None)]
        if not rows:
            return None
        latest = rows[-1]
        prev = rows[-2] if len(rows) > 1 else None
        try:
            value = float(latest[series_id])
            prev_value = float(prev[series_id]) if prev else None
        except (ValueError, TypeError):
            return None
        return {
            "series_id": series_id,
            "date": latest.get("DATE") or latest.get("observation_date"),
            "value": value,
            "previous_value": prev_value,
            "change": (value - prev_value) if prev_value is not None else None,
        }

    async def snapshot(self) -> list[dict]:
        """Returns the curated set of US macro indicators with their latest values."""
        results = []
        for series_id in SERIES:
            obs = await self.get_latest(series_id)
            if obs:
                results.append(obs)
        return results
