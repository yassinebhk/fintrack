"""Build QuickChart image URLs (Chart.js rendered to PNG, no local deps).

QuickChart renders a Chart.js config passed as a URL param. We use it to
send portfolio / asset charts through Telegram via sendPhoto.
"""

import json
import urllib.parse


QUICKCHART_BASE = "https://quickchart.io/chart"


def _chart_url(config: dict, width: int = 640, height: int = 360) -> str:
    c = urllib.parse.quote(json.dumps(config, separators=(",", ":")))
    return f"{QUICKCHART_BASE}?w={width}&h={height}&bkg=%230a0e17&c={c}"


def line_chart(title: str, labels: list[str], values: list[float], color: str = "#00d4aa") -> str:
    # Thin out labels for readability
    n = len(labels)
    step = max(1, n // 8)
    display_labels = [lbl if i % step == 0 else "" for i, lbl in enumerate(labels)]

    config = {
        "type": "line",
        "data": {
            "labels": display_labels,
            "datasets": [{
                "label": title,
                "data": values,
                "borderColor": color,
                "backgroundColor": "rgba(0,212,170,0.15)",
                "fill": True,
                "pointRadius": 0,
                "borderWidth": 2,
                "tension": 0.3,
            }],
        },
        "options": {
            "plugins": {
                "title": {"display": True, "text": title, "color": "#f8fafc"},
                "legend": {"display": False},
            },
            "scales": {
                "x": {"ticks": {"color": "#94a3b8", "maxRotation": 0}, "grid": {"color": "rgba(255,255,255,0.05)"}},
                "y": {"ticks": {"color": "#94a3b8"}, "grid": {"color": "rgba(255,255,255,0.08)"}},
            },
        },
    }
    return _chart_url(config)


def doughnut_chart(title: str, labels: list[str], values: list[float]) -> str:
    colors = ["#00d4aa", "#6366f1", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#ef4444", "#3b82f6"]
    config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [{"data": values, "backgroundColor": colors[: len(labels)]}],
        },
        "options": {
            "plugins": {
                "title": {"display": True, "text": title, "color": "#f8fafc"},
                "legend": {"position": "right", "labels": {"color": "#f8fafc"}},
            },
        },
    }
    return _chart_url(config)
