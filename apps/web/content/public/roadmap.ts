/**
 * Proposed transformation roadmap (SPEC §13). Tag: Proposed Future Capability.
 * Rules: no invented company budgets or returns; success criteria are measured against a baseline that the
 * discovery phase establishes; tone = "opportunity to build on".
 */
import type { Bilingual } from "@/lib/i18n/define";

type L = Bilingual<string[]>;

export type RoadmapPhase = {
  id: string;
  horizon: Bilingual;
  title: Bilingual;
  goal: Bilingual;
  deliverables: L;
  roles: L;
  dependencies: L;
  risks: Bilingual<{ risk: string; mitigation: string }[]>;
  success: L;
};

export const ROADMAP: readonly RoadmapPhase[] = [
  {
    id: "discovery",
    horizon: { th: "วันที่ 1–30", en: "Days 1–30" },
    title: { th: "ค้นหาข้อเท็จจริง (Discovery)", en: "Discovery" },
    goal: {
      th: "ทำความเข้าใจระบบ ผู้เกี่ยวข้อง ข้อมูลที่มีอยู่ และข้อจำกัด IT/OT แล้วเลือกโครงการนำร่องหนึ่งโครงการที่วัดผลได้",
      en: "Understand existing systems, stakeholders, available data and IT/OT constraints, then choose one measurable pilot.",
    },
    deliverables: {
      th: ["แผนที่ระบบและแหล่งข้อมูลปัจจุบัน", "สรุปสัมภาษณ์ผู้เกี่ยวข้องและประเด็นที่ทีมอยากพัฒนา", "ค่า KPI ตั้งต้น (baseline) ที่ตกลงร่วมกัน", "เกณฑ์เลือกและข้อเสนอโครงการนำร่อง"],
      en: ["Map of current systems and data sources", "Stakeholder interview summary and improvement themes", "Agreed KPI baseline", "Pilot selection criteria and pilot proposal"],
    },
    roles: {
      th: ["Technical Project Manager", "ผู้แทนฝ่ายผลิตและซ่อมบำรุง", "IT/OT", "ผู้สนับสนุนระดับผู้บริหาร"],
      en: ["Technical Project Manager", "Production & maintenance representatives", "IT/OT", "Executive sponsor"],
    },
    dependencies: {
      th: ["การเข้าถึงผู้เกี่ยวข้องและหน้างาน", "ข้อตกลงด้านการรักษาความลับของข้อมูล"],
      en: ["Access to stakeholders and the site", "Data confidentiality agreement"],
    },
    risks: {
      th: [
        { risk: "คุณภาพหรือความครบถ้วนของข้อมูลต่ำกว่าที่คาด", mitigation: "ประเมินคุณภาพข้อมูลก่อนเลือกโครงการนำร่อง" },
        { risk: "ความคาดหวังไม่ตรงกัน", mitigation: "เขียนขอบเขตและเกณฑ์ความสำเร็จให้ลงนามร่วมกัน" },
      ],
      en: [
        { risk: "Data quality or completeness lower than expected", mitigation: "Assess data quality before choosing the pilot" },
        { risk: "Misaligned expectations", mitigation: "Written scope and success criteria signed off jointly" },
      ],
    },
    success: {
      th: ["ผู้สนับสนุนอนุมัติโครงการนำร่องและ baseline", "ทราบแหล่งข้อมูลและเจ้าของข้อมูลของโครงการนำร่องครบ"],
      en: ["Sponsor approves the pilot and the baseline", "Every pilot data source and owner identified"],
    },
  },
  {
    id: "pilot-build",
    horizon: { th: "วันที่ 31–60", en: "Days 31–60" },
    title: { th: "พัฒนาโครงการนำร่อง", en: "Pilot development" },
    goal: {
      th: "สร้างแดชบอร์ดและโมเดลบนข้อมูลย้อนหลังที่ได้รับอนุญาต พร้อมแผนการเชื่อมต่อแบบอ่านอย่างเดียว",
      en: "Build the dashboard and models on authorised historical data, with a read-only integration plan.",
    },
    deliverables: {
      th: ["แผนการเชื่อมต่อข้อมูล (อ่านอย่างเดียวต่อระบบ OT)", "แดชบอร์ดนำร่อง", "โมเดลบนข้อมูลย้อนหลังพร้อมการเทียบ baseline", "รายงานการตรวจสอบความถูกต้องกับผู้ใช้"],
      en: ["Integration plan (read-only towards OT)", "Pilot dashboard", "Models on historical data with baseline comparison", "Validation report with users"],
    },
    roles: {
      th: ["Technical Project Manager", "Data/ML engineer", "Full-stack developer", "ผู้ใช้หลักจากหน้างาน"],
      en: ["Technical Project Manager", "Data/ML engineer", "Full-stack developer", "Key users from operations"],
    },
    dependencies: { th: ["ผลจากช่วงค้นหาข้อเท็จจริง", "การเข้าถึงข้อมูลย้อนหลัง"], en: ["Discovery outputs", "Access to historical data"] },
    risks: {
      th: [
        { risk: "โมเดลไม่ดีกว่า baseline", mitigation: "รายงานตามจริง และใช้ baseline หรือกฎที่เรียบง่ายกว่า" },
        { risk: "การเชื่อมต่อใช้เวลานานกว่าแผน", mitigation: "เริ่มจากไฟล์ส่งออกตามรอบ ก่อนเชื่อมต่อแบบอัตโนมัติ" },
      ],
      en: [
        { risk: "Models do not beat the baseline", mitigation: "Report it truthfully and use the simpler baseline or rules" },
        { risk: "Integration takes longer than planned", mitigation: "Start with periodic exports before automated connections" },
      ],
    },
    success: {
      th: ["ผู้ใช้หลักยืนยันว่าตัวเลขตรงกับแหล่งข้อมูลต้นทาง", "รายงานผลโมเดลเทียบ baseline บนช่วงเวลาทดสอบที่แยกไว้"],
      en: ["Key users confirm figures match the source systems", "Model results reported against the baseline on a held-out period"],
    },
  },
  {
    id: "pilot-eval",
    horizon: { th: "วันที่ 61–90", en: "Days 61–90" },
    title: { th: "ประเมินผลโครงการนำร่อง", en: "Pilot evaluation" },
    goal: {
      th: "ทดลองใช้งานจริงแบบจำกัด เก็บความคิดเห็น วัด KPI เทียบ baseline และเตรียมแผนขยายผล",
      en: "Run a limited live trial, collect feedback, measure KPIs against the baseline and prepare a scale-up plan.",
    },
    deliverables: {
      th: ["รายงานการทดลองใช้งาน", "ผลการวัด KPI เทียบ baseline", "การทบทวนความปลอดภัยและความเสถียร", "การประเมินผลตอบแทนจากข้อมูลจริง", "แผนขยายผล"],
      en: ["Trial report", "KPI results against the baseline", "Security and reliability review", "Return assessment from real data", "Scale-up plan"],
    },
    roles: {
      th: ["Technical Project Manager", "ผู้ใช้หลัก", "IT security", "ฝ่ายการเงิน (สำหรับการประเมินผลตอบแทน)"],
      en: ["Technical Project Manager", "Key users", "IT security", "Finance (for the return assessment)"],
    },
    dependencies: { th: ["โครงการนำร่องผ่านการตรวจสอบความถูกต้อง", "ความพร้อมของผู้ใช้"], en: ["Validated pilot", "User availability"] },
    risks: {
      th: [
        { risk: "ผลไม่ชัดเจนในช่วงเวลาสั้น", mitigation: "กำหนดตัวชี้วัดนำ (leading indicators) และขยายช่วงทดลองหากจำเป็น" },
        { risk: "การยอมรับของผู้ใช้ต่ำ", mitigation: "ปรับตามความคิดเห็นทุกสัปดาห์ และให้ผู้ใช้มีส่วนออกแบบ" },
      ],
      en: [
        { risk: "Results unclear over a short period", mitigation: "Define leading indicators and extend the trial if needed" },
        { risk: "Low user adoption", mitigation: "Weekly feedback-driven changes and co-design with users" },
      ],
    },
    success: {
      th: ["ตัดสินใจขยายผล/ปรับ/หยุดได้จากหลักฐาน", "ไม่มีประเด็นความปลอดภัยระดับสูงค้างอยู่"],
      en: ["A go / adjust / stop decision made on evidence", "No open high-severity security findings"],
    },
  },
  {
    id: "year-1",
    horizon: { th: "ปีที่ 1", en: "Year 1" },
    title: { th: "ปฏิบัติการดิจิทัล", en: "Operational digitalisation" },
    goal: {
      th: "ขยายสิ่งที่พิสูจน์แล้วจากโครงการนำร่อง สร้างแพลตฟอร์มข้อมูลร่วม และนิยาม KPI มาตรฐาน",
      en: "Scale what the pilot proved, build a shared data platform and standard KPI definitions.",
    },
    deliverables: {
      th: ["แพลตฟอร์มข้อมูลการผลิตร่วม", "แดชบอร์ดผู้บริหารและหน้างาน", "ขั้นตอนใบสั่งงานที่เชื่อมกับระบบเดิม", "แนวทางกำกับดูแลข้อมูล"],
      en: ["Shared production data platform", "Executive and floor dashboards", "Work-order flow connected to existing systems", "Data governance guidelines"],
    },
    roles: { th: ["ทีมแพลตฟอร์มข้อมูล", "ทีมพัฒนาแอปพลิเคชัน", "ผู้ใช้หลักแต่ละฝ่าย"], en: ["Data platform team", "Application team", "Key users per department"] },
    dependencies: { th: ["ผลประเมินโครงการนำร่อง", "การอนุมัติงบประมาณตามกระบวนการของบริษัท"], en: ["Pilot evaluation", "Budget approval through the company's own process"] },
    risks: {
      th: [{ risk: "ขยายเร็วเกินความพร้อมของข้อมูล", mitigation: "ขยายทีละพื้นที่ ตามเกณฑ์ความพร้อมข้อมูล" }],
      en: [{ risk: "Scaling faster than data readiness", mitigation: "Expand area by area against data-readiness criteria" }],
    },
    success: {
      th: ["KPI หลักมาจากแหล่งเดียวที่ตรวจสอบได้", "ผู้ใช้ใช้งานแดชบอร์ดในการประชุมประจำ"],
      en: ["Core KPIs come from one verifiable source", "Dashboards used in routine meetings"],
    },
  },
  {
    id: "year-2",
    horizon: { th: "ปีที่ 2", en: "Year 2" },
    title: { th: "AI และ Industrial IoT", en: "AI & Industrial IoT" },
    goal: {
      th: "เพิ่มการตรวจวัดสภาพเครื่องจักรที่จำเป็น โมเดลพยากรณ์ที่ผ่านการสอบเทียบกับข้อมูลจริง และผู้ช่วย AI ที่ควบคุมสิทธิ์",
      en: "Add needed condition monitoring, forecasting models calibrated on real data and a permission-controlled AI copilot.",
    },
    deliverables: {
      th: ["การเชื่อมต่อ historian/OPC UA แบบอ่านอย่างเดียว", "โมเดลที่มี model card และการติดตามประสิทธิภาพ", "ผู้ช่วย AI พร้อมแหล่งอ้างอิง"],
      en: ["Read-only historian / OPC UA connection", "Models with model cards and performance monitoring", "AI copilot with citations"],
    },
    roles: { th: ["ML engineer", "OT engineer", "ทีมความปลอดภัยไซเบอร์"], en: ["ML engineer", "OT engineer", "Cybersecurity team"] },
    dependencies: { th: ["แพลตฟอร์มข้อมูลจากปีที่ 1", "การแบ่งเครือข่าย IT/OT"], en: ["Year-1 data platform", "IT/OT network segmentation"] },
    risks: {
      th: [{ risk: "ความเสี่ยงไซเบอร์จากการเชื่อมต่อ OT", mitigation: "อ่านอย่างเดียว ผ่าน DMZ/historian replica ไม่เปิด PLC สู่อินเทอร์เน็ต" }],
      en: [{ risk: "Cyber risk from OT connectivity", mitigation: "Read-only through a DMZ / historian replica; never expose PLCs to the internet" }],
    },
    success: {
      th: ["โมเดลรายงานผลบนข้อมูลจริงเทียบ baseline", "AI ไม่ควบคุมเครื่องจักร และทุกการเปลี่ยนแปลงข้อมูลมีมนุษย์ยืนยัน"],
      en: ["Models reported on real data against baselines", "AI never controls machines; every record change is human-confirmed"],
    },
  },
  {
    id: "year-3",
    horizon: { th: "ปีที่ 3", en: "Year 3" },
    title: { th: "ปฏิบัติการอัจฉริยะระดับกลุ่ม", en: "Group-wide intelligent operations" },
    goal: {
      th: "นำรูปแบบที่ได้ผลไปใช้ข้ามธุรกิจที่เหมาะสม ด้วยมาตรฐานข้อมูลและการกำกับดูแลร่วม",
      en: "Reuse proven patterns across suitable business units with shared data standards and governance.",
    },
    deliverables: {
      th: ["มาตรฐานข้อมูลและ API ระดับกลุ่ม", "แคตตาล็อกโมเดลและกระบวนการ MLOps", "ศูนย์ความเชี่ยวชาญภายใน"],
      en: ["Group-level data and API standards", "Model catalogue and MLOps process", "Internal centre of excellence"],
    },
    roles: { th: ["ผู้นำด้านข้อมูล/ดิจิทัล", "ทีมแพลตฟอร์มกลาง", "ผู้แทนแต่ละธุรกิจ"], en: ["Data/digital leadership", "Central platform team", "Business-unit representatives"] },
    dependencies: { th: ["ผลลัพธ์ที่พิสูจน์แล้วจากปีที่ 1–2"], en: ["Proven results from years 1–2"] },
    risks: {
      th: [{ risk: "ความต้องการของแต่ละธุรกิจต่างกัน", mitigation: "แกนกลางร่วม + โมดูลเฉพาะธุรกิจ" }],
      en: [{ risk: "Business units have different needs", mitigation: "Shared core plus business-specific modules" }],
    },
    success: {
      th: ["รูปแบบที่ใช้ซ้ำได้อย่างน้อยหนึ่งรูปแบบในธุรกิจที่สอง", "มีทีมภายในดูแลระบบได้เอง"],
      en: ["At least one pattern reused in a second business unit", "Internal team able to run the platform"],
    },
  },
];
