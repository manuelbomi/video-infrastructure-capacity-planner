"""Unit tests for src/planner/calculator.py, against hand-computed expected values.

Every expected value below is computed by hand in the comment above it so
the test itself can be audited without re-deriving the arithmetic from the
implementation.
"""

import math

import pytest

from planner.calculator import (
    estimate_gpu_count,
    estimate_per_camera_bitrate_mbps,
    estimate_storage_tb,
    estimate_total_bandwidth_mbps,
    recommend_architecture,
    run_scenario,
)

# ---------------------------------------------------------------------------
# estimate_per_camera_bitrate_mbps
# ---------------------------------------------------------------------------


def test_bitrate_1080p_h264_medium():
    # pixel_count = 1920 * 1080 = 2,073,600
    # bits_per_second = 2,073,600 * 15 fps * 0.10 (h264) * 1.0 (medium)
    #                 = 2,073,600 * 15 = 31,104,000
    #                 * 0.10           = 3,110,400
    #                 * 1.0            = 3,110,400
    # mbps = 3,110,400 / 1,000,000 = 3.1104
    result = estimate_per_camera_bitrate_mbps("1080p", 15, "h264", "medium")
    assert result == pytest.approx(3.1104, rel=1e-9)


def test_bitrate_1080p_h265_is_half_of_h264():
    # H.265 bits-per-pixel factor (0.05) is exactly half of H.264's (0.10),
    # so at identical resolution/fps/quality the estimated bitrate must be
    # exactly half: 3.1104 / 2 = 1.5552
    h264 = estimate_per_camera_bitrate_mbps("1080p", 15, "h264", "medium")
    h265 = estimate_per_camera_bitrate_mbps("1080p", 15, "h265", "medium")
    assert h265 == pytest.approx(1.5552, rel=1e-9)
    assert h265 == pytest.approx(h264 / 2, rel=1e-9)


def test_bitrate_720p_h264_high_quality():
    # pixel_count = 1280 * 720 = 921,600
    # bits_per_second = 921,600 * 30 fps * 0.10 (h264) * 1.6 (high)
    #                 = 921,600 * 30 = 27,648,000
    #                 * 0.10          = 2,764,800
    #                 * 1.6           = 4,423,680
    # mbps = 4,423,680 / 1,000,000 = 4.42368
    result = estimate_per_camera_bitrate_mbps("720p", 30, "h264", "high")
    assert result == pytest.approx(4.42368, rel=1e-9)


def test_bitrate_low_quality_multiplier():
    # low-quality multiplier is 0.6, applied on top of the medium baseline:
    # 3.1104 * 0.6 = 1.86624
    result = estimate_per_camera_bitrate_mbps("1080p", 15, "h264", "low")
    assert result == pytest.approx(1.86624, rel=1e-9)


def test_bitrate_resolution_string_and_tuple_equivalent_to_preset():
    preset = estimate_per_camera_bitrate_mbps("1080p", 15, "h264", "medium")
    wxh_string = estimate_per_camera_bitrate_mbps("1920x1080", 15, "h264", "medium")
    tuple_res = estimate_per_camera_bitrate_mbps((1920, 1080), 15, "h264", "medium")
    assert preset == pytest.approx(wxh_string)
    assert preset == pytest.approx(tuple_res)


def test_bitrate_unknown_codec_raises():
    with pytest.raises(ValueError):
        estimate_per_camera_bitrate_mbps("1080p", 15, "vp9-not-supported", "medium")


def test_bitrate_unknown_resolution_raises():
    with pytest.raises(ValueError):
        estimate_per_camera_bitrate_mbps("not-a-resolution", 15, "h264", "medium")


def test_bitrate_zero_fps_raises():
    with pytest.raises(ValueError):
        estimate_per_camera_bitrate_mbps("1080p", 0, "h264", "medium")


# ---------------------------------------------------------------------------
# estimate_total_bandwidth_mbps
# ---------------------------------------------------------------------------


def test_total_bandwidth_500_cameras():
    # 500 cameras * 1.5552 Mbps/camera = 777.6 Mbps
    result = estimate_total_bandwidth_mbps(500, 1.5552)
    assert result == pytest.approx(777.6, rel=1e-9)


def test_total_bandwidth_zero_cameras():
    assert estimate_total_bandwidth_mbps(0, 3.11) == 0


def test_total_bandwidth_negative_camera_count_raises():
    with pytest.raises(ValueError):
        estimate_total_bandwidth_mbps(-1, 3.11)


# ---------------------------------------------------------------------------
# estimate_storage_tb
# ---------------------------------------------------------------------------


def test_storage_777_6_mbps_30_days():
    # bytes_per_second = 777.6e6 / 8 = 97,200,000
    # total_bytes = 97,200,000 * 86,400 * 30
    #             = 8,398,080,000,000 (bytes/day) * 30
    #             = 251,942,400,000,000 bytes
    # storage_tb = 251,942,400,000,000 / 1e12 = 251.9424
    result = estimate_storage_tb(777.6, 30)
    assert result == pytest.approx(251.9424, rel=1e-9)


def test_storage_doubling_retention_doubles_storage():
    thirty_days = estimate_storage_tb(100.0, 30)
    sixty_days = estimate_storage_tb(100.0, 60)
    assert sixty_days == pytest.approx(2 * thirty_days, rel=1e-9)


def test_storage_zero_bandwidth_is_zero():
    assert estimate_storage_tb(0, 30) == 0


def test_storage_negative_retention_raises():
    with pytest.raises(ValueError):
        estimate_storage_tb(100.0, -1)


# ---------------------------------------------------------------------------
# estimate_gpu_count
# ---------------------------------------------------------------------------


def test_gpu_count_100_streams_yolov8m_10fps():
    # base_streams_per_gpu for person_detection_yolov8m = 8 at reference_fps 30
    # effective_streams_per_gpu = 8 * (30 / 10) = 24
    # gpu_count = ceil(100 / 24) = ceil(4.1666...) = 5
    result = estimate_gpu_count(100, "person_detection_yolov8m", 10)
    assert result == 5


def test_gpu_count_exact_division_no_rounding_up_needed():
    # base_streams_per_gpu for person_detection_yolov8m = 8 at reference_fps 30
    # target_fps = 30 (== reference) -> effective_streams_per_gpu = 8
    # gpu_count = ceil(48 / 8) = 6 (exact)
    result = estimate_gpu_count(48, "person_detection_yolov8m", 30)
    assert result == 6


def test_gpu_count_zero_streams_needs_zero_gpus():
    assert estimate_gpu_count(0, "person_detection_yolov8m", 10) == 0


def test_gpu_count_unknown_model_raises():
    with pytest.raises(ValueError):
        estimate_gpu_count(10, "not-a-real-model", 10)


def test_gpu_count_uses_math_ceil_semantics():
    # Sanity check that our hand math above agrees with math.ceil directly.
    base = 8
    reference_fps = 30
    target_fps = 10
    effective = base * (reference_fps / target_fps)
    assert math.ceil(100 / effective) == estimate_gpu_count(100, "person_detection_yolov8m", 10)


# ---------------------------------------------------------------------------
# recommend_architecture
# ---------------------------------------------------------------------------


def test_recommend_edge_when_bandwidth_exceeds_wan():
    # 600 Mbps required > 500 Mbps available -> must push inference to the edge
    result = recommend_architecture(600, 500, camera_count=200, latency_sensitive=False)
    assert result == "edge"


def test_recommend_hybrid_when_latency_sensitive_even_with_spare_bandwidth():
    # Only 10 Mbps of 500 Mbps used, but latency-sensitive workloads still
    # need local/edge processing to avoid round-trip delay.
    result = recommend_architecture(10, 500, camera_count=5, latency_sensitive=True)
    assert result == "hybrid"


def test_recommend_hybrid_when_bandwidth_over_safety_margin():
    # 400 / 500 = 80%, which is above the 70% safety margin, but does not
    # exceed available capacity outright.
    result = recommend_architecture(400, 500, camera_count=100, latency_sensitive=False)
    assert result == "hybrid"


def test_recommend_cloud_when_ample_headroom_and_not_latency_sensitive():
    # 100 / 500 = 20%, well under the 70% safety margin.
    result = recommend_architecture(100, 500, camera_count=50, latency_sensitive=False)
    assert result == "cloud"


def test_recommend_invalid_available_wan_raises():
    with pytest.raises(ValueError):
        recommend_architecture(100, 0, camera_count=10, latency_sensitive=False)


# ---------------------------------------------------------------------------
# run_scenario (end-to-end orchestration)
# ---------------------------------------------------------------------------


def test_run_scenario_end_to_end():
    config = {
        "name": "Unit-test scenario",
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
    result = run_scenario(config)
    assert result.per_camera_bitrate_mbps == pytest.approx(1.5552, rel=1e-9)
    assert result.total_bandwidth_mbps == pytest.approx(777.6, rel=1e-9)
    assert result.storage_tb == pytest.approx(251.9424, rel=1e-9)
    assert result.gpu_count == 5
    assert result.recommended_architecture == "edge"
