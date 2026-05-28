"""Curated list of finance analysts / divulgadores we follow on YouTube.

Quality over quantity. We avoid alarmist / pump-and-dump content. Each entry
includes the channel_id (verified) so we can hit YouTube's RSS without scraping.
Handles included for readability and as a fallback if the ID ever changes.

Add or remove freely — list-driven, no schema change needed.
"""

# Each entry: handle (cosmetic), human name, language, focus, channel_id (verified).
CREATORS: list[dict] = [
    # --- Español ---
    {"handle": "@JoseLuisCavaTV", "name": "José Luis Cava", "lang": "es",
     "focus": "análisis técnico de bolsa española y EEUU",
     "channel_id": "UCvCCLJkQpRg0NdT3zNcI08A"},
    {"handle": "@DLacalle", "name": "Daniel Lacalle", "lang": "es",
     "focus": "macroeconomía y mercados",
     "channel_id": "UCFbuyBmlQC24PbUuroR3gjw"},
    {"handle": "@PabloGilTrader", "name": "Pablo Gil", "lang": "es",
     "focus": "macro · trading",
     "channel_id": "UCPQ2dheMajZPnIleYZHzblg"},

    # --- English ---
    {"handle": "@PatrickBoyle", "name": "Patrick Boyle", "lang": "en",
     "focus": "academic finance · markets commentary",
     "channel_id": "UCOIi9OLSpXRsX-wp2u26fsA"},
    {"handle": "@AswathDamodaranonValuation", "name": "Aswath Damodaran", "lang": "en",
     "focus": "valuation · NYU Stern",
     "channel_id": "UCLvnJL8htRR1T9cbSccaoVw"},
    {"handle": "@BenFelixCSI", "name": "Ben Felix", "lang": "en",
     "focus": "evidence-based investing · factor research",
     "channel_id": "UCDXTQ8nWmx_EhZ2v-kp7QxA"},
    {"handle": "@TheCompoundNews", "name": "The Compound (Josh Brown)", "lang": "en",
     "focus": "markets commentary (Ritholtz Wealth)",
     "channel_id": "UCBRpqrzuuqE8TZcWw75JSdw"},
]


# Long-form finance newsletters / blogs (RSS, free, no API key needed). Same
# pipeline as YouTubers: ingest → LLM summary → Telegram + cache.
NEWSLETTERS: list[dict] = [
    {"name": "Of Dollars and Data — Nick Maggiulli", "lang": "en",
     "focus": "personal finance · data-driven",
     "feed": "https://ofdollarsanddata.com/feed/"},
    {"name": "A Wealth of Common Sense — Ben Carlson", "lang": "en",
     "focus": "markets commentary",
     "feed": "https://awealthofcommonsense.com/feed/"},
    {"name": "Musings on Markets — Aswath Damodaran", "lang": "en",
     "focus": "valuation · NYU",
     "feed": "http://aswathdamodaran.blogspot.com/feeds/posts/default"},
    {"name": "Lyn Alden", "lang": "en",
     "focus": "macro · monetary",
     "feed": "https://www.lynalden.com/feed/"},
]

