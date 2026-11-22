import type { DemoRole, Schema } from "@dml/contracts";
import type { Bilingual } from "@/lib/i18n/define";

export type ScenarioCode = Schema<"ScenarioCode">;
export type PlaybackMode = "today" | "last_7_days" | "last_30_days" | "scenario_date" | "simulated_live";
export type Period = Schema<"Period">;

/** Order matters: it is the order shown in the switcher. Keys = contract enum `ScenarioCode`. */
export const SCENARIO_CODES: readonly ScenarioCode[] = [
  "NORMAL_DAY",
  "OER_DEGRADATION",
  "PRESS_VIBRATION_ANOMALY",
  "STEAM_PRESSURE_DEVIATION",
  "TRUCK_QUEUE_CONGESTION",
  "ENERGY_EFFICIENCY_DROP",
];

/**
 * UI labels for scenario codes. Used until/unless GET /api/v1/scenarios (backend-b, DML-087) returns the
 * catalog with `name_th` / `name_en`; the API names win when available.
 */
export const SCENARIO_LABELS: Record<ScenarioCode, Bilingual> = {
  NORMAL_DAY: { th: "วันทำงานปกติ", en: "Normal day" },
  OER_DEGRADATION: { th: "OER ลดลง", en: "OER degradation" },
  PRESS_VIBRATION_ANOMALY: { th: "เครื่องหีบสั่นผิดปกติ", en: "Press vibration anomaly" },
  STEAM_PRESSURE_DEVIATION: { th: "แรงดันไอน้ำเบี่ยงเบน", en: "Steam pressure deviation" },
  TRUCK_QUEUE_CONGESTION: { th: "คิวรถบรรทุกแออัด", en: "Truck queue congestion" },
  ENERGY_EFFICIENCY_DROP: { th: "ประสิทธิภาพพลังงานลดลง", en: "Energy efficiency drop" },
};

export const ROLES: readonly DemoRole[] = [
  "public_viewer",
  "executive",
  "factory_manager",
  "production_engineer",
  "maintenance_engineer",
  "logistics_officer",
  "ai_analyst",
  "system_admin",
];

/** Fallback labels; GET /api/v1/demo/roles (implemented) provides label_th / label_en at runtime. */
export const ROLE_LABELS: Record<DemoRole, Bilingual> = {
  public_viewer: { th: "ผู้ชมเดโมทั่วไป", en: "Public demo viewer" },
  executive: { th: "ผู้บริหาร", en: "Executive" },
  factory_manager: { th: "ผู้จัดการโรงงาน", en: "Factory manager" },
  production_engineer: { th: "วิศวกรฝ่ายผลิต", en: "Production engineer" },
  maintenance_engineer: { th: "วิศวกรซ่อมบำรุง", en: "Maintenance engineer" },
  logistics_officer: { th: "เจ้าหน้าที่โลจิสติกส์", en: "Logistics officer" },
  ai_analyst: { th: "นักวิเคราะห์ AI", en: "AI analyst" },
  system_admin: { th: "ผู้ดูแลระบบ", en: "System administrator" },
};

export const PLAYBACK_MODES: readonly PlaybackMode[] = ["today", "last_7_days", "last_30_days", "scenario_date", "simulated_live"];

export const PLAYBACK_LABELS: Record<PlaybackMode, Bilingual> = {
  today: { th: "วันนี้", en: "Today" },
  last_7_days: { th: "7 วันล่าสุด", en: "Last 7 days" },
  last_30_days: { th: "30 วันล่าสุด", en: "Last 30 days" },
  scenario_date: { th: "วันที่ของสถานการณ์", en: "Scenario date" },
  simulated_live: { th: "จำลองแบบสด", en: "Simulated live" },
};

/** Playback → `period` query value for endpoints that accept one (contract enum `Period`). */
export const PLAYBACK_PERIOD: Record<PlaybackMode, Period> = {
  today: "today",
  last_7_days: "7d",
  last_30_days: "30d",
  scenario_date: "today",
  simulated_live: "today",
};

/** Simulated-live cadence: one tick every N ms, advancing the demo clock by `step_minutes` (server-side). */
export const LIVE_TICK_MS = 6000;
export const LIVE_STEP_MINUTES = 30;
