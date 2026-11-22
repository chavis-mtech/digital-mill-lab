/**
 * SINGLE SOURCE OF FEATURE MATURITY IN THE UI (the build plan §4 ruling).
 *
 * Every <StatusChip feature="…"> on every page reads from this file. Values follow the contract enum
 * `FeatureStatus`: implemented | partial | prototype | planned.
 *
 * RULES
 *  - Only the ORCHESTRATOR changes a status to `implemented`, after verifying evidence (the engineering logs (kept private)).
 *  - Owner agents may move their own entries planned → partial / prototype when work exists, and must
 *    write the evidence in their status file.
 *  - `target` = the maturity the feature is meant to reach (e.g. P2 concepts stay `prototype` forever).
 *
 * Initialised by frontend-foundation (wave 1) — honestly: everything is `planned` unless it exists.
 */
import type { Schema } from "@dml/contracts";
import type { Bilingual } from "@/lib/i18n/define";

export type FeatureStatus = Schema<"FeatureStatus">;
export type Priority = "P0" | "P1" | "P2" | "platform";

export type FeatureEntry = {
  label: Bilingual;
  status: FeatureStatus;
  target?: FeatureStatus;
  priority: Priority;
  route?: string;
  owner: string;
  tasks: readonly string[];
  note?: Bilingual;
};

export const FEATURES = {
  // ── Platform ────────────────────────────────────────────────────────────────
  public_site: {
    label: { th: "เว็บไซต์นำเสนอโครงการ", en: "Public project site" },
    status: "implemented",
    priority: "platform",
    route: "/",
    owner: "frontend-foundation",
    tasks: ["DML-020", "DML-091", "DML-092", "DML-093", "DML-096"],
    note: { th: "ภาษาไทยยังไม่ผ่านการตรวจโดยเจ้าของภาษา; ข้อมูลผู้พัฒนาที่ไม่มีใน README เป็นตัวยึดตำแหน่ง", en: "Thai copy not yet reviewed by a native speaker; developer facts not in the README are placeholders." },
  },
  design_system: {
    label: { th: "ระบบดีไซน์และคอมโพเนนต์กลาง", en: "Design system & shared components" },
    status: "implemented",
    priority: "platform",
    route: "/ui-kit",
    owner: "frontend-foundation",
    tasks: ["DML-018", "DML-019", "DML-024"],
  },
  guided_tour: {
    label: { th: "ทัวร์นำชมสำหรับผู้บริหาร", en: "Guided executive tour" },
    status: "implemented",
    priority: "platform",
    owner: "frontend-foundation",
    tasks: ["DML-097"],
  },
  api_contract: {
    label: { th: "สัญญา API แบบมีชนิดข้อมูล", en: "Typed API contract" },
    status: "implemented",
    priority: "platform",
    owner: "architect",
    tasks: ["DML-014"],
  },
  api_foundation: {
    label: { th: "แกนบริการ API (middleware, DemoContext, RBAC, audit)", en: "API core (middleware, DemoContext, RBAC, audit)" },
    status: "implemented",
    priority: "platform",
    owner: "architect",
    tasks: ["DML-011", "DML-103", "DML-104"],
  },
  database_schema: {
    label: { th: "สคีมาฐานข้อมูลและ migration", en: "Database schema & migrations" },
    status: "partial",
    priority: "platform",
    owner: "architect",
    tasks: ["DML-012", "DML-013"],
    note: { th: "ใช้งานจริงบน SQLite; PostgreSQL ตรวจเป็น DDL ออฟไลน์เท่านั้น ยังไม่เคยรันกับเซิร์ฟเวอร์จริง", en: "Runs on SQLite; PostgreSQL only checked as offline DDL, never run against a live server." },
  },
  domain_services: {
    label: { th: "บริการโดเมน (KPI, การผลิต, ซ่อมบำรุง, ROI ฯลฯ)", en: "Domain services (KPI, production, maintenance, ROI…)" },
    status: "implemented",
    priority: "platform",
    owner: "backend-a / backend-b",
    tasks: ["DML-035", "DML-043", "DML-051", "DML-086"],
  },
  ml_models: {
    label: { th: "โมเดล ML (พยากรณ์ ความผิดปกติ ความเสี่ยง)", en: "ML models (forecast, anomaly, risk)" },
    status: "implemented",
    priority: "platform",
    owner: "ml",
    tasks: ["DML-046", "DML-047", "DML-048", "DML-053", "DML-054"],
    note: { th: "ตรวจจับความผิดปกติใช้ได้ผล; โมเดลพยากรณ์ OER พลังงาน และรถเข้า ไม่ชนะ baseline และรายงานตามจริง", en: "Anomaly detectors perform; the OER, energy and arrival forecasts do not beat their baselines and are reported as such." },
  },
  synthetic_data: {
    label: { th: "เอนจินข้อมูลสังเคราะห์ 120 วัน", en: "120-day synthetic data engine" },
    status: "implemented",
    priority: "platform",
    owner: "data-engine",
    tasks: ["DML-025", "DML-026", "DML-032", "DML-033", "DML-034"],
  },
  simulated_live: {
    label: { th: "โหมดจำลองแบบสด", en: "Simulated live mode" },
    status: "partial",
    priority: "platform",
    owner: "backend-b",
    tasks: ["DML-037"],
    note: { th: "API tick ทำงานแล้ว; ฝั่งหน้าจอยังไม่ได้ครอบคลุมด้วยเทสต์ e2e", en: "The tick API works; the UI path is not covered by an end-to-end test." },
  },
  session_sandbox: {
    label: { th: "แซนด์บ็อกซ์ต่อผู้เยี่ยมชม", en: "Per-visitor sandbox session" },
    status: "implemented",
    priority: "platform",
    owner: "backend-b",
    tasks: ["DML-034"],
  },
  integration_contracts: {
    label: { th: "สัญญาการเชื่อมต่อระบบในอนาคต", en: "Future integration contracts" },
    status: "planned",
    priority: "platform",
    route: "/docs/integration",
    owner: "architect",
    tasks: ["DML-014"],
    note: {
      th: "เป็นเพียงสัญญา (contract) ไม่มีการเชื่อมต่อระบบจริงใด ๆ",
      en: "Contract only — nothing connects to any real system.",
    },
  },

  // ── P0 flagship ─────────────────────────────────────────────────────────────
  executive_control_tower: {
    label: { th: "ศูนย์ควบคุมอัจฉริยะสำหรับผู้บริหาร", en: "Executive Industrial Control Tower" },
    status: "implemented",
    priority: "P0",
    route: "/demo/executive",
    owner: "frontend-exec / backend-a",
    tasks: ["DML-035", "DML-036", "DML-037", "DML-038", "DML-039", "DML-040", "DML-041", "DML-042"],
  },
  palm_mill_production: {
    label: { th: "ข้อมูลอัจฉริยะการผลิตโรงสกัด", en: "Palm Mill Production Intelligence" },
    status: "implemented",
    priority: "P0",
    route: "/demo/palm-mill",
    owner: "frontend-exec / backend-a",
    tasks: ["DML-043", "DML-044", "DML-045"],
  },
  digital_twin_lite: {
    label: { th: "ดิจิทัลทวินแบบย่อของกระบวนการ", en: "Industrial Digital Twin Lite" },
    status: "implemented",
    priority: "P0",
    route: "/demo/palm-mill/process",
    owner: "frontend-exec / backend-a",
    tasks: ["DML-079", "DML-080", "DML-081"],
  },
  oer_forecast: {
    label: { th: "พยากรณ์ OER (AI-B01)", en: "OER forecast (AI-B01)" },
    status: "partial",
    priority: "P0",
    route: "/demo/palm-mill/analytics",
    owner: "ml",
    tasks: ["DML-046", "DML-047", "DML-049"],
    note: { th: "โมเดลพยากรณ์ OER ไม่ชนะ baseline ทุกระดับ (รายชั่วโมง/กะ/วัน) หน้าจอแสดงการเทียบตามจริง; คำอธิบายปัจจัยจากโมเดลไม่น่าเชื่อถือนอกตัวอย่าง", en: "The OER forecast does not beat its baseline at any granularity; the page shows the comparison honestly. Model attribution is unreliable out of sample." },
  },
  production_anomaly: {
    label: { th: "ตรวจจับความผิดปกติการผลิต (AI-B02)", en: "Production anomaly detection (AI-B02)" },
    status: "implemented",
    priority: "P0",
    route: "/demo/palm-mill/ai-insights",
    owner: "ml",
    tasks: ["DML-048", "DML-049"],
  },
  production_scenarios: {
    label: { th: "วิเคราะห์สถานการณ์การผลิต (AI-B03)", en: "Production scenario analysis (AI-B03)" },
    status: "implemented",
    priority: "P0",
    route: "/demo/scenarios",
    owner: "frontend-exec / backend-b",
    tasks: ["DML-050"],
  },
  predictive_maintenance: {
    label: { th: "AI ซ่อมบำรุงเชิงพยากรณ์", en: "Predictive Maintenance AI" },
    status: "implemented",
    priority: "P0",
    route: "/demo/maintenance",
    owner: "frontend-ops / backend-b / ml",
    tasks: ["DML-051", "DML-052", "DML-053", "DML-054", "DML-055"],
  },
  equipment_health: {
    label: { th: "สถานะสุขภาพเครื่องจักร (AI-C01)", en: "Equipment health states (AI-C01)" },
    status: "implemented",
    priority: "P0",
    route: "/demo/maintenance/equipment",
    owner: "backend-b",
    tasks: ["DML-051", "DML-052"],
  },
  failure_risk: {
    label: { th: "คะแนนความเสี่ยงเชิงเปรียบเทียบ (AI-C03)", en: "Relative failure-risk score (AI-C03)" },
    status: "implemented",
    priority: "P0",
    route: "/demo/maintenance/equipment",
    owner: "ml",
    tasks: ["DML-054"],
    note: { th: "ดัชนีเปรียบเทียบตามกฎ ไม่ใช่ความน่าจะเป็นของการเสียหายที่สอบเทียบแล้ว", en: "A rule-based relative index, not a calibrated probability of failure." },
  },
  copilot: {
    label: { th: "ผู้ช่วย AI สำหรับงานปฏิบัติการ", en: "Industrial Operations Copilot" },
    status: "implemented",
    priority: "P0",
    route: "/demo/ai-copilot",
    owner: "copilot / frontend-ops",
    tasks: ["DML-071", "DML-072", "DML-073", "DML-074", "DML-076", "DML-077", "DML-078"],
    note: { th: "โหมดไม่ใช้ API; ถามด้วยถ้อยคำใหม่ตอบถูกราวครึ่งและถามกลับราว 35%", en: "Deterministic no-API mode; on fresh paraphrases it answers correctly about half the time and asks a clarifying question about 35%." },
  },
  copilot_llm_mode: {
    label: { th: "โหมด LLM ของผู้ช่วย (ตัวเลือก)", en: "Copilot LLM mode (optional)" },
    status: "prototype",
    priority: "P0",
    owner: "copilot",
    tasks: ["DML-075"],
    note: { th: "มีตัวเชื่อม LLM แต่ทดสอบกับผู้ให้บริการปลอมเท่านั้น ยังไม่เคยเรียกผู้ให้บริการจริง", en: "Provider adapters exist but were tested only with a fake provider; no real LLM provider was ever called." },
  },
  scenario_simulator: {
    label: { th: "เครื่องจำลองสถานการณ์", en: "Scenario Simulator" },
    status: "implemented",
    priority: "P0",
    route: "/demo/scenarios",
    owner: "frontend-exec / backend-b",
    tasks: ["DML-087", "DML-089"],
  },
  business_impact: {
    label: { th: "วิเคราะห์ผลกระทบทางธุรกิจแบบตรวจสอบย้อนได้", en: "Traceable Business Impact (ROI)" },
    status: "implemented",
    priority: "P0",
    route: "/demo/business-impact",
    owner: "frontend-exec / backend-b",
    tasks: ["DML-085", "DML-086", "DML-088", "DML-090"],
  },

  // ── P1 supporting ───────────────────────────────────────────────────────────
  work_orders: {
    label: { th: "ใบสั่งงานซ่อมบำรุง", en: "Maintenance work orders" },
    status: "implemented",
    priority: "P1",
    route: "/demo/maintenance/work-orders",
    owner: "frontend-ops / backend-b",
    tasks: ["DML-056", "DML-057"],
  },
  human_approval: {
    label: { th: "คำแนะนำ AI และการอนุมัติโดยมนุษย์", en: "AI recommendations & human approval" },
    status: "implemented",
    priority: "P1",
    route: "/demo/maintenance",
    owner: "backend-b",
    tasks: ["DML-055"],
  },
  maintenance_impact: {
    label: { th: "จำลองผลกระทบการหยุดเครื่อง (AI-C06)", en: "Downtime impact what-if (AI-C06)" },
    status: "implemented",
    priority: "P1",
    route: "/demo/maintenance",
    owner: "backend-b",
    tasks: ["DML-058"],
  },
  logistics: {
    label: { th: "โลจิสติกส์และตาชั่งรถบรรทุก", en: "Logistics & Weighbridge Intelligence" },
    status: "partial",
    priority: "P1",
    route: "/demo/logistics",
    owner: "frontend-ops / backend-a / ml",
    tasks: ["DML-059", "DML-060", "DML-061", "DML-062", "DML-063", "DML-064"],
    note: { th: "การจำลองคิวยังไม่ตรงกับข้อมูลจริง (ยังไม่ปรับเทียบ) หน้าจอแสดงค่าจริงเทียบค่าจำลองและคำเตือน", en: "The queue simulation does not yet reproduce the observed congestion (uncalibrated); the page shows observed vs simulated with a warning." },
  },
  energy: {
    label: { th: "พลังงานและความยั่งยืน", en: "Energy & Sustainability" },
    status: "partial",
    priority: "P1",
    route: "/demo/energy",
    owner: "frontend-ops / backend-a / ml",
    tasks: ["DML-065", "DML-066", "DML-067", "DML-068", "DML-069", "DML-070"],
    note: { th: "วิเคราะห์และ what-if ใช้ได้; โมเดลพยากรณ์พลังงานไม่ชนะ baseline และตัวตรวจความผิดปกติพลาด label เดียวในชุดทดสอบ", en: "Analytics and what-if work; the energy forecast does not beat its baseline and the anomaly detector misses the only held-out label." },
  },
  traceability: {
    label: { th: "ผู้ส่ง FFB และการตรวจสอบย้อนกลับ", en: "FFB Supplier & Traceability" },
    status: "implemented",
    priority: "P1",
    route: "/demo/traceability",
    owner: "frontend-ops / backend-b",
    tasks: ["DML-082", "DML-083", "DML-084"],
    note: { th: "ติดตามแบบสมดุลมวล (mass-balance) โครงสร้างข้อมูลแบบ RSPO ไม่ใช่การรับรอง", en: "Mass-balance tracking; an RSPO-style data model, not a certification." },
  },

  // ── P2 concepts (always labelled prototype, never production) ───────────────
  cv_grading: {
    label: { th: "ต้นแบบคัดเกรด FFB ด้วยภาพ", en: "Computer-vision FFB grading" },
    status: "prototype",
    target: "prototype",
    priority: "P2",
    owner: "ml",
    tasks: ["P2-CV"],
    note: { th: "ต้นแบบวิจัย: อัปโหลดอย่างปลอดภัยและสถิติสีของภาพ ไม่ใช่ตัวคัดเกรดที่ผ่านการตรวจสอบ ไม่มีค่าความแม่นยำ", en: "Research prototype: safe upload and image colour statistics, not a validated grader; no accuracy is claimed." },
  },
  smart_plantation: {
    label: { th: "สวนอัจฉริยะ / พยากรณ์ผลผลิต", en: "Smart plantation / yield forecast" },
    status: "planned",
    target: "prototype",
    priority: "P2",
    owner: "unassigned",
    tasks: [],
  },
  petroleum_inventory: {
    label: { th: "บริหารคลังปิโตรเลียม", en: "Petroleum inventory" },
    status: "planned",
    target: "prototype",
    priority: "P2",
    owner: "unassigned",
    tasks: [],
  },
  port_scheduling: {
    label: { th: "จัดตารางท่าเรือและคลังสินค้า", en: "Port & terminal scheduling" },
    status: "planned",
    target: "prototype",
    priority: "P2",
    owner: "unassigned",
    tasks: [],
  },
  group_data_platform: {
    label: { th: "แพลตฟอร์มข้อมูลข้ามธุรกิจ", en: "Cross-company data platform" },
    status: "planned",
    target: "prototype",
    priority: "P2",
    owner: "unassigned",
    tasks: [],
  },

  // ── Technical docs pages ────────────────────────────────────────────────────
  technical_docs: {
    label: { th: "เอกสารเทคนิค", en: "Technical documentation" },
    status: "implemented",
    priority: "platform",
    route: "/docs/overview",
    owner: "frontend-ops",
    tasks: ["DML-107", "DML-109", "DML-110", "DML-111"],
  },
} as const satisfies Record<string, FeatureEntry>;

export type FeatureKey = keyof typeof FEATURES;

export function getFeature(key: FeatureKey): FeatureEntry {
  return FEATURES[key];
}

export const STATUS_ORDER: readonly FeatureStatus[] = ["implemented", "partial", "prototype", "planned"];
