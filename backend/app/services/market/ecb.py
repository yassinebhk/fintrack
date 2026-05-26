"""ECB Statistical Data Warehouse client — Euro area macro indicators (free, no key).

Uses the SDMX 2.1 REST API. Returns JSON. We pull a small curated set of series.
"""

from datetime import datetime, timedelta

import httpx
from loguru import logger


BASE_URL = "https://data-api.ecb.europa.eu/service/data"

# (flowRef, key) → metadata. Keys follow ECB SDMX conventions.
SERIES: dict[str, dict] = {
    "ecb_mrr": {
        "flow": "FM",
        "key": "B.U2.EUR.4F.KR.MRR_FR.LEV",
        "label": "Tipo principal de refinanciación BCE",
        "unit": "%",
    },
    "ecb_dfr": {
        "flow": "FM",
        "key": "B.U2.EUR.4F.KR.DFR.LEV",
        "label": "Tipo depósito BCE",
        "unit": "%",
    },
    "eu_hicp": {
        "flow": "ICP",
        "key": "M.U2.N.000000.4.ANR",
        "label": "HICP zona euro (inflación interanual)",
        "unit": "%",
    },
    "eu_unemployment": {
        "flow": "LFSI",
        "key": "M.I9.S.UNEHRT.TOTAL0.15_74.T",
        "label": "Tasa desempleo zona euro",
        "unit": "%",
    },
}


class ECBClient:
    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}
        self._cache_expiry: dict[str, datetime] = {}
        self._ttl = timedelta(hours=12)

    def _fresh(self, key: str) -> bool:
        return key in self._cache_expiry and datetime.now() < self._cache_expiry[key]

    async def get_latest(self, alias: str) -> dict | None:
        meta = SERIES.get(alias)
        if not meta:
            return None
        if self._fresh(alias):
            return self._cache[alias]
        url = f"{BASE_URL}/{meta['flow']}/{meta['key']}"
        params = {"lastNObservations": 2, "format": "jsondata"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("ECB fetch failed for {}: {}", alias, exc)
            return None

        try:
            datasets = data["dataSets"][0]["series"]
            (_, series_data) = next(iter(datasets.items()))
            obs = series_data["observations"]
            time_dim = data["structure"]["dimensions"]["observation"][0]["values"]
            # Sort by time index
            entries = sorted(((int(k), v[0]) for k, v in obs.items()), key=lambda x: x[0])
            if not entries:
                return None
            latest_idx, latest_value = entries[-1]
            prev_value = entries[-2][1] if len(entries) > 1 else None
            latest_date = time_dim[latest_idx]["id"]
        except (KeyError, IndexError, StopIteration, ValueError, TypeError) as exc:
            logger.warning("ECB parsing failed for {}: {}", alias, exc)
            return None

        result = {
            "series_id": alias,
            "date": latest_date,
            "value": float(latest_value),
            "previous_value": float(prev_value) if prev_value is not None else None,
            "change": (float(latest_value) - float(prev_value)) if prev_value is not None else None,
            "label": meta["label"],
            "unit": meta["unit"],
        }
        self._cache[alias] = result
        self._cache_expiry[alias] = datetime.now() + self._ttl
        return result

    async def snapshot(self) -> list[dict]:
        results = []
        for alias in SERIES:
            obs = await self.get_latest(alias)
            if obs:
                results.append(obs)
        return results
