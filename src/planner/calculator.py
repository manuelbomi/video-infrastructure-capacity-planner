"""Core capacity-planning calculations.

Every function in this module documents the exact formula it uses and the
reasoning behind it. Two categories of numeric assumption are used
throughout, and both are called out explicitly wherever they appear:

1. Codec efficiency factors (bits-per-pixel) used for bitrate estimation.
   These are example, industry-typical rules of thumb, NOT measurements from
   a specific encoder. Real encoders vary a lot with scene complexity,
   motion, encoder tuning (rate control mode, GOP length, profile/level),
   and vendor implementation quality. Validate against real encoder
   benchmarks (or, ideally, a short on-site pilot with the actual cameras)
   before quoting a customer.

2. GPU inference throughput-per-model assumptions, loaded from
   ``data/gpu_benchmark_assumptions.yaml``. These are illustrative planning
   numbers, NOT vendor-verified benchmarks. Validate against real
   measurements on the actual target GPU/model/precision combination before
   quoting a customer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Resolution handling
# ---------------------------------------------------------------------------

# Common IP-camera resolution presets, mapped to (width, height) in pixels.
# These are standard/well-known pixel dimensions, not an assumption we are
# making up -- they are included purely for operator convenience so a config
# file can say "1080p" instead of "1920x1080".
RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "480p": (720, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4mp": (2688, 1520),
    "5mp": (2592, 1944),
    "4k": (3840, 2160),
    "8mp": (3840, 2160),
    "12mp": (4000, 3000),
}


def _resolve_resolution(resolution: Any) -> tuple[int, int]:
    """Normalize a resolution input into an (width, height) pixel tuple.

    Accepts:
      - a preset name string, e.g. "1080p", "4K" (case-insensitive)
      - a "WxH" string, e.g. "1920x1080"
      - a (width, height) tuple/list of ints
    """
    if isinstance(resolution, (tuple, list)) and len(resolution) == 2:
        width, height = resolution
        return int(width), int(height)

    if isinstance(resolution, str):
        key = resolution.strip().lower()
        if key in RESOLUTION_PRESETS:
            return RESOLUTION_PRESETS[key]
        if "x" in key:
            width_str, height_str = key.split("x", 1)
            return int(width_str), int(height_str)

    raise ValueError(
        f"Unrecognized resolution: {resolution!r}. Use a preset name "
        f"({sorted(RESOLUTION_PRESETS)}), a 'WxH' string, or a (width, height) tuple."
    )


# ---------------------------------------------------------------------------
# Bitrate estimation
# ---------------------------------------------------------------------------

# Example, industry-typical bits-per-pixel factors used to approximate
# average (not peak) encoded bitrate for a "typical" indoor/outdoor
# surveillance scene with moderate motion. This is the classic
#
#     bitrate ~= pixel_count * fps * bits_per_pixel
#
# rule of thumb used across the video-surveillance industry for rough
# bandwidth planning. It intentionally ignores scene-specific variable
# bitrate (VBR) swings -- a scene with heavy motion (e.g. a busy street)
# will encode meaningfully higher than a mostly-static scene (e.g. an empty
# hallway) at the same nominal settings.
#
# H.265 (HEVC) is assumed here to need roughly HALF the bits-per-pixel of
# H.264 (AVC) to hit similar perceived visual quality. This "H.265 ~= 50% of
# H.264" figure is a widely cited industry rule of thumb for modern HEVC
# encoders, not a guarantee for any specific camera/encoder firmware --
# actual savings commonly range from ~30% to ~50% depending on the encoder.
#
# THESE ARE EXAMPLE ASSUMPTIONS. Validate against real encoder benchmarks
# (ideally a short pilot with the actual camera models) before quoting a
# customer.
CODEC_BITS_PER_PIXEL: dict[str, float] = {
    "h264": 0.10,   # example: typical "good quality" H.264 baseline
    "h265": 0.05,   # example: ~50% of H.264 for similar visual quality
    "hevc": 0.05,   # alias for h265
    "mjpeg": 0.50,  # example: intra-frame-only codec, much less efficient
}

# Quality-profile multipliers applied on top of the codec baseline above, to
# represent typical camera "quality"/compression-level presets (these do NOT
# change resolution or frame rate, only the target encoded quality level).
QUALITY_PROFILE_MULTIPLIERS: dict[str, float] = {
    "low": 0.6,
    "medium": 1.0,
    "high": 1.6,
}


def estimate_per_camera_bitrate_mbps(
    resolution: Any,
    fps: float,
    codec: str,
    quality_profile: str = "medium",
) -> float:
    """Estimate the average encoded bitrate of a single camera stream, in Mbps.

    Formula
    -------
        pixel_count      = width * height
        bits_per_second   = pixel_count * fps * bits_per_pixel * quality_multiplier
        bitrate_mbps      = bits_per_second / 1_000_000

    Reasoning
    ---------
    This is the standard "pixels x frames x bits-per-pixel" estimation
    approach used throughout the video-surveillance and video-conferencing
    industries for first-pass bandwidth planning. It scales linearly with
    both spatial resolution (more pixels to encode per frame) and temporal
    resolution (more frames per second to encode), which matches how video
    encoders actually behave at a fixed quality target.

    The `bits_per_pixel` factor is where codec efficiency comes in: H.265 is
    assumed to need about half as many bits per pixel as H.264 to reach
    similar perceived visual quality (see CODEC_BITS_PER_PIXEL above), which
    directly halves the estimated bitrate (and therefore the network
    bandwidth and storage footprint) for an otherwise-identical stream.

    IMPORTANT: This produces an AVERAGE bitrate estimate for a "typical"
    scene. Real cameras use variable bitrate (VBR) encoding, so a scene with
    a lot of motion will use notably more bandwidth than a static scene at
    the same settings. Treat this as a planning estimate, not a guarantee,
    and validate against real encoder output before quoting a customer.

    Parameters
    ----------
    resolution : preset name ("1080p", "4K", ...), "WxH" string, or (w, h) tuple
    fps : frames per second the camera streams at
    codec : "h264", "h265"/"hevc", or "mjpeg" (case-insensitive)
    quality_profile : "low", "medium" (default), or "high"

    Returns
    -------
    float : estimated average bitrate in megabits per second (Mbps)
    """
    if fps <= 0:
        raise ValueError("fps must be positive")

    width, height = _resolve_resolution(resolution)
    pixel_count = width * height

    codec_key = codec.strip().lower()
    if codec_key not in CODEC_BITS_PER_PIXEL:
        raise ValueError(
            f"Unknown codec {codec!r}. Supported: {sorted(CODEC_BITS_PER_PIXEL)}"
        )
    bits_per_pixel = CODEC_BITS_PER_PIXEL[codec_key]

    quality_key = quality_profile.strip().lower()
    if quality_key not in QUALITY_PROFILE_MULTIPLIERS:
        raise ValueError(
            f"Unknown quality_profile {quality_profile!r}. "
            f"Supported: {sorted(QUALITY_PROFILE_MULTIPLIERS)}"
        )
    quality_multiplier = QUALITY_PROFILE_MULTIPLIERS[quality_key]

    bits_per_second = pixel_count * fps * bits_per_pixel * quality_multiplier
    return bits_per_second / 1_000_000.0


def estimate_total_bandwidth_mbps(camera_count: int, per_camera_bitrate_mbps: float) -> float:
    """Estimate aggregate network bandwidth required for all cameras, in Mbps.

    Formula
    -------
        total_bandwidth_mbps = camera_count * per_camera_bitrate_mbps

    Reasoning
    ---------
    This assumes every camera stream is sent, uncontended, at its estimated
    average bitrate simultaneously (the standard "worst case, all streams
    active" planning assumption for network sizing). It does not add
    protocol/framing overhead (RTP/RTSP headers, retransmits, etc.) or any
    other traffic sharing the same link -- add a safety margin (commonly
    20-30%) on top of this number when sizing an actual link.
    """
    if camera_count < 0:
        raise ValueError("camera_count must be non-negative")
    return camera_count * per_camera_bitrate_mbps


def estimate_storage_tb(total_bandwidth_mbps: float, retention_days: float) -> float:
    """Estimate raw video storage required to retain all streams, in TB.

    Formula
    -------
        bytes_per_second = (total_bandwidth_mbps * 1_000_000) / 8
        total_bytes      = bytes_per_second * 86_400 * retention_days
        storage_tb        = total_bytes / 1_000_000_000_000     # decimal TB

    Reasoning
    ---------
    Storage is simply "bandwidth integrated over time": if the system
    ingests `total_bandwidth_mbps` megabits every second, continuously, then
    over `retention_days` days it must persist that many bits, converted to
    bytes (divide by 8) and then to decimal terabytes (divide by 10^12,
    matching how storage vendors typically size and sell capacity).

    Retention days is very often the single biggest lever on total storage
    cost: doubling retention from, say, 30 to 60 days exactly doubles the
    storage requirement, whereas most other levers (resolution, fps, codec)
    only produce sub-linear or one-time changes once decided. This is why
    retention policy is usually the first thing to interrogate on a
    discovery call, right after "how many cameras."

    This estimate assumes constant bitrate equal to the average estimated
    bitrate and does not include any RAID/erasure-coding overhead, database
    /metadata overhead, or thumbnail/proxy storage -- add a margin (commonly
    10-20%) for those in a real storage quote.
    """
    if total_bandwidth_mbps < 0:
        raise ValueError("total_bandwidth_mbps must be non-negative")
    if retention_days < 0:
        raise ValueError("retention_days must be non-negative")

    bytes_per_second = (total_bandwidth_mbps * 1_000_000.0) / 8.0
    total_bytes = bytes_per_second * 86_400.0 * retention_days
    return total_bytes / 1_000_000_000_000.0


# ---------------------------------------------------------------------------
# GPU sizing
# ---------------------------------------------------------------------------

_DEFAULT_GPU_BENCHMARK_PATH = Path(__file__).parent / "data" / "gpu_benchmark_assumptions.yaml"


def load_gpu_benchmark_table(path: str | Path | None = None) -> dict[str, Any]:
    """Load the (illustrative, example) GPU throughput assumption table.

    The table is a plain YAML/dict structure of the form::

        reference_fps: 30
        streams_per_gpu:
          model_name: <int streams the reference GPU can handle at reference_fps>

    It is intentionally kept out of Python source so it can be swapped for
    real, validated benchmark numbers without touching any calculation
    code -- see the module docstring for why these numbers must not be
    presented to a customer as verified hardware benchmarks.
    """
    table_path = Path(path) if path else _DEFAULT_GPU_BENCHMARK_PATH
    with open(table_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if "reference_fps" not in data or "streams_per_gpu" not in data:
        raise ValueError(
            f"GPU benchmark table at {table_path} must define "
            "'reference_fps' and 'streams_per_gpu'"
        )
    return data


def estimate_gpu_count(
    concurrent_ai_streams: int,
    model_name: str,
    target_fps: float,
    throughput_table: dict[str, Any] | None = None,
) -> int:
    """Estimate the number of inference GPUs required for a given workload.

    Formula
    -------
        base_streams_per_gpu = throughput_table['streams_per_gpu'][model_name]
        reference_fps         = throughput_table['reference_fps']
        effective_streams_per_gpu = base_streams_per_gpu * (reference_fps / target_fps)
        gpu_count = ceil(concurrent_ai_streams / effective_streams_per_gpu)

    Reasoning
    ---------
    `throughput_table` gives, per model, an EXAMPLE number of concurrent
    video streams a single reference GPU is assumed able to process at a
    reference inference frame rate (`reference_fps`, default 30 fps in the
    bundled table). If a deployment only needs a lower inference frame rate
    (e.g. 5 fps is often plenty for "did a person enter this zone"-style
    analytics), a single GPU can typically keep up with proportionally more
    streams -- this function models that as a simple linear scaling factor.
    This is a simplification: real throughput scaling is affected by
    batching efficiency, memory bandwidth, and fixed per-stream overhead,
    and is rarely perfectly linear in practice.

    THESE THROUGHPUT NUMBERS ARE ILLUSTRATIVE EXAMPLES, NOT VERIFIED
    BENCHMARKS. They must be validated against real measurements on the
    exact GPU SKU, model, precision (fp16/int8/TensorRT engine, etc.), and
    input resolution that will actually be deployed before this number is
    used to quote a customer. Presenting an unvalidated planning guess as a
    hardware fact is a common and avoidable source of failed deployments.

    Parameters
    ----------
    concurrent_ai_streams : number of camera streams that need live AI inference
    model_name : key into throughput_table['streams_per_gpu']
    target_fps : inference frame rate actually required for this deployment
    throughput_table : optional override; defaults to the bundled example table

    Returns
    -------
    int : minimum number of GPUs required (rounded up, since GPUs are discrete)
    """
    if concurrent_ai_streams < 0:
        raise ValueError("concurrent_ai_streams must be non-negative")
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")
    if concurrent_ai_streams == 0:
        return 0

    table = throughput_table if throughput_table is not None else load_gpu_benchmark_table()
    streams_per_gpu_table = table["streams_per_gpu"]
    reference_fps = table["reference_fps"]

    model_key = model_name.strip().lower()
    if model_key not in streams_per_gpu_table:
        raise ValueError(
            f"Unknown model {model_name!r}. Supported: {sorted(streams_per_gpu_table)}"
        )
    base_streams_per_gpu = streams_per_gpu_table[model_key]

    effective_streams_per_gpu = base_streams_per_gpu * (reference_fps / target_fps)
    if effective_streams_per_gpu <= 0:
        raise ValueError("Computed effective_streams_per_gpu must be positive")

    return math.ceil(concurrent_ai_streams / effective_streams_per_gpu)


# ---------------------------------------------------------------------------
# Architecture recommendation
# ---------------------------------------------------------------------------

# Safety-margin fraction of available WAN capacity below which we consider a
# link "comfortably" able to carry raw video centrally, leaving headroom for
# other traffic (VoIP, business applications, control-plane chatter, etc.).
# This is an example planning margin, not a hard network-engineering rule.
WAN_SAFETY_MARGIN = 0.7


def recommend_architecture(
    total_bandwidth_mbps: float,
    available_wan_mbps: float,
    camera_count: int,
    latency_sensitive: bool,
) -> str:
    """Recommend "edge", "hybrid", or "cloud" processing architecture.

    Rules (evaluated in order)
    ---------------------------
    1. If the estimated raw-video bandwidth EXCEEDS the available WAN
       capacity, raw video physically cannot all reach the cloud at once.
       -> recommend "edge": run AI inference locally at each site and only
          ship compressed metadata/events (detections, alerts, thumbnails)
          to the cloud, instead of full raw video streams.
    2. Else, if the workload is latency-sensitive (e.g. access-control gate
       triggers, real-time intrusion response), a round trip to a distant
       cloud region adds delay that a local decision loop cannot tolerate,
       even if there is bandwidth to spare.
       -> recommend "hybrid": keep time-critical inference local/at the
          edge, while still sending raw or lightly-processed video to the
          cloud for archival, dashboards, and non-time-critical analytics.
    3. Else, if the estimated bandwidth would consume more than
       WAN_SAFETY_MARGIN (default 70%) of the available WAN capacity, there
       is not enough headroom left for other traffic and normal bandwidth
       variance (VBR spikes, other applications).
       -> recommend "hybrid" for the same reason.
    4. Otherwise there is ample bandwidth and no latency constraint.
       -> recommend "cloud": centralize raw video ingestion, storage, and
          inference in the cloud for simplicity of management.

    Reasoning
    ---------
    The central idea a solution engineer should take away: bandwidth is the
    hard physical constraint (you cannot ship more bits than the link
    supports), while latency sensitivity is a soft-but-critical business
    constraint (a technically-possible round trip may still be too slow for
    the use case). Both push in the same direction -- toward doing more
    processing close to the cameras and only centralizing what actually
    needs to be centralized.
    """
    if available_wan_mbps <= 0:
        raise ValueError("available_wan_mbps must be positive")
    if camera_count < 0:
        raise ValueError("camera_count must be non-negative")

    if total_bandwidth_mbps > available_wan_mbps:
        return "edge"

    if latency_sensitive:
        return "hybrid"

    if total_bandwidth_mbps > WAN_SAFETY_MARGIN * available_wan_mbps:
        return "hybrid"

    return "cloud"


# ---------------------------------------------------------------------------
# Full-scenario orchestration
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """Full computed output for a single scenario."""

    name: str
    camera_count: int
    per_camera_bitrate_mbps: float
    total_bandwidth_mbps: float
    storage_tb: float
    retention_days: float
    gpu_count: int
    recommended_architecture: str
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "camera_count": self.camera_count,
            "per_camera_bitrate_mbps": self.per_camera_bitrate_mbps,
            "total_bandwidth_mbps": self.total_bandwidth_mbps,
            "storage_tb": self.storage_tb,
            "retention_days": self.retention_days,
            "gpu_count": self.gpu_count,
            "recommended_architecture": self.recommended_architecture,
            "inputs": self.inputs,
        }


def run_scenario(config: dict[str, Any], throughput_table: dict[str, Any] | None = None) -> ScenarioResult:
    """Run the full calculation pipeline for one scenario config dict.

    Expected keys in `config` (see examples/*.yaml for full sample files):
      name, camera_count, resolution, fps, codec, quality_profile,
      retention_days, concurrent_ai_streams, ai_model, target_ai_fps,
      available_wan_mbps, latency_sensitive
    """
    per_camera_bitrate_mbps = estimate_per_camera_bitrate_mbps(
        resolution=config["resolution"],
        fps=config["fps"],
        codec=config["codec"],
        quality_profile=config.get("quality_profile", "medium"),
    )
    total_bandwidth_mbps = estimate_total_bandwidth_mbps(
        camera_count=config["camera_count"],
        per_camera_bitrate_mbps=per_camera_bitrate_mbps,
    )
    storage_tb = estimate_storage_tb(
        total_bandwidth_mbps=total_bandwidth_mbps,
        retention_days=config["retention_days"],
    )
    gpu_count = estimate_gpu_count(
        concurrent_ai_streams=config.get("concurrent_ai_streams", 0),
        model_name=config.get("ai_model", "generic_object_detection"),
        target_fps=config.get("target_ai_fps", 15),
        throughput_table=throughput_table,
    )
    recommended_architecture = recommend_architecture(
        total_bandwidth_mbps=total_bandwidth_mbps,
        available_wan_mbps=config["available_wan_mbps"],
        camera_count=config["camera_count"],
        latency_sensitive=config.get("latency_sensitive", False),
    )

    return ScenarioResult(
        name=config.get("name", "Unnamed scenario"),
        camera_count=config["camera_count"],
        per_camera_bitrate_mbps=per_camera_bitrate_mbps,
        total_bandwidth_mbps=total_bandwidth_mbps,
        storage_tb=storage_tb,
        retention_days=config["retention_days"],
        gpu_count=gpu_count,
        recommended_architecture=recommended_architecture,
        inputs=dict(config),
    )
