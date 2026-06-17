"""Curated BUYABLE universe — what Yassine can actually buy in Trade Republic /
MyInvestor (UCITS ETFs in EUR where possible, a few funds, and major crypto).

Kept deliberately small (~18) so the whole universe can be scored on Render's
512MB tier WITHOUT the OOM that forced the 143-name discovery scan onto GitHub
Actions. Each entry: (ticker, name, asset_class). Bad/again-delisted tickers are
skipped gracefully at fetch time, never crash the pipeline.
"""

# asset_class: "equity_broad" | "equity_theme" | "commodity" | "bond" | "crypto"
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
    # Bonds (defensive sleeve)
    ("IBTM.L", "iShares $ Treasury 7-10y UCITS", "bond"),
    # Crypto (Kraken / major)
    ("BTC-EUR", "Bitcoin", "crypto"),
    ("ETH-EUR", "Ethereum", "crypto"),
]


def buyable_meta() -> dict[str, dict]:
    return {t: {"name": n, "asset_class": c} for t, n, c in BUYABLE}
