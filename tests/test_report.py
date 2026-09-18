"""Tests that report.py produces valid HTML containing the key computed figures."""

from planner.calculator import run_scenario
from planner.report import render_report_html, write_report


def _sample_result():
    config = {
        "name": "Report-test scenario",
        "camera_count": 500,
        "resolution": "1080p",
        "fps": 15,
        "codec": "h265",
        "quality_profile": "medium",
        "retention_days": 30,
        "concurrent_ai_streams": 100,
        "ai_model": "person_detection_yolov8m",
        "target_ai_fps": 10,
        "available_wan_mbps": 500,
        "latency_sensitive": False,
    }
    return run_scenario(config)


def test_render_report_html_contains_key_figures():
    result = _sample_result()
    html = render_report_html([result])

    assert html.startswith("<!DOCTYPE html>") or "<!DOCTYPE html>" in html
    assert "<html" in html

    # Bandwidth (777.60 Mbps), storage (251.94 TB), GPU count (5), and the
    # recommendation ("edge") must all appear in the rendered report.
    assert "777.6" in html
    assert "251.94" in html
    assert ">5<" in html or "5</div>" in html  # gpu count rendered as a metric
    assert "edge" in html.lower()
    assert result.name in html


def test_render_report_html_embeds_chart_image():
    result = _sample_result()
    html = render_report_html([result])
    assert "data:image/png;base64," in html


def test_render_report_html_multi_scenario_comparison_table():
    primary = _sample_result()
    variant_config = dict(primary.inputs)
    variant_config["name"] = "Variant with H.264"
    variant_config["codec"] = "h264"
    variant = run_scenario(variant_config)

    html = render_report_html([primary, variant])
    assert "Scenario comparison" in html
    assert primary.name in html
    assert variant.name in html


def test_write_report_creates_file_with_content(tmp_path):
    result = _sample_result()
    out_path = tmp_path / "nested" / "report.html"
    written = write_report([result], out_path)

    assert written == out_path
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "251.94" in content
