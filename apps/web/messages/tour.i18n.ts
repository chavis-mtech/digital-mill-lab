import { defineMessages } from "@/lib/i18n/define";

export default defineMessages({
  th: {
    start: "ทดลองชมระบบใน 5 นาที",
    title: "ทัวร์นำชมสำหรับผู้บริหาร",
    step: (n: number, total: number) => `ขั้นที่ ${n} จาก ${total}`,
    next: "ถัดไป",
    back: "ย้อนกลับ",
    finish: "จบทัวร์",
    skip: "ข้ามทัวร์",
    notBuilt: "มุมมองนี้ยังไม่ถูกสร้าง",
    notBuiltHint: (owner: string) => `ทีมที่รับผิดชอบ (${owner}) จะทำให้ส่วนที่ไฮไลต์ใช้งานได้จริง`,
    context: "บริบทที่ตั้งค่าให้",
    keyboard: "ใช้ปุ่มลูกศรซ้าย/ขวาเพื่อเปลี่ยนขั้น และ Esc เพื่อออก",
    finishedToast: "จบทัวร์แล้ว — สำรวจเดโมต่อได้ตามสะดวก",
  },
  en: {
    start: "Take the 5-minute tour",
    title: "Guided executive tour",
    step: (n: number, total: number) => `Step ${n} of ${total}`,
    next: "Next",
    back: "Back",
    finish: "Finish tour",
    skip: "Skip tour",
    notBuilt: "This view is not built yet",
    notBuiltHint: (owner: string) => `The owning team (${owner}) will make the highlighted element real.`,
    context: "Context applied",
    keyboard: "Use the left/right arrow keys to change steps and Esc to exit",
    finishedToast: "Tour finished — feel free to keep exploring the demo",
  },
});
