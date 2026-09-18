"""Tests for the additive JSON API (POST /api/plan) in planner.webform.

POST /api/plan is used by the React/TypeScript frontend (frontend/) instead
of the HTML report route. It must call the same run_scenario() pipeline as
the CLI and the HTML form, so the expected numbers here are the exact same
hand-verified values already used in tests/test_calculator.py and
tests/test_examples.py for the "500 cameras across 20 facilities" scenario.
"""

import pytest
from fastapi.testclient import TestClient

from planner.webform import app

client = TestClient(app)

_500_CAMERAS_PAYLOAD = {
    "name": "500 cameras across 20 facilities",
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


def test_api_plan_matches_hand_verified_500_camera_scenario():
    # Same expected values as examples/500_cameras_20_sites_expected_output.json
    # and tests/test_calculator.py::test_run_scenario_end_to_end.
    response = client.post("/api/plan", json=_500_CAMERAS_PAYLOAD)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "500 cameras across 20 facilities"
    assert data["camera_count"] == 500
    assert data["per_camera_bitrate_mbps"] == pytest.approx(1.5552, rel=1e-6)
    assert data["total_bandwidth_mbps"] == pytest.approx(777.6, rel=1e-6)
    assert data["storage_tb"] == pytest.approx(251.9424, rel=1e-6)
    assert data["retention_days"] == 30
    assert data["gpu_count"] == 5
    assert data["recommended_architecture"] == "edge"


def test_api_plan_h264_doubles_bandwidth_and_storage_vs_h265():
    # Same "what-if" relationship documented in the README worked example:
    # H.264 needs twice the bits-per-pixel of H.265 at the same settings, so
    # bandwidth and storage should both double relative to the h265 baseline.
    h265 = client.post("/api/plan", json=_500_CAMERAS_PAYLOAD).json()
    h264_payload = dict(_500_CAMERAS_PAYLOAD, codec="h264")
    h264 = client.post("/api/plan", json=h264_payload).json()

    assert h264["total_bandwidth_mbps"] == pytest.approx(2 * h265["total_bandwidth_mbps"], rel=1e-6)
    assert h264["storage_tb"] == pytest.approx(2 * h265["storage_tb"], rel=1e-6)


def test_api_plan_rejects_missing_required_field():
    bad_payload = dict(_500_CAMERAS_PAYLOAD)
    del bad_payload["camera_count"]
    response = client.post("/api/plan", json=bad_payload)
    assert response.status_code == 422


def test_api_plan_rejects_non_positive_camera_count():
    bad_payload = dict(_500_CAMERAS_PAYLOAD, camera_count=0)
    response = client.post("/api/plan", json=bad_payload)
    assert response.status_code == 422
