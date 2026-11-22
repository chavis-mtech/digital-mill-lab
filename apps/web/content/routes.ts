/**
 * Route registry for the demo and docs areas (SPEC §6). Drives the sidebar, breadcrumbs, the /demo hub and
 * <RoutePlaceholder>. Route owners replace their `page.tsx` wholesale; they normally don't need to edit this
 * file (ask frontend-foundation / orchestrator to change titles or grouping).
 */
import type { Bilingual } from "@/lib/i18n/define";
import type { FeatureKey } from "./status";

export type LayoutKind = "executive" | "operations" | "ai" | "docs";
export type IconName =
  | "layout-grid"
  | "gauge"
  | "factory"
  | "workflow"
  | "line-chart"
  | "sparkles"
  | "wrench"
  | "cog"
  | "clipboard-list"
  | "truck"
  | "zap"
  | "git-branch"
  | "bot"
  | "sliders"
  | "calculator"
  | "book-open"
  | "network"
  | "database"
  | "brain"
  | "plug"
  | "shield"
  | "map";

export type RouteEntry = {
  path: string;
  title: Bilingual;
  description: Bilingual;
  icon: IconName;
  layout: LayoutKind;
  feature: FeatureKey;
  owner: string;
  group: NavGroupKey;
  /** Parent path for breadcrumbs / sub-navigation. */
  parent?: string;
};

export type NavGroupKey = "overview" | "executive" | "palm_mill" | "maintenance" | "operations" | "ai" | "docs";

export const NAV_GROUPS: Record<NavGroupKey, Bilingual> = {
  overview: { th: "ภาพรวม", en: "Overview" },
  executive: { th: "ผู้บริหารและธุรกิจ", en: "Executive & business" },
  palm_mill: { th: "โรงสกัดน้ำมันปาล์ม", en: "Palm oil mill" },
  maintenance: { th: "ซ่อมบำรุง", en: "Maintenance" },
  operations: { th: "ปฏิบัติการสนับสนุน", en: "Supporting operations" },
  ai: { th: "พื้นที่ทำงาน AI", en: "AI workspace" },
  docs: { th: "เอกสารเทคนิค", en: "Technical docs" },
};

export const DEMO_ROUTES: readonly RouteEntry[] = [
  {
    path: "/demo/executive",
    title: { th: "ศูนย์ควบคุมผู้บริหาร", en: "Executive Control Tower" },
    description: {
      th: "KPI 12 ตัว เทียบช่วงก่อนหน้า การแจ้งเตือนตามระดับความเสี่ยง และสรุปข้อมูลเชิงลึกจาก AI",
      en: "12 KPIs vs the previous period, risk-ranked alerts and an AI insight summary.",
    },
    icon: "gauge",
    layout: "executive",
    feature: "executive_control_tower",
    owner: "frontend-exec",
    group: "executive",
  },
  {
    path: "/demo/business-impact",
    title: { th: "ผลกระทบทางธุรกิจ (ROI)", en: "Business Impact (ROI)" },
    description: {
      th: "กรณีฐาน/ระมัดระวัง/คาดการณ์/มองบวก พร้อมสูตรและสมมติฐานที่ตรวจสอบย้อนได้",
      en: "Baseline / conservative / expected / optimistic cases with traceable formulas and assumptions.",
    },
    icon: "calculator",
    layout: "executive",
    feature: "business_impact",
    owner: "frontend-exec",
    group: "executive",
  },
  {
    path: "/demo/scenarios",
    title: { th: "เครื่องจำลองสถานการณ์", en: "Scenario Simulator" },
    description: {
      th: "ปรับปริมาณ FFB, OER, ชั่วโมงเดินเครื่อง และราคา แล้วคำนวณใหม่จริงพร้อมแสดงสูตร",
      en: "Adjust FFB intake, OER, availability, hours and prices — recomputed by the API with formulas shown.",
    },
    icon: "sliders",
    layout: "executive",
    feature: "scenario_simulator",
    owner: "frontend-exec",
    group: "executive",
  },
  {
    path: "/demo/palm-mill",
    title: { th: "ภาพรวมการผลิต", en: "Production overview" },
    description: {
      th: "การรับ FFB อัตราการผลิต OER/KER สมดุลมวล และคุณภาพ ณ เวลาสาธิต",
      en: "FFB intake, throughput, OER/KER, mass balance and quality at the demo clock.",
    },
    icon: "factory",
    layout: "operations",
    feature: "palm_mill_production",
    owner: "frontend-exec",
    group: "palm_mill",
  },
  {
    path: "/demo/palm-mill/process",
    title: { th: "ผังกระบวนการ (Digital Twin Lite)", en: "Process flow (Digital Twin Lite)" },
    description: {
      th: "ผังกระบวนการแบบโต้ตอบได้ คลิกแต่ละขั้นตอนเพื่อดูสถานะเครื่องจักร เซนเซอร์ และการแจ้งเตือน",
      en: "Interactive process flow — click a stage for equipment status, sensors and alerts.",
    },
    icon: "workflow",
    layout: "operations",
    feature: "digital_twin_lite",
    owner: "frontend-exec",
    group: "palm_mill",
    parent: "/demo/palm-mill",
  },
  {
    path: "/demo/palm-mill/analytics",
    title: { th: "การวิเคราะห์และพยากรณ์ OER", en: "Analytics & OER forecast" },
    description: {
      th: "แนวโน้ม OER เทียบค่าคาดหมาย พยากรณ์พร้อมช่วงความไม่แน่นอน และเทียบกับ baseline",
      en: "OER trend vs expected, forecast with an uncertainty band and a naive-baseline comparison.",
    },
    icon: "line-chart",
    layout: "operations",
    feature: "oer_forecast",
    owner: "frontend-exec",
    group: "palm_mill",
    parent: "/demo/palm-mill",
  },
  {
    path: "/demo/palm-mill/ai-insights",
    title: { th: "ข้อมูลเชิงลึกจาก AI", en: "AI insights" },
    description: {
      th: "ความผิดปกติของการผลิต หลักฐานที่สังเกตได้ ช่วงค่าปกติ และปัจจัยที่อาจเกี่ยวข้อง",
      en: "Production anomalies with observed evidence, normal ranges and possible contributing factors.",
    },
    icon: "sparkles",
    layout: "operations",
    feature: "production_anomaly",
    owner: "frontend-exec",
    group: "palm_mill",
    parent: "/demo/palm-mill",
  },
  {
    path: "/demo/maintenance",
    title: { th: "ภาพรวมซ่อมบำรุง", en: "Maintenance overview" },
    description: {
      th: "สุขภาพเครื่องจักร คำแนะนำเชิงป้องกัน และการอนุมัติโดยมนุษย์",
      en: "Equipment health, advisory recommendations and human approval.",
    },
    icon: "wrench",
    layout: "operations",
    feature: "predictive_maintenance",
    owner: "frontend-ops",
    group: "maintenance",
  },
  {
    path: "/demo/maintenance/equipment",
    title: { th: "เครื่องจักรและเซนเซอร์", en: "Equipment & sensors" },
    description: {
      th: "ทะเบียนเครื่องจักร เกณฑ์สถานะสุขภาพ อนุกรมเวลาเซนเซอร์ และคะแนนความเสี่ยงเชิงเปรียบเทียบ",
      en: "Registry, explicit health criteria, sensor time-series and relative risk ranking.",
    },
    icon: "cog",
    layout: "operations",
    feature: "equipment_health",
    owner: "frontend-ops",
    group: "maintenance",
    parent: "/demo/maintenance",
  },
  {
    path: "/demo/maintenance/work-orders",
    title: { th: "ใบสั่งงาน", en: "Work orders" },
    description: {
      th: "แจ้งเตือน AI → ตรวจสอบ → ใบสั่งงาน → มอบหมายช่าง → บันทึก → ปิดงาน พร้อม audit trail",
      en: "AI alert → review → work order → technician → record → resolved, with an audit trail.",
    },
    icon: "clipboard-list",
    layout: "operations",
    feature: "work_orders",
    owner: "frontend-ops",
    group: "maintenance",
    parent: "/demo/maintenance",
  },
  {
    path: "/demo/logistics",
    title: { th: "โลจิสติกส์และตาชั่ง", en: "Logistics & weighbridge" },
    description: {
      th: "คิวรถ ตั๋วชั่ง เวลารอ การพยากรณ์คิว และการจำลองการจัดช่วงเวลา",
      en: "Truck queue, weighbridge tickets, waiting time, queue prediction and slot simulation.",
    },
    icon: "truck",
    layout: "operations",
    feature: "logistics",
    owner: "frontend-ops",
    group: "operations",
  },
  {
    path: "/demo/energy",
    title: { th: "พลังงาน", en: "Energy" },
    description: {
      th: "พลังงานต่อตัน FFB ไอน้ำ น้ำ ต้นทุนต่อตัน การพยากรณ์ และ what-if พร้อมข้อจำกัด",
      en: "Energy per tonne, steam, water, cost per tonne, forecast and what-if with stated limits.",
    },
    icon: "zap",
    layout: "operations",
    feature: "energy",
    owner: "frontend-ops",
    group: "operations",
  },
  {
    path: "/demo/traceability",
    title: { th: "การตรวจสอบย้อนกลับ", en: "Traceability" },
    description: {
      th: "ผู้ส่ง → การส่งมอบ → ล็อต FFB → ล็อตการผลิต → ล็อต CPO แบบสมดุลมวล",
      en: "Supplier → delivery → FFB batch → processing batch → CPO lot (mass balance).",
    },
    icon: "git-branch",
    layout: "operations",
    feature: "traceability",
    owner: "frontend-ops",
    group: "operations",
  },
  {
    path: "/demo/ai-copilot",
    title: { th: "ผู้ช่วย AI", en: "AI Copilot" },
    description: {
      th: "ถามด้วยภาษาธรรมชาติ ได้คำตอบจากข้อมูลในระบบพร้อมแหล่งอ้างอิงและหลักฐาน",
      en: "Ask in natural language; answers grounded in system data with sources and evidence.",
    },
    icon: "bot",
    layout: "ai",
    feature: "copilot",
    owner: "frontend-ops",
    group: "ai",
  },
];

export const DOCS_ROUTES: readonly RouteEntry[] = [
  ["/docs/overview", "ภาพรวมเอกสาร", "Overview", "book-open"],
  ["/docs/architecture", "สถาปัตยกรรม", "Architecture", "network"],
  ["/docs/data-model", "แบบจำลองข้อมูล", "Data model", "database"],
  ["/docs/ai-methodology", "ระเบียบวิธี AI", "AI methodology", "brain"],
  ["/docs/integration", "การเชื่อมต่อระบบ", "Integration", "plug"],
  ["/docs/security", "ความปลอดภัย", "Security", "shield"],
  ["/docs/roadmap", "แผนงาน", "Roadmap", "map"],
].map(([path, th, en, icon]) => ({
  path: path as string,
  title: { th: th as string, en: en as string },
  description: {
    th: "เอกสารเทคนิคที่ต้องตรงกับสิ่งที่สร้างจริง พร้อมป้ายสถานะสำหรับส่วนที่ยังไม่สร้าง",
    en: "Technical documentation that must match what is really built, with status labels for unbuilt parts.",
  },
  icon: icon as IconName,
  layout: "docs" as const,
  feature: "technical_docs" as const,
  owner: "frontend-ops",
  group: "docs" as const,
}));

export const ALL_APP_ROUTES: readonly RouteEntry[] = [...DEMO_ROUTES, ...DOCS_ROUTES];

export function findRoute(path: string): RouteEntry | undefined {
  return ALL_APP_ROUTES.find((r) => r.path === path);
}

export function childRoutes(parent: string): RouteEntry[] {
  return DEMO_ROUTES.filter((r) => r.parent === parent);
}
