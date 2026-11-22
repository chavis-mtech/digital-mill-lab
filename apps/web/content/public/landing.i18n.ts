import { defineMessages } from "@/lib/i18n/define";

/**
 * Landing page copy (SPEC §3). Headline and subtitle are the exact SPEC wording; TH adds a translation.
 * Copy rules (the public-facts research (kept private) §9): "independent concept", "opportunities to build on",
 * never claims about the group's systems or performance.
 */
export default defineMessages({
  th: {
    eyebrow: "แนวคิดอิสระ · ข้อมูลสังเคราะห์ · โรงสกัดน้ำมันปาล์ม",
    headline: "Intelligent Operations for a Smarter Industrial Future",
    headlineTranslation: "ปฏิบัติการอัจฉริยะ เพื่ออนาคตอุตสาหกรรมที่ชาญฉลาดยิ่งขึ้น",
    subtitle:
      "An independent AI-driven industrial transformation concept, exploring how manufacturing intelligence, predictive analytics, and connected operations could create measurable business value.",
    subtitleTranslation:
      "แนวคิดอิสระด้านการเปลี่ยนผ่านอุตสาหกรรมด้วย AI ที่สำรวจว่าข้อมูลอัจฉริยะการผลิต การวิเคราะห์เชิงพยากรณ์ และการเชื่อมโยงงานปฏิบัติการ จะสร้างคุณค่าทางธุรกิจที่วัดผลได้อย่างไร",
    ctaDemo: "สำรวจเดโม",
    ctaTour: "ทดลองชมระบบใน 5 นาที",
    heroNote: "ไม่ใช่ระบบทางการของบริษัทใด ๆ · ไม่มีข้อมูลภายในของบริษัท · ข้อมูลทั้งหมดสร้างขึ้นเพื่อการสาธิต",
    heroFlowLabel: "สายกระบวนการผลิตของโรงสกัดสมมติ “Demo Palm Mill A”",
    heroFlowCaption: "ผังขั้นตอนเท่านั้น — ตัวเลขจริงสังเคราะห์อยู่ในเดโม พร้อมป้ายบอกที่มา",
    overviewKicker: "ภาพรวมโครงการ",
    overviewTitle: "ระบบตัวอย่างที่ทำงานได้จริง ไม่ใช่สไลด์นำเสนอ",
    overviewBody:
      "โครงการนี้สาธิตว่าแพลตฟอร์มข้อมูลอัจฉริยะสำหรับโรงสกัดน้ำมันปาล์มจะทำงานอย่างไร ตั้งแต่ข้อมูลการรับผลปาล์ม ไปจนถึงการตัดสินใจของผู้บริหาร ตัวเลขคำนวณจากข้อมูลสังเคราะห์ที่สร้างแบบกำหนดได้ และตัวเลขสำคัญมีป้ายบอกที่มา",
    pillars: {
      process: { title: "เข้าใจกระบวนการ", body: "จากผลปาล์มสดถึง CPO: สมดุลมวล OER/KER ไอน้ำ และความสัมพันธ์ของผลพลอยได้ที่ถูกต้องตามหลักวิศวกรรม" },
      ai: { title: "AI ที่ตรวจสอบได้", body: "โมเดลแบบคลาสสิกเทียบกับ baseline แบ่งข้อมูลตามเวลา รายงานผลตามที่วัดได้จริง และ AI ให้คำแนะนำเท่านั้น" },
      architecture: { title: "สถาปัตยกรรมองค์กร", body: "Modular monolith, API-first, สัญญาข้อมูลแบบมีชนิด, audit log และสัญญาการเชื่อมต่อระบบในอนาคต" },
      value: { title: "คุณค่าทางธุรกิจ", body: "เชื่อมสัญญาณในโรงงานกับต้นทุน ความเสี่ยง และผลผลิต ผ่านสูตรและสมมติฐานที่ปรับได้และเห็นได้ชัด" },
      leadership: { title: "ภาวะผู้นำทางเทคนิค", body: "แผนงาน 30/60/90 วัน และ 1–3 ปี backlog ความเสี่ยง และเกณฑ์ความสำเร็จที่วัดผลได้" },
    },
    challengesKicker: "โอกาสในการต่อยอด",
    challengesTitle: "จุดที่ข้อมูลอัจฉริยะสามารถเสริมงานที่มีอยู่",
    challengesBody:
      "โรงสกัดทั่วไปมีความรู้และระบบงานอยู่แล้ว แนวคิดนี้มองหาโอกาสที่ชั้นข้อมูลและ AI จะช่วยต่อยอด โดยไม่ได้อ้างว่าระบบใดของบริษัทใดขาดหายหรือไม่ดี",
    solutionsKicker: "โซลูชัน AI",
    solutionsTitle: "โมดูลหลัก พร้อมป้ายระดับความพร้อมตามจริง",
    solutionsBody: "ป้ายสถานะมาจากแหล่งข้อมูลเดียวในระบบ และเปลี่ยนเป็น “ใช้งานได้” เฉพาะเมื่อมีหลักฐานการทดสอบ",
    demoTitle: "ลองใช้เดโมได้ทันที ไม่ต้องสมัคร",
    demoBody:
      "เลือกสถานการณ์ เช่น “เครื่องหีบสั่นผิดปกติ” แล้วดูผลกระทบที่สอดคล้องกันทั้งผังกระบวนการ ความผิดปกติ การซ่อมบำรุง และผลกระทบทางธุรกิจ บทบาทผู้ใช้เป็นมุมมองจำลอง ไม่ใช่การยืนยันตัวตน",
    architectureKicker: "สถาปัตยกรรมทางเทคนิค",
    architectureTitle: "ตัวเลขทุกตัวมาจากแหล่งความจริงเดียว",
    architectureBody:
      "Next.js เป็นเพียงชั้นแสดงผล ตรรกะทางธุรกิจ การวิเคราะห์ และ AI ทั้งหมดอยู่ในบริการ Python เดียว สัญญา OpenAPI สร้างชนิดข้อมูล TypeScript ให้หน้าเว็บโดยอัตโนมัติ",
    roadmapKicker: "แผนการดำเนินงาน",
    roadmapTitle: "เริ่มจากการค้นหาข้อเท็จจริง แล้วค่อยขยายผล",
    roadmapBody: "แผนที่เสนอเริ่มด้วยการทำความเข้าใจระบบ ผู้เกี่ยวข้อง และข้อมูลที่มีอยู่ ก่อนเลือกโครงการนำร่องที่วัดผลได้",
    developerKicker: "เกี่ยวกับผู้พัฒนา",
    developerTitle: "สร้างโดยผู้สมัครตำแหน่ง Technical Project Manager (Software & AI)",
    developerBody: "ผลงานนี้จัดทำขึ้นเพื่อเสนอแนวทางการทำงานระยะยาวร่วมกับทีมที่มีอยู่ ข้อมูลประวัติมาจาก GitHub profile ของผู้สมัครเท่านั้น",
    seeAll: "ดูทั้งหมด",
    readMore: "อ่านต่อ",
    viewArchitecture: "ดูสถาปัตยกรรม",
    viewRoadmap: "ดูแผนงาน",
    viewDeveloper: "ดูโปรไฟล์ผู้พัฒนา",
    contact: "ติดต่อ",
  },
  en: {
    eyebrow: "Independent concept · Synthetic data · Palm oil mill",
    headline: "Intelligent Operations for a Smarter Industrial Future",
    headlineTranslation: "Intelligent Operations & AI Transformation for palm oil manufacturing",
    subtitle:
      "An independent AI-driven industrial transformation concept, exploring how manufacturing intelligence, predictive analytics, and connected operations could create measurable business value.",
    subtitleTranslation: "A working, testable demo — all data is synthetic and key figures carry a provenance label.",
    ctaDemo: "Explore live demo",
    ctaTour: "Take the 5-minute tour",
    heroNote: "Not an official system of any company · No internal company data · All data generated for demonstration",
    heroFlowLabel: "Process line of the fictional “Demo Palm Mill A”",
    heroFlowCaption: "Process map only — the synthetic numbers live in the demo, each with a provenance label",
    overviewKicker: "Project overview",
    overviewTitle: "A working reference system, not a slide deck",
    overviewBody:
      "This project demonstrates how an industrial intelligence platform for a palm oil mill could work, from fresh fruit bunch reception to executive decisions. Figures are computed from deterministic synthetic data, and key figures carry a provenance label.",
    pillars: {
      process: { title: "Process understanding", body: "From FFB to CPO: mass balance, OER/KER, steam and by-product relationships that respect the engineering." },
      ai: { title: "Verifiable AI", body: "Classical models against naive baselines, temporal splits, metrics reported as measured — and AI that only advises." },
      architecture: { title: "Enterprise architecture", body: "Modular monolith, API-first, typed data contracts, audit log and future integration contracts." },
      value: { title: "Business value", body: "Plant signals linked to cost, risk and output through visible formulas and adjustable assumptions." },
      leadership: { title: "Technical leadership", body: "30/60/90-day and 1–3 year roadmap, backlog, risks and measurable success criteria." },
    },
    challengesKicker: "Opportunities to build on",
    challengesTitle: "Where an intelligence layer could complement existing work",
    challengesBody:
      "Mills already run on deep expertise and established systems. This concept looks for places where a data and AI layer could build on them — it does not claim that any company's systems are missing or inadequate.",
    solutionsKicker: "AI solutions",
    solutionsTitle: "Core modules, with honest maturity labels",
    solutionsBody: "Status chips come from a single source in the codebase and only turn “Implemented” once test evidence exists.",
    demoTitle: "Try the demo now — no sign-up",
    demoBody:
      "Pick a scenario such as “Press vibration anomaly” and follow its consistent effect across the process flow, anomaly detection, maintenance and business impact. Roles are simulated viewpoints, not authentication.",
    architectureKicker: "Technical architecture",
    architectureTitle: "Every number has one source of truth",
    architectureBody:
      "Next.js only renders. All business rules, analytics and AI live in one Python service; the OpenAPI contract generates the TypeScript types the web app is checked against.",
    roadmapKicker: "Implementation roadmap",
    roadmapTitle: "Discover first, then scale what works",
    roadmapBody: "The proposed plan starts by understanding existing systems, stakeholders and data before choosing a measurable pilot.",
    developerKicker: "About the developer",
    developerTitle: "Built by an applicant for Technical Project Manager (Software & AI)",
    developerBody: "Prepared to propose long-term work alongside the existing team. Profile facts come only from the applicant's own GitHub profile.",
    seeAll: "See all",
    readMore: "Read more",
    viewArchitecture: "View architecture",
    viewRoadmap: "View roadmap",
    viewDeveloper: "View developer profile",
    contact: "Contact",
  },
});
