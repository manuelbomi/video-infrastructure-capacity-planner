"""Loads each examples/*.yaml scenario, runs the full calculation pipeline,
and asserts the result matches the corresponding hand-verified
examples/*_expected_output.json within a small numeric tolerance.
"""

import json
from pathlib import Path

import pytest
import yaml

from planner.calculator import run_scenario

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _discover_example_pairs():
    pairs = []
    for config_path in sorted(EXAMPLES_DIR.glob("*.yaml")):
        expected_path = config_path.with_name(config_path.stem + "_expected_output.json")
        assert expected_path.exists(), f"Missing expected output file: {expected_path}"
        pairs.append((config_path, expected_path))
    return pairs


EXAMPLE_PAIRS = _discover_example_pairs()


@pytest.mark.parametrize(
    "config_path,expected_path",
    EXAMPLE_PAIRS,
    ids=[p[0].stem for p in EXAMPLE_PAIRS],
)
def test_example_matches_expected_output(config_path, expected_path):
    with open(config_path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    # Only the primary scenario (variants excluded) is checked against the
    # hand-verified expected output.
    primary_config = {k: v for k, v in config.items() if k != "variants"}

    with open(expected_path, "r", encoding="utf-8") as fh:
        expected = json.load(fh)

    result = run_scenario(primary_config)

    assert result.name == expected["name"]
    assert result.camera_count == expected["camera_count"]
    assert result.per_camera_bitrate_mbps == pytest.approx(expected["per_camera_bitrate_mbps"], rel=1e-6)
    assert result.total_bandwidth_mbps == pytest.approx(expected["total_bandwidth_mbps"], rel=1e-6)
    assert result.storage_tb == pytest.approx(expected["storage_tb"], rel=1e-6)
    assert result.retention_days == expected["retention_days"]
    assert result.gpu_count == expected["gpu_count"]
    assert result.recommended_architecture == expected["recommended_architecture"]


def test_at_least_two_examples_discovered():
    # Guards against an empty examples/ dir silently skipping all coverage.
    assert len(EXAMPLE_PAIRS) >= 2
