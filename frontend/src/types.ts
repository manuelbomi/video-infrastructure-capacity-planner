/**
 * TypeScript mirrors of the FastAPI Pydantic models in
 * `src/planner/webform.py` (`PlanRequest` / `PlanResponse` for
 * `POST /api/plan`). Keep these in sync with that file if the API changes.
 */

/** Resolution presets accepted by the backend's `resolution` field. */
export const RESOLUTION_OPTIONS = [
  "480p",
  "720p",
  "1080p",
  "1440p",
  "4mp",
  "5mp",
  "4k",
  "8mp",
  "12mp",
] as const;

export type Resolution = (typeof RESOLUTION_OPTIONS)[number];

export const CODEC_OPTIONS = ["h264", "h265", "mjpeg"] as const;
export type Codec = (typeof CODEC_OPTIONS)[number];

export const QUALITY_PROFILE_OPTIONS = ["low", "medium", "high"] as const;
export type QualityProfile = (typeof QUALITY_PROFILE_OPTIONS)[number];

export const AI_MODEL_OPTIONS = [
  "person_detection_yolov8n",
  "person_detection_yolov8m",
  "generic_object_detection",
  "face_recognition",
  "license_plate_recognition",
] as const;
export type AiModel = (typeof AI_MODEL_OPTIONS)[number];

/** Request body for `POST /api/plan`. Mirrors `webform.PlanRequest`. */
export interface PlanRequest {
  name: string;
  camera_count: number;
  resolution: string;
  fps: number;
  codec: string;
  quality_profile: string;
  retention_days: number;
  concurrent_ai_streams: number;
  ai_model: string;
  target_ai_fps: number;
  available_wan_mbps: number;
  latency_sensitive: boolean;
}

/** Recommended deployment architecture returned by the calculator. */
export type RecommendedArchitecture = "edge" | "hybrid" | "cloud";

/** Response body from `POST /api/plan`. Mirrors `webform.PlanResponse`. */
export interface PlanResponse {
  name: string;
  camera_count: number;
  per_camera_bitrate_mbps: number;
  total_bandwidth_mbps: number;
  storage_tb: number;
  retention_days: number;
  gpu_count: number;
  recommended_architecture: RecommendedArchitecture;
}

/**
 * Default form values, taken directly from the real, hand-verified
 * `examples/500_cameras_20_sites.yaml` scenario so the very first render
 * already shows a realistic, compelling result
 * (see `examples/500_cameras_20_sites_expected_output.json`).
 */
export const DEFAULT_PLAN_REQUEST: PlanRequest = {
  name: "500 cameras across 20 facilities",
  camera_count: 500,
  resolution: "1080p",
  fps: 15,
  codec: "h265",
  quality_profile: "medium",
  retention_days: 30,
  concurrent_ai_streams: 100,
  ai_model: "person_detection_yolov8m",
  target_ai_fps: 10,
  available_wan_mbps: 500,
  latency_sensitive: false,
};
