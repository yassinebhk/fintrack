"""Curated BUYABLE universe — what Yassine can actually buy in Trade Republic /
MyInvestor (UCITS ETFs in EUR where possible, a few funds, and major crypto).

Kept deliberately compact (~30) so the whole universe can be scored well within
the Oracle Always-Free VM's memory (and even Render's old 512MB tier), avoiding
the OOM that forced the 143-name discovery scan onto GitHub Actions. Each entry:
(ticker, name, asset_class). Bad/again-delisted tickers are skipped gracefully at
fetch time, never crash the pipeline — so a wrong symbol degrades, never breaks.

2026-09-10: broadened beyond pure ETFs at Yassine's request — added liquid single
stocks (equity_single) and a proper bond curve (ultrashort→20y, TIPS, IG, HY) so
the quant engine can rank real trading candidates cross-sectionally, not just
funds. Single-name risk is contained by a dedicated sleeve cap (see risk.py).
"""

# asset_class: "equity_broad" | "equity_theme" | "equity_single"
#            | "commodity" | "bond" | "crypto"
BUYABLE: list[tuple[str, str, str]] = [
    # Broad market (core)
    ("EUNL.DE", "iShares Core MSCI World UCITS", "equity_broad"),
    ("VWCE.DE", "Vanguard FTSE All-World UCITS", "equity_broad"),
    ("EQQQ.DE", "Invesco Nasdaq-100 UCITS", "equity_broad"),
    ("SXR8.DE", "iShares Core S&P 500 UCITS", "equity_broad"),
    ("XMME.DE", "Xtrackers MSCI Emerging Mkts UCITS", "equity_broad"),
    # Thematic / sector (UCITS, mostly EUR)
    ("VVSM.DE", "VanEck Semiconductor UCITS", "equity_theme"),
    ("QDVF.DE", "iShares S&P 500 Energy UCITS", "equity_theme"),
    ("NUKL.DE", "VanEck Uranium & Nuclear UCITS", "equity_theme"),
    ("COPX.L", "Global X Copper Miners UCITS", "equity_theme"),
    ("JEDI.DE", "VanEck Space Innovators UCITS", "equity_theme"),
    ("BATT.L", "L&G Battery Value-Chain UCITS", "equity_theme"),
    ("BTEC.L", "iShares Nasdaq US Biotech UCITS", "equity_theme"),
    ("WCLD.L", "WisdomTree Cloud Computing UCITS", "equity_theme"),
    # Commodities / defensives
    ("SGLN.L", "iShares Physical Gold", "commodity"),
    ("4GLD.DE", "Xetra-Gold", "commodity"),
    # Single stocks (liquid, buyable in TR/MyInvestor) — trading candidates the
    # engine ranks cross-sectionally. Edit this block freely; a bad symbol is
    # skipped, never fatal. USD names price in USD, EUR/DKK names in their ccy —
    # factors are return-based so mixing currencies is fine.
    ("NVDA",     "NVIDIA Corp",            "equity_single"),
    ("AMD",      "Advanced Micro Devices", "equity_single"),
    ("ASML.AS",  "ASML Holding (EUR)",     "equity_single"),
    ("MU",       "Micron Technology",      "equity_single"),
    ("PLTR",     "Palantir Technologies",  "equity_single"),
    ("AAPL",     "Apple Inc",              "equity_single"),
    ("NOVO-B.CO", "Novo Nordisk B (DKK)",  "equity_single"),
    # Bonds — a real curve + credit, not just one tenor (defensive + duration/
    # credit trading legs). All UCITS, buyable in TR/MyInvestor.
    ("IB01.L", "iShares $ Treasury 0-1y UCITS", "bond"),        # cash-like / ultrashort
    ("IBTM.L", "iShares $ Treasury 7-10y UCITS", "bond"),       # belly
    ("IDTL.L", "iShares $ Treasury 20+y UCITS", "bond"),        # long duration bet
    ("ITPS.L", "iShares $ TIPS UCITS", "bond"),                 # inflation-linked
    ("LQDE.L", "iShares $ Corp Bond UCITS", "bond"),            # investment-grade credit
    ("IHYU.L", "iShares $ High Yield Corp UCITS", "bond"),      # risk-on / HY
    # Crypto (Kraken / major)
    ("BTC-EUR", "Bitcoin", "crypto"),
    ("ETH-EUR", "Ethereum", "crypto"),
]


def buyable_meta() -> dict[str, dict]:
    return {t: {"name": n, "asset_class": c} for t, n, c in BUYABLE}
