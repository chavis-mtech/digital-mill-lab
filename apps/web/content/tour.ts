/**
 * Guided Executive Tour — "ทดลองชมระบบใน 5 นาที" (SPEC §3). Seven steps, one consistent scenario
 * (PRESS_VIBRATION_ANOMALY: press vibration → press feed cut and slightly higher press-fibre oil loss; plant OER moves
 * only ~0.2 pp, within normal daily noise — the signal is in the equipment sensors, not in OER), so numbers agree across steps.
 *
 * Each step sets the demo context (scenario / role / playback), routes to a page and highlights the element
 * with `data-tour="<target>"`. ROUTE OWNERS: add that attribute to the named element when you build the
 * page. Until then the tour shows the narration with a "this view is not built yet" chip.
 */
import type { DemoRole } from "@dml/contracts";
import type { Bilingual } from "@/lib/i18n/define";
import type { PlaybackMode, ScenarioCode } from "@/lib/demo/constants";

export type TourStep = {
  id: string;
  route: string;
  scenario: ScenarioCode;
  role: DemoRole;
  playback: PlaybackMode;
  /** Value of the `data-tour` attribute to highlight on the target page. */
  target: string;
  /** Agent that owns the target page (for the "not built yet" chip). */
  owner: string;
  title: Bilingual;
  body: Bilingual;
};

const SCENARIO: ScenarioCode = "PRESS_VIBRATION_ANOMALY";

export const TOUR_STEPS: readonly TourStep[] = [
  {
    id: "efficiency-drop",
    route: "/demo/executive",
    scenario: SCENARIO,
    role: "executive",
    playback: "scenario_date",
    target: "exec-kpi-oer",
    owner: "frontend-exec",
    title: { th: "1 · ตรวจพบประสิทธิภาพการผลิตลดลง", en: "1 · Production efficiency drop detected" },
    body: {
      th: "ศูนย์ควบคุมผู้บริหารเทียบ KPI กับช่วงก่อนหน้า เมื่อเทียบกับช่วงเวลาเดียวกันของเมื่อวาน ปริมาณ FFB ที่แปรรูปและ CPO ต่ำลง ขณะที่ OER แทบไม่เปลี่ยน (อยู่ในความแกว่งปกติรายวัน) แต่มีการแจ้งเตือนวิกฤตที่เครื่องหีบ PRS-03 ตัวเลขทุกตัวมีป้ายบอกที่มา (ข้อมูลจริงสังเคราะห์ / พยากรณ์ / สมมติ)",
      en: "The control tower compares KPIs with the previous period. Against the same hours yesterday, processed FFB and CPO are lower while OER barely moves (within normal daily noise) — yet a critical alert points at press PRS-03. Every number is labelled synthetic actual, forecast or what-if.",
    },
  },
  {
    id: "ai-analyses",
    route: "/demo/palm-mill/ai-insights",
    scenario: SCENARIO,
    role: "production_engineer",
    playback: "scenario_date",
    target: "palm-anomaly-evidence",
    owner: "frontend-exec",
    title: { th: "2 · AI วิเคราะห์ข้อมูลที่เกี่ยวข้อง", en: "2 · AI analyses the related data" },
    body: {
      th: "ระบบตรวจจับความผิดปกติเทียบค่าที่สังเกตได้กับช่วงค่าปกติ แล้วแสดงหลักฐานและปัจจัยที่อาจเกี่ยวข้อง — ไม่ใช่สาเหตุที่พิสูจน์แล้ว",
      en: "Anomaly detection compares observed values with normal ranges and shows the evidence and possible contributing factors — not proven causes.",
    },
  },
  {
    id: "equipment-signal",
    route: "/demo/maintenance/equipment",
    scenario: SCENARIO,
    role: "maintenance_engineer",
    playback: "scenario_date",
    target: "equipment-sensor-trend",
    owner: "frontend-ops",
    title: { th: "3 · พบสัญญาณผิดปกติที่เครื่องจักร", en: "3 · Abnormal equipment signal found" },
    body: {
      th: "แนวโน้มการสั่นสะเทือนของเครื่องหีบ (screw press) สูงกว่าช่วงปกติ สถานะสุขภาพคำนวณจากเกณฑ์ที่ระบุชัดเจน และคะแนนความเสี่ยงเป็นการจัดลำดับเชิงเปรียบเทียบ ไม่ใช่ความน่าจะเป็น",
      en: "Screw-press vibration trends above its normal range. Health states come from explicit criteria; the risk score is a relative ranking, not a probability.",
    },
  },
  {
    id: "ai-proposes-inspection",
    route: "/demo/maintenance",
    scenario: SCENARIO,
    role: "maintenance_engineer",
    playback: "scenario_date",
    target: "maintenance-recommendation",
    owner: "frontend-ops",
    title: { th: "4 · AI เสนอให้ตรวจสอบ", en: "4 · AI proposes an inspection" },
    body: {
      th: "AI ให้คำแนะนำเท่านั้น (เช่น ตรวจตลับลูกปืนและการหล่อลื่น) ไม่ควบคุมเครื่องจักร วิศวกรเป็นผู้ตัดสินใจอนุมัติหรือปฏิเสธ",
      en: "AI only advises (e.g. inspect bearing and lubrication) and never controls machines. The engineer decides to approve or reject.",
    },
  },
  {
    id: "create-work-order",
    route: "/demo/maintenance/work-orders",
    scenario: SCENARIO,
    role: "factory_manager",
    playback: "scenario_date",
    target: "work-order-create",
    owner: "frontend-ops",
    title: { th: "5 · ผู้จัดการสร้างใบสั่งงานซ่อมบำรุง", en: "5 · Manager creates a maintenance work order" },
    body: {
      th: "การสร้างใบสั่งงานต้องยืนยันก่อนเสมอ มีผลเฉพาะในเซสชันแซนด์บ็อกซ์ของคุณ และถูกบันทึกใน audit trail แบบ hash chain",
      en: "Creating a work order always asks for confirmation, applies only to your sandbox session and is recorded in a hash-chained audit trail.",
    },
  },
  {
    id: "simulate-impact",
    route: "/demo/scenarios",
    scenario: SCENARIO,
    role: "factory_manager",
    playback: "scenario_date",
    target: "scenario-impact",
    owner: "frontend-exec",
    title: { th: "6 · จำลองผลกระทบต่อการผลิต", en: "6 · Simulate the production impact" },
    body: {
      th: "เครื่องจำลองคำนวณผลกระทบใหม่ด้วยสูตรที่แสดงให้เห็น เช่น ตัวอย่างการคำนวณ: FFB 1,000 ตัน × OER +0.5 pp = CPO +5 ตัน",
      en: "The simulator recomputes the impact with visible formulas — calculation example: 1,000 t FFB × +0.5 pp OER = +5 t CPO.",
    },
  },
  {
    id: "executive-status",
    route: "/demo/executive",
    scenario: SCENARIO,
    role: "executive",
    playback: "scenario_date",
    target: "exec-insight-summary",
    owner: "frontend-exec",
    title: { th: "7 · ผู้บริหารเห็นสถานะและประโยชน์ที่อาจได้รับ", en: "7 · The executive sees status and potential benefit" },
    body: {
      th: "สรุปสำหรับผู้บริหาร: อะไรผิดปกติ กระทบธุรกิจเท่าไร ทีมใดควรตรวจก่อน และควรตัดสินใจอะไร ประโยชน์ทางการเงินเป็นสถานการณ์เพื่อการอธิบายเท่านั้น",
      en: "Executive summary: what is abnormal, its business effect, which team checks first and what to decide. Financial benefit is an illustrative scenario only.",
    },
  },
];
