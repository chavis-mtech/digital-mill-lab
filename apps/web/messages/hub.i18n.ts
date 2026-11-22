import { defineMessages } from "@/lib/i18n/define";

export default defineMessages({
  th: {
    title: "ศูนย์รวมเดโม",
    description:
      "เลือกโมดูลเพื่อสำรวจ ทุกหน้าใช้ข้อมูลสังเคราะห์ชุดเดียวกัน ณ เวลาสาธิตเดียวกัน ป้ายสถานะบอกระดับความพร้อมจริงของแต่ละส่วน",
    tourTitle: "ยังไม่แน่ใจว่าจะเริ่มตรงไหน?",
    tourBody: "ทัวร์ 7 ขั้นตอนพาดูตั้งแต่ตรวจพบ OER ลดลง จนถึงการสร้างใบสั่งงานและการประเมินผลกระทบ",
    systemTitle: "สถานะระบบ",
    systemBody: "ตรวจสอบสด ๆ จาก GET /api/v1/meta",
    honestyTitle: "ความโปร่งใส",
    honestyBody:
      "หน้าที่ยังไม่ถูกสร้างจะแสดงว่า “ยังไม่ถูกสร้าง” แทนการแสดงตัวเลขสมมติ และ endpoint ที่ยังเป็น stub จะแสดงผู้รับผิดชอบและรหัสงาน",
    concepts: "แนวคิด P2 (ต้นแบบเท่านั้น ไม่ใช่ระบบใช้งานจริง)",
    conceptsNote: "แสดงเพื่อสื่อทิศทางในอนาคต แต่ละรายการจะถูกติดป้าย “ต้นแบบ” เสมอ",
    open: "เปิดโมดูล",
    platform: "แพลตฟอร์ม",
  },
  en: {
    title: "Demo hub",
    description:
      "Pick a module to explore. Every page reads the same synthetic dataset at the same demo clock; status chips state each part's real maturity.",
    tourTitle: "Not sure where to start?",
    tourBody: "A 7-step tour from an OER drop being detected to a work order and an impact estimate.",
    systemTitle: "System status",
    systemBody: "Checked live from GET /api/v1/meta",
    honestyTitle: "Transparency",
    honestyBody:
      "Views that are not built yet say so instead of showing made-up numbers, and stub endpoints show their owner and task id.",
    concepts: "P2 concepts (prototype only, never production)",
    conceptsNote: "Shown to signal future direction; each will always be labelled as a prototype.",
    open: "Open module",
    platform: "Platform",
  },
});
