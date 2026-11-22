/**
 * Business opportunities — framed as "opportunities to build on" (SPEC §13, PUBLIC_FACTS §9).
 * Every item carries a fact tag (SPEC §0 taxonomy). No claim about any real company's systems or results.
 */
import type { Bilingual } from "@/lib/i18n/define";
import type { FeatureKey } from "@/content/status";
import type { Schema } from "@dml/contracts";

export type Opportunity = {
  id: string;
  icon: "gauge" | "wrench" | "truck" | "zap" | "git-branch" | "bot";
  title: Bilingual;
  /** What the opportunity is. */
  summary: Bilingual;
  /** Which SPEC §1 value question it answers. */
  value: Bilingual;
  /** What evidence a real plant would need before claiming a benefit. */
  evidenceNeeded: Bilingual;
  /** What a real deployment would need. */
  realPlantNeeds: Bilingual;
  tag: Schema<"FactTag">;
  feature: FeatureKey;
  demoRoute: string;
};

export const OPPORTUNITIES: readonly Opportunity[] = [
  {
    id: "decision-visibility",
    icon: "gauge",
    title: { th: "มุมมองเดียวสำหรับการตัดสินใจประจำวัน", en: "One view for daily decisions" },
    summary: {
      th: "รวม KPI สำคัญของโรงสกัด (FFB, OER, KER, การหยุดเครื่อง, พลังงานต่อตัน, คิวรถ) ไว้ในหน้าจอเดียว พร้อมเทียบช่วงก่อนหน้าและบอกว่าทีมใดควรตรวจก่อน",
      en: "Bring the key mill KPIs (FFB, OER, KER, downtime, energy per tonne, truck queue) into one view, compared with the previous period and showing which team should look first.",
    },
    value: { th: "ช่วยให้ผู้บริหารตัดสินใจได้เร็วขึ้นและลดงานรวบรวมรายงานซ้ำซ้อน", en: "Faster executive decisions and less duplicate report compilation." },
    evidenceNeeded: {
      th: "เวลาที่ใช้จัดทำรายงานในปัจจุบัน และความถี่ที่ข้อมูลไม่ตรงกันระหว่างหน่วยงาน (วัดในช่วงค้นหาข้อเท็จจริง)",
      en: "Current reporting effort and how often figures disagree between departments (measured during discovery).",
    },
    realPlantNeeds: {
      th: "นิยาม KPI ที่ตกลงร่วมกัน สิทธิ์เข้าถึงข้อมูลการผลิตและห้องแล็บ และเจ้าของข้อมูลที่ชัดเจน",
      en: "Agreed KPI definitions, authorised access to production and lab data, and clear data owners.",
    },
    tag: "proposed_future_capability",
    feature: "executive_control_tower",
    demoRoute: "/demo/executive",
  },
  {
    id: "condition-based-maintenance",
    icon: "wrench",
    title: { th: "ต่อยอดงานซ่อมบำรุงสู่การดูแลตามสภาพเครื่อง", en: "Extend maintenance towards condition-based care" },
    summary: {
      th: "ใช้แนวโน้มการสั่นสะเทือน อุณหภูมิ และกระแสไฟของเครื่องหีบ เครื่องย่อย และปั๊ม เพื่อจัดลำดับการตรวจสอบก่อนเกิดการหยุดเครื่องโดยไม่ได้วางแผน",
      en: "Use vibration, temperature and current trends on presses, digesters and pumps to prioritise inspections before unplanned stops.",
    },
    value: { th: "ลดความเสี่ยงการหยุดเครื่องและการสูญเสียน้ำมันจากเครื่องที่สึกหรอ", en: "Lower downtime risk and oil losses from worn equipment." },
    evidenceNeeded: {
      th: "ประวัติการเสียและการซ่อมจริง เพื่อสอบเทียบคะแนนความเสี่ยง (ในเดโมเป็นเพียงการจัดลำดับเชิงเปรียบเทียบ)",
      en: "Real failure and repair history to calibrate risk scores (in the demo they are relative rankings only).",
    },
    realPlantNeeds: {
      th: "เซนเซอร์หรือ historian ที่มีอยู่ (อ่านอย่างเดียว) รหัสเครื่องจักรที่ตรงกับระบบซ่อมบำรุง และขั้นตอนอนุมัติโดยวิศวกร",
      en: "Existing sensors or historian (read-only), equipment codes aligned with the maintenance system, and engineer approval steps.",
    },
    tag: "industry_practice",
    feature: "predictive_maintenance",
    demoRoute: "/demo/maintenance",
  },
  {
    id: "weighbridge-flow",
    icon: "truck",
    title: { th: "การไหลของรถบรรทุกช่วงผลผลิตสูง", en: "Truck flow in peak season" },
    summary: {
      th: "ใช้ข้อมูลตาชั่งและเวลาเข้าคิวเพื่อพยากรณ์เวลารอ และทดลองการจัดช่วงเวลารับผลปาล์มแบบจำลองเทียบกับการเข้าคิวตามลำดับ",
      en: "Use weighbridge and queue timestamps to predict waiting time and simulate slot scheduling against first-come-first-served.",
    },
    value: {
      th: "ลดเวลารอซึ่งเกี่ยวข้องกับคุณภาพผลปาล์ม (แนวปฏิบัติคือแปรรูปภายในประมาณ 24 ชม. หลังเก็บเกี่ยว)",
      en: "Shorter waits, which matter for fruit quality (practice is to process within about 24 h of harvest).",
    },
    evidenceNeeded: { th: "บันทึกเวลาเข้า-ออกจริงของรถในช่วงพีค", en: "Real arrival/exit timestamps during peak weeks." },
    realPlantNeeds: {
      th: "การส่งออกข้อมูลจากซอฟต์แวร์ตาชั่ง ความยินยอมของผู้ส่งผลปาล์ม และการทบทวนด้านความเป็นส่วนตัว",
      en: "Export from the weighbridge software, supplier consent and a privacy review.",
    },
    tag: "industry_practice",
    feature: "logistics",
    demoRoute: "/demo/logistics",
  },
  {
    id: "energy-per-tonne",
    icon: "zap",
    title: { th: "มองเห็นพลังงานต่อตันผลปาล์ม", en: "Energy-per-tonne visibility" },
    summary: {
      th: "เทียบการใช้ไฟฟ้า ไอน้ำ และน้ำกับปริมาณการผลิต เพื่อหาช่วงที่ใช้พลังงานสูงเกินสัดส่วน เช่น การเดินเครื่องเปล่า",
      en: "Compare electricity, steam and water against throughput to spot disproportionate use, such as idle running.",
    },
    value: { th: "ลดต้นทุนพลังงานต่อหน่วย โดยแสดงข้อจำกัดของการวิเคราะห์ชัดเจน", en: "Lower unit energy cost, with the analysis limits stated plainly." },
    evidenceNeeded: { th: "มิเตอร์ย่อยตามพื้นที่ และข้อมูลเชื้อเพลิงชีวมวลที่ใช้จริง", en: "Area sub-metering and actual biomass fuel data." },
    realPlantNeeds: {
      th: "จุดวัดพลังงานที่เชื่อถือได้ และความเข้าใจว่าโรงสกัดส่วนใหญ่ผลิตพลังงานใช้เองจากเส้นใยและกะลา",
      en: "Reliable metering points and recognition that most mills self-generate energy from fibre and shell.",
    },
    tag: "industry_practice",
    feature: "energy",
    demoRoute: "/demo/energy",
  },
  {
    id: "traceability-readiness",
    icon: "git-branch",
    title: { th: "ความพร้อมด้านการตรวจสอบย้อนกลับ", en: "Traceability readiness" },
    summary: {
      th: "เชื่อมผู้ส่ง การส่งมอบ ล็อต FFB ล็อตการผลิต และล็อต CPO แบบสมดุลมวล เพื่อรองรับการตรวจประเมินด้านความยั่งยืน (เป็นแบบร่างข้อมูล ไม่ใช่การรับรอง)",
      en: "Link supplier, delivery, FFB batch, processing batch and CPO lot using mass balance to support sustainability audits (a data-model sketch, never a certification claim).",
    },
    value: { th: "ลดงานเตรียมเอกสารตรวจประเมิน และตอบคำถามลูกค้าได้เร็วขึ้น", en: "Less audit preparation effort and faster answers to customer questions." },
    evidenceNeeded: { th: "เวลาที่ใช้เตรียมการตรวจประเมินในปัจจุบัน", en: "Current audit preparation effort." },
    realPlantNeeds: {
      th: "ข้อมูลทะเบียนผู้ส่ง เลขที่ตั๋วชั่ง และวิธีการตรวจสอบย้อนกลับที่ตกลงกับผู้ตรวจประเมิน",
      en: "Supplier registry data, ticket numbering and the trace method agreed with auditors.",
    },
    tag: "proposed_future_capability",
    feature: "traceability",
    demoRoute: "/demo/traceability",
  },
  {
    id: "grounded-copilot",
    icon: "bot",
    title: { th: "ผู้ช่วยตอบคำถามจากข้อมูลจริงในระบบ", en: "A copilot grounded in system data" },
    summary: {
      th: "ให้ผู้จัดการถามคำถามด้วยภาษาไทยหรืออังกฤษ แล้วได้คำตอบจากเครื่องมือที่อนุญาตเท่านั้น พร้อมแหล่งอ้างอิง และปฏิเสธเมื่อไม่มีข้อมูล",
      en: "Let managers ask in Thai or English and get answers from allow-listed tools only, with citations, and a refusal when data is missing.",
    },
    value: { th: "ลดเวลาค้นหาข้อมูลข้ามหลายระบบ", en: "Less time searching across several systems." },
    evidenceNeeded: { th: "ชุดคำถามจริงจากผู้ใช้ และเกณฑ์ความถูกต้องของคำตอบ", en: "A real question set from users and answer-accuracy criteria." },
    realPlantNeeds: {
      th: "เอกสารที่ได้รับอนุญาต การควบคุมสิทธิ์ตามบทบาท และการป้องกัน prompt injection",
      en: "Authorised documents, role-based permissions and prompt-injection protection.",
    },
    tag: "proposed_future_capability",
    feature: "copilot",
    demoRoute: "/demo/ai-copilot",
  },
];
