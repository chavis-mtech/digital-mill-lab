/**
 * Developer profile (DML-092).
 *
 * SOURCE RULE (SPEC §0 rule 9): every fact below comes ONLY from the applicant's own sources: the public GitHub profile
 * README (github.com/chavis-mtech, README "Last Updated: November 2026") and the applicant's résumé (November 2026).
 * Nothing is invented. Anything not in those sources is a visible placeholder listed in `PLACEHOLDERS` — the applicant
 * fills those in. Employer internals are deliberately kept at the level of the résumé's summary line.
 * The target position is the owner's stated intent (SPEC §0).
 */
import type { Bilingual } from "@/lib/i18n/define";

interface ExperienceProject {
  name: string;
  stack: readonly string[];
  points: Bilingual<string[]>;
}

interface Experience {
  period: string;
  company: string;
  role: string;
  summary?: Bilingual<string[]>;
  projects: readonly ExperienceProject[];
}

export const DEVELOPER = {
  source: { label: "GitHub profile README (chavis-mtech) and résumé", url: "https://github.com/chavis-mtech", lastUpdated: "November 2026" },
  /** The README gives the Latin spelling only; a Thai spelling is a placeholder (see PLACEHOLDERS.name_th). */
  name: "Chavis Keawrat",
  currentTitle: "Full-Stack Developer",
  positionSought: "Technical Project Manager (Software & AI)",
  summary: {
    en: "Full-Stack Developer working on AI and automation for industrial and HR systems, passionate about solving complex problems and building reliable systems. Experienced in developing high-accuracy Payroll systems, Real-time POS systems and AI-assisted workflows, with a strong focus on data accuracy, traceability, clean code, testing, and continuous learning.",
    th: "นักพัฒนา Full-Stack ที่ทำงานด้าน AI และระบบอัตโนมัติสำหรับงานอุตสาหกรรมและ HR สนใจการแก้ปัญหาซับซ้อนและการสร้างระบบที่เชื่อถือได้ มีประสบการณ์พัฒนาระบบเงินเดือน (Payroll) ที่ต้องการความแม่นยำสูง ระบบ POS แบบเรียลไทม์ และเวิร์กโฟลว์ที่มี AI ช่วย ให้ความสำคัญกับความถูกต้องของข้อมูล การตรวจสอบย้อนหลังได้ โค้ดที่สะอาด การทดสอบ และการเรียนรู้อย่างต่อเนื่อง",
  } as Bilingual,
  experience: [
    {
      period: "Oct 2026 – Present",
      company: "Von Bundit Co., Ltd.",
      role: "Head of AI Department",
      summary: {
        en: [
          "Responsible for AI and automation for HR and factory operations, guided by data accuracy, traceability and a person confirming AI output before it is used",
          "Wrote the company's AI usage policy and AI system register, requiring human review of AI output before use",
        ],
        th: [
          "รับผิดชอบงาน AI และระบบอัตโนมัติด้าน HR และงานโรงงาน โดยยึดความถูกต้องของข้อมูล การตรวจสอบย้อนหลังได้ และให้คนยืนยันผลลัพธ์ของ AI ก่อนนำไปใช้",
          "จัดทำนโยบายการใช้ AI และทะเบียนระบบ AI โดยกำหนดให้คนตรวจผลลัพธ์ของ AI ก่อนนำไปใช้จริง",
        ],
      } as Bilingual<string[]>,
      projects: [],
    },
    {
      period: "Jul 2024 – Oct 2026",
      company: "Bookengine.com (Thailand) Co., Ltd.",
      role: "Programmer",
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
        {
          name: "Across projects",
          stack: ["Vue 3", "Vite", "PHPUnit", "Cypress", "Angular", "NestJS"],
          points: {
            en: [
              "Migrated the front end from Vue 2 to Vue 3 + Vite, and wrote PHPUnit and Cypress tests for the key flows",
              "Advised a team building an ERP on Angular + NestJS on development and code structure",
            ],
            th: [
              "ย้ายหน้าบ้านจาก Vue 2 ไป Vue 3 + Vite และเขียนชุดทดสอบ PHPUnit และ Cypress ให้ flow สำคัญ",
              "ให้คำปรึกษาทีมที่พัฒนาระบบ ERP ด้วย Angular + NestJS ด้านการพัฒนาและโครงสร้างโค้ด",
            ],
          } as Bilingual<string[]>,
        },
      ],
    },
  ] as readonly Experience[],
  skills: {
    Frontend: ["Angular", "Vue.js", "Next.js", "SolidJS"],
    Backend: [".NET", "Rust", "Python", "FastAPI", "Laravel", "CodeIgniter", "NestJS"],
    "AI & Data": ["scikit-learn", "Ollama", "YOLO", "OCR"],
    Database: ["MariaDB", "PostgreSQL", "MongoDB"],
    "Tools & Platforms": ["Ubuntu", "Git", "Docker", "GitHub Actions", "JetBrains IDEs"],
  } as Record<string, string[]>,
  education: { institution: "Thaksin University (TSU)", degree: "Bachelor of Science in Computer Science (2024)" },
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
  { key: "certifications", label: { th: "ใบรับรอง (ถ้ามี)", en: "Certifications (if any)" } },
  { key: "languages", label: { th: "ระดับภาษา", en: "Language proficiency" } },
  { key: "linkedin", label: { th: "ลิงก์ LinkedIn", en: "LinkedIn URL" } },
  { key: "resume", label: { th: "ไฟล์เรซูเม่ (PDF)", en: "Résumé file (PDF)" } },
  { key: "availability", label: { th: "วันที่เริ่มงานได้ / สถานที่ทำงานที่สะดวก", en: "Availability / preferred work location" } },
];
