"""Small FastAPI web form for interactive capacity planning.

Run with:

    uvicorn planner.webform:app --reload

Then open http://127.0.0.1:8000/ in a browser. The GET route renders a
plain HTML form; the POST route computes the plan and returns the same HTML
report produced by the CLI.

This is intentionally small -- it is meant for quick interactive use on a
call (e.g. adjusting camera count live while talking to a customer), not as
a production multi-tenant web service. There is no authentication, no
persistence, and no input sanitization beyond basic type coercion.
"""

from __future__ import annotations

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .calculator import RESOLUTION_PRESETS, run_scenario
from .report import render_report_html

app = FastAPI(title="Video Infrastructure Capacity Planner")

# Permissive CORS so the standalone React/Vite dev server (a different
# origin, e.g. http://localhost:5173) can call the JSON API below during
# local development. This process has no auth/session state, so a permissive
# CORS policy does not expose anything sensitive -- see the module docstring.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_FORM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Video Infrastructure Capacity Planner</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          max-width: 560px; margin: 2rem auto; color: #1a202c; }}
  h1 {{ font-size: 1.4rem; }}
  label {{ display: block; margin-top: 0.9rem; font-size: 0.9rem; color: #4a5568; }}
  input, select {{ width: 100%; padding: 0.4rem; margin-top: 0.2rem; box-sizing: border-box; }}
  button {{ margin-top: 1.4rem; padding: 0.6rem 1.2rem; background: #2b6cb0; color: white;
            border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }}
  .hint {{ color: #718096; font-size: 0.8rem; }}
</style>
</head>
<body>
  <h1>Video Infrastructure Capacity Planner</h1>
  <p class="hint">Fill in a scenario to get an instant bandwidth / storage / GPU / architecture estimate.</p>
  <form method="post" action="/plan">
    <label>Scenario name
      <input type="text" name="name" value="Discovery-call scenario">
    </label>
    <label>Camera count
      <input type="number" name="camera_count" value="50" min="1" required>
    </label>
    <label>Resolution
      <select name="resolution">
        {resolution_options}
      </select>
    </label>
    <label>Frame rate (fps)
      <input type="number" name="fps" value="15" min="1" required>
    </label>
    <label>Codec
      <select name="codec">
        <option value="h264">H.264</option>
        <option value="h265" selected>H.265</option>
        <option value="mjpeg">MJPEG</option>
      </select>
    </label>
    <label>Quality profile
      <select name="quality_profile">
        <option value="low">Low</option>
        <option value="medium" selected>Medium</option>
        <option value="high">High</option>
      </select>
    </label>
    <label>Retention (days)
      <input type="number" name="retention_days" value="30" min="1" required>
    </label>
    <label>Concurrent AI inference streams
      <input type="number" name="concurrent_ai_streams" value="10" min="0" required>
    </label>
    <label>AI model
      <select name="ai_model">
        <option value="person_detection_yolov8n">Person detection (YOLOv8n)</option>
        <option value="person_detection_yolov8m" selected>Person detection (YOLOv8m)</option>
        <option value="generic_object_detection">Generic object detection</option>
        <option value="face_recognition">Face recognition</option>
        <option value="license_plate_recognition">License plate recognition</option>
      </select>
    </label>
    <label>Target AI inference fps
      <input type="number" name="target_ai_fps" value="10" min="1" required>
    </label>
    <label>Available WAN capacity (Mbps)
      <input type="number" name="available_wan_mbps" value="200" min="1" required>
    </label>
    <label>
      <input type="checkbox" name="latency_sensitive" value="true" style="width:auto; display:inline;">
      Latency-sensitive workload
    </label>
    <button type="submit">Compute plan</button>
  </form>
</body>
</html>
"""


def _render_form() -> str:
    options = "\n".join(
        f'<option value="{key}"{" selected" if key == "1080p" else ""}>{key}</option>'
        for key in RESOLUTION_PRESETS
    )
    return _FORM_HTML.format(resolution_options=options)


@app.get("/", response_class=HTMLResponse)
def show_form() -> str:
    return _render_form()


@app.post("/plan", response_class=HTMLResponse)
def compute_plan(
    name: str = Form("Discovery-call scenario"),
    camera_count: int = Form(...),
    resolution: str = Form("1080p"),
    fps: float = Form(...),
    codec: str = Form("h265"),
    quality_profile: str = Form("medium"),
    retention_days: float = Form(...),
    concurrent_ai_streams: int = Form(0),
    ai_model: str = Form("generic_object_detection"),
    target_ai_fps: float = Form(15),
    available_wan_mbps: float = Form(...),
    latency_sensitive: str | None = Form(None),
) -> str:
    config = {
        "name": name,
        "camera_count": camera_count,
        "resolution": resolution,
        "fps": fps,
        "codec": codec,
        "quality_profile": quality_profile,
        "retention_days": retention_days,
        "concurrent_ai_streams": concurrent_ai_streams,
        "ai_model": ai_model,
        "target_ai_fps": target_ai_fps,
        "available_wan_mbps": available_wan_mbps,
        "latency_sensitive": bool(latency_sensitive),
    }
    result = run_scenario(config)
    return render_report_html([result])


# ---------------------------------------------------------------------------
# JSON API (additive) -- for the React/TypeScript planner UI in frontend/.
#
# This endpoint accepts the exact same scenario inputs as the HTML form/CLI
# and returns the computed numbers as JSON instead of a rendered HTML report,
# by calling the same `run_scenario()` pipeline used everywhere else in this
# project. It does not reimplement any of the bandwidth/storage/GPU math, so
# results stay numerically identical to the CLI, the HTML report, and the
# existing test suite.
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """Scenario inputs for POST /api/plan. Mirrors the fields run_scenario() reads."""

    name: str = "Discovery-call scenario"
    camera_count: int = Field(..., gt=0)
    resolution: str = "1080p"
    fps: float = Field(..., gt=0)
    codec: str = "h265"
    quality_profile: str = "medium"
    retention_days: float = Field(..., ge=0)
    concurrent_ai_streams: int = Field(0, ge=0)
    ai_model: str = "generic_object_detection"
    target_ai_fps: float = 15
    available_wan_mbps: float = Field(..., gt=0)
    latency_sensitive: bool = False


class PlanResponse(BaseModel):
    """Computed output for POST /api/plan. Mirrors ScenarioResult.to_dict()."""

    name: str
    camera_count: int
    per_camera_bitrate_mbps: float
    total_bandwidth_mbps: float
    storage_tb: float
    retention_days: float
    gpu_count: int
    recommended_architecture: str


@app.post("/api/plan", response_model=PlanResponse)
def api_compute_plan(request: PlanRequest) -> PlanResponse:
    """Compute a capacity plan and return it as JSON (for the React UI)."""
    result = run_scenario(request.model_dump())
    return PlanResponse(
        name=result.name,
        camera_count=result.camera_count,
        per_camera_bitrate_mbps=result.per_camera_bitrate_mbps,
        total_bandwidth_mbps=result.total_bandwidth_mbps,
        storage_tb=result.storage_tb,
        retention_days=result.retention_days,
        gpu_count=result.gpu_count,
        recommended_architecture=result.recommended_architecture,
    )
