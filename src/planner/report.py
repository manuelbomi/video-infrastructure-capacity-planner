"""HTML report generation for capacity-planning scenarios.

Renders a professional-looking, self-contained HTML report (via Jinja2)
summarizing the inputs and computed outputs for one or more scenarios,
including a matplotlib bar chart (embedded as a base64 PNG, so the report is
a single portable file) comparing bandwidth, storage, and GPU requirements
across scenarios.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless rendering, no display server required
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .calculator import ScenarioResult

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _build_comparison_chart_png_base64(results: list[ScenarioResult]) -> str:
    """Build a grouped bar chart comparing bandwidth/storage/GPU across scenarios.

    Each metric is normalized to its own subplot (they have very different
    units/scales -- Mbps, TB, and GPU count -- so a single shared axis would
    make the smaller metrics unreadable).

    Returns the chart as a base64-encoded PNG string, so the caller can embed
    it directly into the HTML report with no separate image file.
    """
    names = [r.name for r in results]
    bandwidth = [r.total_bandwidth_mbps for r in results]
    storage = [r.storage_tb for r in results]
    gpus = [r.gpu_count for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    metrics = [
        ("Bandwidth (Mbps)", bandwidth, "#2b6cb0"),
        ("Storage (TB)", storage, "#2f855a"),
        ("GPU count", gpus, "#c05621"),
    ]
    for ax, (title, values, color) in zip(axes, metrics):
        ax.bar(names, values, color=color)
        ax.set_title(title, fontsize=11)
        ax.tick_params(axis="x", rotation=30, labelsize=8)
        for i, v in enumerate(values):
            ax.text(i, v, f"{v:,.1f}" if isinstance(v, float) else str(v),
                     ha="center", va="bottom", fontsize=8)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _get_template():
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    return env.get_template("report_template.html")


def render_report_html(
    results: list[ScenarioResult],
    generated_at: datetime | None = None,
) -> str:
    """Render the full HTML report (as a string) for one or more scenarios.

    The first scenario in `results` is treated as the "primary" scenario for
    the summary headline; all scenarios (including a single one) are shown
    in the comparison table and chart.
    """
    if not results:
        raise ValueError("results must contain at least one ScenarioResult")

    chart_png_base64 = _build_comparison_chart_png_base64(results) if len(results) >= 1 else None

    template = _get_template()
    return template.render(
        primary=results[0],
        results=results,
        chart_png_base64=chart_png_base64,
        generated_at=(generated_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC"),
    )


def write_report(
    results: list[ScenarioResult],
    output_path: str | Path,
    generated_at: datetime | None = None,
) -> Path:
    """Render the report and write it to `output_path`. Returns the Path written."""
    html = render_report_html(results, generated_at=generated_at)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
