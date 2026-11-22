/**
 * Developer profile (DML-092).
 *
 * SOURCE RULE (SPEC §0 rule 9): every fact below comes ONLY from the applicant's own public GitHub profile
 * README (github.com/chavis-mtech, README "Last Updated: March 2025"). Nothing is invented. Anything not in
 * that README is a visible placeholder listed in `PLACEHOLDERS` — the applicant fills those in.
 * The target position is the owner's stated intent (SPEC §0).
 */
import type { Bilingual } from "@/lib/i18n/define";

export const DEVELOPER = {
  source: { label: "GitHub profile README (chavis-mtech)", url: "https://github.com/chavis-mtech", lastUpdated: "March 2025" },
  /** The README gives the Latin spelling only; a Thai spelling is a placeholder (see PLACEHOLDERS.name_th). */
  name: "Chavis Keawrat",
  currentTitle: "Full-Stack Developer",
  positionSought: "Technical Project Manager (Software & AI)",
  summary: {
    en: "Full-Stack Developer passionate about solving complex problems and building reliable systems. Experienced in developing high-accuracy Payroll systems and Real-time POS systems, with a strong focus on clean code, performance, and continuous learning.",
    th: "นักพัฒนา Full-Stack ที่สนใจการแก้ปัญหาซับซ้อนและการสร้างระบบที่เชื่อถือได้ มีประสบการณ์พัฒนาระบบเงินเดือน (Payroll) ที่ต้องการความแม่นยำสูง และระบบ POS แบบเรียลไทม์ ให้ความสำคัญกับโค้ดที่สะอาด ประสิทธิภาพ และการเรียนรู้อย่างต่อเนื่อง",
  } as Bilingual,
  experience: [
    {
      period: "2024 – Present",
      company: "Bookengine.com",
      projects: [
        {
          name: "TITANSJET – POS System",
          stack: ["CodeIgniter", "Next.js", "Socket.io"],
          points: {
            en: [
              "Built a real-time order management system using Socket.io to synchronize data between order points and kitchen displays",
              "Developed a Task Tracker supporting multi-level task assignment with Kanban board workflow management",
            ],
            th: [
              "พัฒนาระบบจัดการคำสั่งซื้อแบบเรียลไทม์ด้วย Socket.io เพื่อซิงก์ข้อมูลระหว่างจุดรับออร์เดอร์และจอแสดงผลในครัว",
              "พัฒนา Task Tracker ที่รองรับการมอบหมายงานหลายระดับ พร้อมการจัดการเวิร์กโฟลว์แบบ Kanban board",
            ],
          } as Bilingual<string[]>,
        },
        {
          name: "Livepocket – HRM & Payroll System",
          stack: ["Laravel", "Vue.js", "Firebase"],
          points: {
            en: [
              "Designed and implemented validation logic for complex OT calculation rules, fully tested with PHPUnit",
              "Developed a document management system using PdfMe with multi-level approval workflows and file compression via Pako",
              "Implemented secure salary adjustment features with encryption and decryption",
              "Integrated real-time notification delivery using Firebase Cloud Messaging (FCM)",
            ],
            th: [
              "ออกแบบและพัฒนาตรรกะตรวจสอบกฎการคำนวณค่าล่วงเวลา (OT) ที่ซับซ้อน ทดสอบครบถ้วนด้วย PHPUnit",
              "พัฒนาระบบจัดการเอกสารด้วย PdfMe พร้อมเวิร์กโฟลว์อนุมัติหลายระดับ และบีบอัดไฟล์ด้วย Pako",
              "พัฒนาฟีเจอร์ปรับเงินเดือนอย่างปลอดภัยด้วยการเข้ารหัสและถอดรหัส",
              "เชื่อมต่อการแจ้งเตือนแบบเรียลไทม์ด้วย Firebase Cloud Messaging (FCM)",
            ],
          } as Bilingual<string[]>,
        },
      ],
    },
  ],
  skills: {
    Frontend: ["Angular", "Vue.js", "SolidJS"],
    Backend: [".NET", "Rust", "Python", "Laravel", "CodeIgniter", "NestJS"],
    Database: ["MariaDB", "PostgreSQL", "MongoDB"],
    "Tools & Platforms": ["Ubuntu", "Git", "Docker", "JetBrains IDEs"],
  } as Record<string, string[]>,
  education: { institution: "Thaksin University (TSU)", degree: "Bachelor's Degree in Computer Science" },
  contact: {
    email: "chavis.mtech@gmail.com",
    // Phone deliberately NOT published: it appears in the applicant's own README, but putting it on a public demo is the
    // owner's decision (see the engineering log (kept private)). Add a `phone` field and a row in app/(public)/contact/page.tsx only after approval.
    github: "https://github.com/chavis-mtech",
  },
} as const;

/** Visible placeholders + TODO list for the applicant (not in the README, so not invented). */
export const PLACEHOLDERS: readonly { key: string; label: Bilingual }[] = [
  { key: "photo", label: { th: "รูปโปรไฟล์ (ถ้าต้องการ)", en: "Profile photo (optional)" } },
  { key: "name_th", label: { th: "ชื่อ-นามสกุลภาษาไทย", en: "Name in Thai script" } },
  { key: "pm_experience", label: { th: "ประสบการณ์บริหารโครงการ / ภาวะผู้นำทีม", en: "Project-management / team-leadership experience" } },
  { key: "ai_experience", label: { th: "ประสบการณ์ด้าน AI / ข้อมูล นอกเหนือจากโครงการนี้", en: "AI / data experience beyond this project" } },
  { key: "certifications", label: { th: "ใบรับรอง (ถ้ามี)", en: "Certifications (if any)" } },
  { key: "languages", label: { th: "ระดับภาษา", en: "Language proficiency" } },
  { key: "linkedin", label: { th: "ลิงก์ LinkedIn", en: "LinkedIn URL" } },
  { key: "resume", label: { th: "ไฟล์เรซูเม่ (PDF)", en: "Résumé file (PDF)" } },
  { key: "availability", label: { th: "วันที่เริ่มงานได้ / สถานที่ทำงานที่สะดวก", en: "Availability / preferred work location" } },
];
