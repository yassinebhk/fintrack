"""Curated discovery universe — the raw material the quant engine ranks.

These are liquid, real, Yahoo-resolvable ETFs (plus a few well-known funds)
across asset classes, regions, factors and themes. The scanner scores ALL of
them objectively; the top-ranked names the user does NOT already hold surface as
discoveries. This is what lets the engine propose opportunities the user doesn't
know — without the LLM inventing tickers.

Extend freely: add a row and it enters the ranking next scan. Tickers must exist
on Yahoo Finance (UCITS .L/.DE/.PA suffixes are fine).
"""

# (ticker, friendly name, category, region)
UNIVERSE: list[tuple[str, str, str, str]] = [
    # --- Broad market ---
    ("SPY", "S&P 500", "amplio", "EEUU"),
    ("QQQ", "Nasdaq-100", "amplio", "EEUU"),
    ("IWM", "Russell 2000 (small caps EEUU)", "amplio", "EEUU"),
    ("RSP", "S&P 500 equiponderado", "amplio", "EEUU"),
    ("VTI", "Total mercado EEUU", "amplio", "EEUU"),
    ("ACWI", "Renta variable mundial", "amplio", "Global"),
    ("SWDA.L", "MSCI World UCITS", "amplio", "Global"),
    ("VWRL.L", "FTSE All-World UCITS", "amplio", "Global"),
    ("EQQQ.L", "Nasdaq-100 UCITS", "amplio", "EEUU"),
    # --- US sectors ---
    ("XLK", "Tecnología EEUU", "sector", "EEUU"),
    ("XLF", "Financieras EEUU", "sector", "EEUU"),
    ("XLE", "Energía (petróleo/gas) EEUU", "sector", "EEUU"),
    ("XLV", "Salud EEUU", "sector", "EEUU"),
    ("XLI", "Industriales EEUU", "sector", "EEUU"),
    ("XLY", "Consumo discrecional EEUU", "sector", "EEUU"),
    ("XLP", "Consumo básico EEUU", "sector", "EEUU"),
    ("XLU", "Utilities EEUU", "sector", "EEUU"),
    ("XLB", "Materiales EEUU", "sector", "EEUU"),
    ("XLRE", "Inmobiliario (REITs) EEUU", "sector", "EEUU"),
    ("XLC", "Comunicación EEUU", "sector", "EEUU"),
    # --- Factors / style ---
    ("MTUM", "Factor momentum EEUU", "factor", "EEUU"),
    ("VLUE", "Factor value EEUU", "factor", "EEUU"),
    ("QUAL", "Factor calidad EEUU", "factor", "EEUU"),
    ("USMV", "Mínima volatilidad EEUU", "factor", "EEUU"),
    ("VUG", "Growth EEUU", "factor", "EEUU"),
    ("VTV", "Value EEUU", "factor", "EEUU"),
    ("IWVL.L", "MSCI World Value UCITS", "factor", "Global"),
    ("SCHD", "Dividendo de calidad EEUU", "factor", "EEUU"),
    ("VYM", "Alto dividendo EEUU", "factor", "EEUU"),
    ("VHYL.L", "Alto dividendo mundial UCITS", "factor", "Global"),
    # --- Regions / countries ---
    ("VGK", "Europa desarrollada", "región", "Europa"),
    ("EZU", "Eurozona", "región", "Europa"),
    ("EWG", "Alemania", "región", "Europa"),
    ("EWU", "Reino Unido", "región", "Europa"),
    ("EWQ", "Francia", "región", "Europa"),
    ("EWI", "Italia", "región", "Europa"),
    ("EWP", "España", "región", "Europa"),
    ("EWJ", "Japón", "región", "Asia"),
    ("MCHI", "China", "región", "Asia"),
    ("FXI", "China large caps", "región", "Asia"),
    ("KWEB", "China internet", "región", "Asia"),
    ("INDA", "India", "región", "Asia"),
    ("EWY", "Corea del Sur", "región", "Asia"),
    ("EWT", "Taiwán", "región", "Asia"),
    ("EWZ", "Brasil", "región", "Latam"),
    ("EWW", "México", "región", "Latam"),
    ("EWC", "Canadá", "región", "Norteamérica"),
    ("EWA", "Australia", "región", "Oceanía"),
    ("EEM", "Mercados emergentes", "región", "Emergentes"),
    ("VWO", "Emergentes (Vanguard)", "región", "Emergentes"),
    ("EFA", "Desarrollados ex-EEUU", "región", "Global"),
    # --- Thematic ---
    ("ICLN", "Energía limpia global", "temático", "Global"),
    ("TAN", "Energía solar", "temático", "Global"),
    ("INRG.L", "Energía limpia UCITS", "temático", "Global"),
    ("LIT", "Litio y baterías", "temático", "Global"),
    ("URA", "Uranio y nuclear", "temático", "Global"),
    ("URNM", "Mineras de uranio", "temático", "Global"),
    ("NLR", "Energía nuclear", "temático", "Global"),
    ("ROBO", "Robótica y automatización", "temático", "Global"),
    ("BOTZ", "Robótica e IA", "temático", "Global"),
    ("CIBR", "Ciberseguridad", "temático", "Global"),
    ("HACK", "Ciberseguridad (alt.)", "temático", "Global"),
    ("SKYY", "Cloud computing", "temático", "Global"),
    ("FINX", "Fintech", "temático", "Global"),
    ("ARKK", "Innovación disruptiva (ARK)", "temático", "EEUU"),
    ("SOXX", "Semiconductores", "temático", "EEUU"),
    ("SMH", "Semiconductores (VanEck)", "temático", "EEUU"),
    ("IBB", "Biotecnología", "temático", "EEUU"),
    ("XBI", "Biotech equiponderado", "temático", "EEUU"),
    ("PHO", "Agua (EEUU)", "temático", "EEUU"),
    ("PIO", "Agua global", "temático", "Global"),
    ("ITA", "Defensa y aeroespacial", "temático", "EEUU"),
    ("XAR", "Aeroespacial y defensa", "temático", "EEUU"),
    ("PPA", "Defensa (Invesco)", "temático", "EEUU"),
    ("GDX", "Mineras de oro", "temático", "Global"),
    ("GDXJ", "Mineras de oro junior", "temático", "Global"),
    ("COPX", "Mineras de cobre", "temático", "Global"),
    ("XME", "Metales y minería EEUU", "temático", "EEUU"),
    ("MOO", "Agronegocio", "temático", "Global"),
    ("JETS", "Aerolíneas", "temático", "EEUU"),
    ("DRIV", "Vehículos eléctricos y autónomos", "temático", "Global"),
    ("ESPO", "Videojuegos y eSports", "temático", "Global"),
    ("BLOK", "Blockchain", "temático", "Global"),
    ("PAVE", "Infraestructura EEUU", "temático", "EEUU"),
    ("VNQ", "REITs EEUU", "temático", "EEUU"),
    # --- Commodities / refugio ---
    ("GLD", "Oro físico", "materia prima", "Global"),
    ("IAU", "Oro (iShares)", "materia prima", "Global"),
    ("SLV", "Plata", "materia prima", "Global"),
    ("DBC", "Cesta de materias primas", "materia prima", "Global"),
    ("PDBC", "Materias primas (sin K-1)", "materia prima", "Global"),
    ("USO", "Petróleo", "materia prima", "Global"),
    ("UNG", "Gas natural", "materia prima", "Global"),
    # --- Fixed income ---
    ("AGG", "Renta fija agregada EEUU", "renta fija", "EEUU"),
    ("BND", "Bonos totales (Vanguard)", "renta fija", "EEUU"),
    ("TLT", "Treasury largo plazo (20+a)", "renta fija", "EEUU"),
    ("IEF", "Treasury 7-10 años", "renta fija", "EEUU"),
    ("SHY", "Treasury 1-3 años", "renta fija", "EEUU"),
    ("LQD", "Bonos corporativos grado inversión", "renta fija", "EEUU"),
    ("HYG", "Bonos high yield", "renta fija", "EEUU"),
    ("TIP", "Bonos ligados a inflación", "renta fija", "EEUU"),
    ("EMB", "Deuda emergente", "renta fija", "Emergentes"),
    ("BNDX", "Bonos internacionales", "renta fija", "Global"),
]


def universe_tickers() -> list[str]:
    return [row[0] for row in UNIVERSE]


def universe_meta() -> dict[str, dict]:
    return {row[0]: {"name": row[1], "cat": row[2], "region": row[3]} for row in UNIVERSE}
