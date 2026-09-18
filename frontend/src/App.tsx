import { useEffect, useState, type FormEvent } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./App.css";
import {
  AI_MODEL_OPTIONS,
  CODEC_OPTIONS,
  DEFAULT_PLAN_REQUEST,
  QUALITY_PROFILE_OPTIONS,
  RESOLUTION_OPTIONS,
  type PlanRequest,
  type PlanResponse,
} from "./types";

// Same-origin default works when the frontend is served by the backend
// itself; during `npm run dev` (Vite on :5173) it points at the FastAPI
// dev server on :8000. Override at build time with VITE_API_BASE_URL.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const ARCHITECTURE_COPY: Record<PlanResponse["recommended_architecture"], string> = {
  edge:
    "Raw video exceeds available WAN capacity. Run AI inference locally at each site and ship only compressed detections/events/thumbnails back over the network.",
  hybrid:
    "Bandwidth is tight (or the workload is latency-sensitive). Keep time-critical inference local while still sending video to the cloud for archival and non-time-critical analytics.",
  cloud:
    "Ample WAN headroom and no latency constraint. Centralize raw video ingestion, storage, and inference in the cloud for simplicity of management.",
};

function formatNumber(value: number, digits = 2): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

interface ChartRow {
  metric: string;
  value: number;
  unit: string;
  color: string;
}

function App() {
  const [form, setForm] = useState<PlanRequest>(DEFAULT_PLAN_REQUEST);
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function calculate(payload: PlanRequest) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Request failed (${response.status}): ${detail}`);
      }
      const data: PlanResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error while computing plan.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  // Auto-calculate once on first render, pre-populated with the real
  // 500-camera / 20-facility example, so the page is compelling immediately.
  useEffect(() => {
    calculate(DEFAULT_PLAN_REQUEST);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    calculate(form);
  }

  function updateField<K extends keyof PlanRequest>(key: K, value: PlanRequest[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const bandwidthRow: ChartRow[] = result
    ? [{ metric: "Bandwidth", value: result.total_bandwidth_mbps, unit: "Mbps", color: "#2a78d6" }]
    : [];
  const storageRow: ChartRow[] = result
    ? [{ metric: "Storage", value: result.storage_tb, unit: "TB", color: "#eb6834" }]
    : [];
  const gpuRow: ChartRow[] = result
    ? [{ metric: "GPUs", value: result.gpu_count, unit: "GPUs", color: "#1baf7a" }]
    : [];

  return (
    <div className="page">
      <header className="page-header">
        <h1>Video Infrastructure Capacity Planner</h1>
        <p className="subtitle">
          Turn camera count, resolution, retention, and AI-inference load into concrete bandwidth,
          storage, GPU, and architecture recommendations.
        </p>
      </header>

      <main className="layout">
        <form className="panel form-panel" onSubmit={handleSubmit}>
          <h2>Scenario inputs</h2>

          <label>
            Scenario name
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField("name", e.target.value)}
            />
          </label>

          <div className="field-grid">
            <label>
              Camera count
              <input
                type="number"
                min={1}
                value={form.camera_count}
                onChange={(e) => updateField("camera_count", Number(e.target.value))}
                required
              />
            </label>

            <label>
              Resolution
              <select value={form.resolution} onChange={(e) => updateField("resolution", e.target.value)}>
                {RESOLUTION_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Frame rate (fps)
              <input
                type="number"
                min={1}
                value={form.fps}
                onChange={(e) => updateField("fps", Number(e.target.value))}
                required
              />
            </label>

            <label>
              Codec
              <select value={form.codec} onChange={(e) => updateField("codec", e.target.value)}>
                {CODEC_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Quality profile
              <select
                value={form.quality_profile}
                onChange={(e) => updateField("quality_profile", e.target.value)}
              >
                {QUALITY_PROFILE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option[0].toUpperCase() + option.slice(1)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Retention (days)
              <input
                type="number"
                min={0}
                value={form.retention_days}
                onChange={(e) => updateField("retention_days", Number(e.target.value))}
                required
              />
            </label>

            <label>
              Concurrent AI streams
              <input
                type="number"
                min={0}
                value={form.concurrent_ai_streams}
                onChange={(e) => updateField("concurrent_ai_streams", Number(e.target.value))}
                required
              />
            </label>

            <label>
              AI model
              <select value={form.ai_model} onChange={(e) => updateField("ai_model", e.target.value)}>
                {AI_MODEL_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Target AI fps
              <input
                type="number"
                min={1}
                value={form.target_ai_fps}
                onChange={(e) => updateField("target_ai_fps", Number(e.target.value))}
                required
              />
            </label>

            <label>
              Available WAN (Mbps)
              <input
                type="number"
                min={1}
                value={form.available_wan_mbps}
                onChange={(e) => updateField("available_wan_mbps", Number(e.target.value))}
                required
              />
            </label>
          </div>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.latency_sensitive}
              onChange={(e) => updateField("latency_sensitive", e.target.checked)}
            />
            Latency-sensitive workload
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "Calculating..." : "Calculate"}
          </button>

          {error && <p className="error">{error}</p>}
        </form>

        <section className="panel results-panel">
          <h2>Results</h2>

          {!result && !error && <p className="hint">Computing initial estimate...</p>}

          {result && (
            <>
              <div className="metric-cards">
                <div className="metric-card">
                  <span className="metric-label">Per-camera bitrate</span>
                  <span className="metric-value">{formatNumber(result.per_camera_bitrate_mbps, 4)}</span>
                  <span className="metric-unit">Mbps</span>
                </div>
                <div className="metric-card">
                  <span className="metric-label">Total bandwidth</span>
                  <span className="metric-value">{formatNumber(result.total_bandwidth_mbps)}</span>
                  <span className="metric-unit">Mbps</span>
                </div>
                <div className="metric-card">
                  <span className="metric-label">Storage ({formatNumber(result.retention_days, 0)}-day retention)</span>
                  <span className="metric-value">{formatNumber(result.storage_tb)}</span>
                  <span className="metric-unit">TB</span>
                </div>
                <div className="metric-card">
                  <span className="metric-label">GPUs required</span>
                  <span className="metric-value">{result.gpu_count}</span>
                  <span className="metric-unit">GPU{result.gpu_count === 1 ? "" : "s"}</span>
                </div>
              </div>

              <div className={`recommendation recommendation-${result.recommended_architecture}`}>
                <span className="recommendation-badge">{result.recommended_architecture}</span>
                <p>{ARCHITECTURE_COPY[result.recommended_architecture]}</p>
              </div>

              <h3 className="chart-heading">Bandwidth / storage / GPU comparison</h3>
              <div className="chart-grid">
                <MiniBarChart title="Bandwidth (Mbps)" rows={bandwidthRow} unit="Mbps" />
                <MiniBarChart title="Storage (TB)" rows={storageRow} unit="TB" />
                <MiniBarChart title="GPU count" rows={gpuRow} unit="GPUs" />
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function MiniBarChart({ title, rows, unit }: { title: string; rows: ChartRow[]; unit: string }) {
  return (
    <div className="mini-chart">
      <h4>{title}</h4>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={rows} margin={{ top: 16, right: 12, left: 12, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e1e0d9" vertical={false} />
          <XAxis dataKey="metric" tick={{ fill: "#898781", fontSize: 12 }} axisLine={{ stroke: "#c3c2b7" }} />
          <YAxis tick={{ fill: "#898781", fontSize: 12 }} axisLine={{ stroke: "#c3c2b7" }} />
          <Tooltip
            formatter={(value) => {
              const numeric = Number(value);
              return [`${formatNumber(numeric, numeric < 10 ? 2 : 1)} ${unit}`, title];
            }}
            contentStyle={{ borderRadius: 8, border: "1px solid #e1e0d9", fontSize: 13 }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={72}>
            {rows.map((row) => (
              <Cell key={row.metric} fill={row.color} />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              formatter={(label) => {
                const numeric = Number(label);
                return formatNumber(numeric, numeric < 10 ? 2 : 1);
              }}
              style={{ fill: "#0b0b0b", fontSize: 12, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default App;
