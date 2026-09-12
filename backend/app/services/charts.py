"""Build QuickChart image URLs (Chart.js rendered to PNG, no local deps).

QuickChart renders a Chart.js config passed as a URL param. We use it for the
asset-analysis charts, the opportunity cards and the Telegram photos.

Styled to match the app's warm light theme — cream background, dark-blue accent,
terracotta for negatives — so the images sit naturally inside the UI instead of
clashing on a near-black canvas. Rendered at 2x for crisp, retina-quality PNGs.
"""

import json
import urllib.parse


QUICKCHART_BASE = "https://quickchart.io/chart"

# --- App theme (matches styles.css and the interactive TradingView/Chart.js charts) ---
BG = "#F5F1E9"        # warm cream background
INK = "#2B2822"       # titles / strong text
MUTED = "#8A8275"     # axis ticks
GRID = "rgba(43,40,34,0.08)"
ACCENT = "#2C4A6E"    # dark blue (up / primary)
NEGATIVE = "#C6473C"  # terracotta (down)
POSITIVE = "#4A9B8E"  # muted teal-green


def _hex_alpha(color: str, alpha_hex: str = "1f") -> str:
    """Translucent fill derived FROM the line color (fixes the old bug where the
    fill was a fixed teal regardless of the line). Falls back to a soft accent tint
    when the color isn't a plain #RRGGBB hex."""
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        return color + alpha_hex
    return "rgba(44,74,110,0.12)"


def _chart_url(config: dict, width: int = 720, height: int = 380) -> str:
    # v=4: QuickChart defaults to Chart.js v2, where our modern config (axis
    # `scales.*.title`, `ticks.color`, `borderRadius`) is silently ignored. Pin v4.
    c = urllib.parse.quote(json.dumps(config, separators=(",", ":")))
    return f"{QUICKCHART_BASE}?v=4&w={width}&h={height}&devicePixelRatio=2&bkg={urllib.parse.quote(BG)}&c={c}"


def _title(text) -> dict:
    return {"display": True, "text": text, "color": INK, "font": {"size": 15, "weight": "600"}}


def _axis_title(text: str) -> dict:
    return {"display": True, "text": text, "color": MUTED, "font": {"size": 12, "weight": "600"}}


def _scales(x_title: str = "Fecha", y_title: str = "") -> dict:
    x = {"ticks": {"color": MUTED, "maxRotation": 0, "font": {"size": 11}}, "grid": {"display": False}}
    y = {"ticks": {"color": MUTED, "font": {"size": 11}}, "grid": {"color": GRID}}
    if x_title:
        x["title"] = _axis_title(x_title)
    if y_title:
        y["title"] = _axis_title(y_title)
    return {"x": x, "y": y}


def _thin(labels: list[str]) -> list[str]:
    """Thin out x labels so they don't overlap."""
    n = len(labels)
    step = max(1, n // 8)
    return [lbl if i % step == 0 else "" for i, lbl in enumerate(labels)]


def line_chart(title: str, labels: list[str], values: list[float], color: str = ACCENT,
               x_title: str = "Fecha", y_title: str = "Precio") -> str:
    config = {
        "type": "line",
        "data": {
            "labels": _thin(labels),
            "datasets": [{
                "label": title,
                "data": values,
                "borderColor": color,
                "backgroundColor": _hex_alpha(color),  # fill now matches the line
                "fill": True,
                "pointRadius": 0,
                "borderWidth": 2,
                "tension": 0.3,
            }],
        },
        "options": {
            "plugins": {"title": _title(title), "legend": {"display": False}},
            "scales": _scales(x_title, y_title),
        },
    }
    return _chart_url(config)


def line_chart_multi(title: str, labels: list[str], datasets: list[dict],
                     width: int = 720, height: int = 380,
                     x_title: str = "Fecha", y_title: str = "") -> str:
    """Multi-series line chart. Each dataset: {name, values, color, dashed?}."""
    cfg_datasets = []
    for ds in datasets:
        d = {
            "label": ds["name"],
            "data": ds["values"],
            "borderColor": ds.get("color", ACCENT),
            "backgroundColor": "rgba(0,0,0,0)",
            "fill": False,
            "pointRadius": 0,
            "borderWidth": ds.get("width", 2),
            "tension": 0.2,
        }
        if ds.get("dashed"):
            d["borderDash"] = [5, 4]
        cfg_datasets.append(d)
    config = {
        "type": "line",
        "data": {"labels": _thin(labels), "datasets": cfg_datasets},
        "options": {
            "plugins": {
                "title": _title(title),
                "legend": {"display": True, "labels": {"color": INK, "font": {"size": 11}, "usePointStyle": True, "boxWidth": 8}},
            },
            "scales": _scales(x_title, y_title),
        },
    }
    return _chart_url(config, width=width, height=height)


def area_chart(title: str, labels: list[str], values: list[float], color: str = NEGATIVE,
               width: int = 720, height: int = 280,
               x_title: str = "Fecha", y_title: str = "") -> str:
    """Single filled area chart — great for drawdown over time."""
    config = {
        "type": "line",
        "data": {"labels": _thin(labels), "datasets": [{
            "label": title, "data": values,
            "borderColor": color, "backgroundColor": _hex_alpha(color, "26"),
            "fill": True, "pointRadius": 0, "borderWidth": 1.5, "tension": 0.2,
        }]},
        "options": {
            "plugins": {"title": _title(title), "legend": {"display": False}},
            "scales": _scales(x_title, y_title),
        },
    }
    return _chart_url(config, width=width, height=height)


def bar_chart(title: str, labels: list[str], values: list[float], color: str = ACCENT,
              width: int = 720, height: int = 280,
              x_title: str = "", y_title: str = "Frecuencia") -> str:
    """Bar chart — used for the returns histogram."""
    config = {
        "type": "bar",
        "data": {"labels": labels, "datasets": [{
            "label": title, "data": values, "backgroundColor": color, "borderWidth": 0, "borderRadius": 3,
        }]},
        "options": {
            "plugins": {"title": _title(title), "legend": {"display": False}},
            "scales": _scales(x_title, y_title),
        },
    }
    return _chart_url(config, width=width, height=height)


def portfolio_today_chart(title_lines: list[str], labels: list[str], values: list[float],
                          width: int = 620, height: int | None = None) -> str:
    """Horizontal bar card of today's % move per holding (green up / red down).
    `title_lines` is shown as a multi-line title (total, today, P/L)."""
    colors = [POSITIVE if (v or 0) >= 0 else NEGATIVE for v in values]
    height = height or max(240, 40 * len(labels) + 110)
    config = {
        "type": "bar",
        "data": {"labels": labels, "datasets": [{
            "data": values, "backgroundColor": colors, "borderWidth": 0, "borderRadius": 3,
        }]},
        "options": {
            "indexAxis": "y",
            "plugins": {
                "title": {"display": True, "text": title_lines, "color": INK, "font": {"size": 15, "weight": "600"}},
                "legend": {"display": False},
            },
            "scales": {
                "x": {"ticks": {"color": MUTED}, "grid": {"color": GRID},
                      "title": {"display": True, "text": "% hoy", "color": MUTED}},
                "y": {"ticks": {"color": INK, "font": {"size": 11}}, "grid": {"display": False}},
            },
        },
    }
    return _chart_url(config, width=width, height=height)


def doughnut_chart(title: str, labels: list[str], values: list[float]) -> str:
    colors = ["#2C4A6E", "#4A9B8E", "#C99A3E", "#C6473C", "#6366f1", "#8b5cf6", "#D65B8A", "#5B8FB0"]
    config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{"data": values, "backgroundColor": colors[: len(labels)],
                          "borderColor": BG, "borderWidth": 2}],
        },
        "options": {
            "plugins": {
                "title": _title(title),
                "legend": {"position": "right", "labels": {"color": INK, "font": {"size": 11}, "usePointStyle": True, "boxWidth": 8}},
            },
        },
    }
    return _chart_url(config)
