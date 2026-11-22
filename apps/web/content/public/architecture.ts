/** Content for /technical-architecture — mirrors docs/architecture/SYSTEM_ARCHITECTURE.md and DECISIONS.md. */
import type { Bilingual } from "@/lib/i18n/define";

export const LAYERS: { layer: string; location: string; rule: Bilingual }[] = [
  { layer: "Web", location: "apps/web", rule: { th: "แสดงผล + พร็อกซีบาง ไม่มีสูตรธุรกิจ แสดงป้ายที่มาและสถานะ", en: "Rendering + thin proxy. No business formulas. Shows provenance and status badges." } },
  { layer: "Contract", location: "packages/contracts", rule: { th: "สร้างจาก OpenAPI ห้ามแก้ด้วยมือ", en: "Generated from OpenAPI. Never hand-edited." } },
  { layer: "API routers", location: "app/api/v1/<module>.py", rule: { th: "ตรวจข้อมูลเข้า, DemoContext, สิทธิ์ แล้วเรียกบริการ", en: "Validate input, resolve DemoContext, check permission, call a service." } },
  { layer: "Services", location: "app/services/<module>.py", rule: { th: "กฎธุรกิจและการวิเคราะห์ ไม่อ่านเวลาจริงของเครื่อง", en: "Business rules and analytics; never read wall-clock time for demo data." } },
  { layer: "ML", location: "app/ml/**", rule: { th: "ฝึก/ประเมินแบบออฟไลน์ เทียบ baseline แบ่งตามเวลา", en: "Offline training/evaluation against baselines with temporal splits." } },
  { layer: "Copilot", location: "app/copilot/**", rule: { th: "เรียกบริการผ่านเครื่องมือที่อนุญาตเท่านั้น ไม่มี SQL อิสระ", en: "Calls services through allow-listed tools only; no raw SQL." } },
  { layer: "Seed", location: "app/seed/**", rule: { th: "สร้างข้อมูลสังเคราะห์แบบกำหนดได้ผ่านโมเดลข้อมูล", en: "Deterministic synthetic generator writing through the models." } },
];

export const DECISIONS: { id: string; title: Bilingual; why: Bilingual }[] = [
  { id: "ADR-001", title: { th: "Modular monolith", en: "Modular monolith" }, why: { th: "ขอบเขตโดเมนชัดเจน ดูแลง่าย แยกเป็นบริการภายหลังได้โดยสัญญา API ไม่เปลี่ยน", en: "Clear domain boundaries, simple to operate; a module can be extracted later without changing the API contract." } },
  { id: "ADR-002", title: { th: "ตัวเลขทุกตัวอยู่ใน Python", en: "All numbers live in Python" }, why: { th: "แดชบอร์ด ผู้ช่วย AI และรายงานแสดงตัวเลขเดียวกันเสมอ", en: "Dashboard, copilot and exports always show the same figure." } },
  { id: "ADR-004", title: { th: "OpenAPI → TypeScript", en: "OpenAPI → TypeScript" }, why: { th: "หน้าเว็บถูกตรวจชนิดข้อมูลกับสัญญาจริง", en: "The web app is type-checked against the real contract." } },
  { id: "ADR-005", title: { th: "เล่นซ้ำสถานการณ์ ไม่แก้ข้อมูล", en: "Scenario playback, not data mutation" }, why: { th: "ผู้เยี่ยมชมหลายคนเห็นผลเหมือนกันและสอดคล้องข้ามโมดูล", en: "Many visitors get reproducible, cross-module consistent results." } },
  { id: "ADR-006", title: { th: "แซนด์บ็อกซ์ต่อเซสชัน", en: "Per-session sandbox" }, why: { th: "ใบสั่งงานและการอนุมัติของผู้เยี่ยมชมไม่กระทบกัน", en: "Visitors' work orders and approvals never affect each other." } },
  { id: "ADR-007", title: { th: "บทบาทจำลอง ตรวจสิทธิ์ฝั่งเซิร์ฟเวอร์", en: "Simulated roles, enforced server-side" }, why: { th: "สาธิตการควบคุมสิทธิ์ โดยระบุชัดว่าไม่ใช่การยืนยันตัวตน", en: "Demonstrates authorization while stating it is not authentication." } },
  { id: "ADR-010", title: { th: "Copilot แบบกำหนดได้ + LLM เสริม", en: "Deterministic copilot + optional LLM" }, why: { th: "ทำงานได้โดยไม่ต้องมี API key และ LLM ไม่เข้าถึง SQL", en: "Works without an API key; an LLM never gets SQL access." } },
  { id: "ADR-013", title: { th: "Audit log แบบ hash chain", en: "Hash-chained audit log" }, why: { th: "ตรวจพบการแก้ไขย้อนหลังได้", en: "Tampering with history is detectable." } },
];

export const INTEGRATIONS: { system: string; direction: Bilingual; needs: Bilingual }[] = [
  { system: "ERP / CMMS", direction: { th: "อ่าน + ส่งใบสั่งงานที่ยืนยันแล้ว", en: "Read + confirmed work-order outbox" }, needs: { th: "การแมปรหัสเครื่องจักร ขั้นตอนอนุมัติ", en: "Equipment-code mapping, approval workflow" } },
  { system: "MES", direction: { th: "อ่าน", en: "Read" }, needs: { th: "โมเดลคำสั่งผลิต ปฏิทินกะ", en: "Production order model, shift calendar" } },
  { system: "SCADA / PLC historian", direction: { th: "อ่านอย่างเดียว", en: "Read-only" }, needs: { th: "historian replica ใน DMZ พจนานุกรม tag", en: "Historian replica in a DMZ, tag dictionary" } },
  { system: "OPC UA", direction: { th: "อ่านอย่างเดียว", en: "Read-only" }, needs: { th: "ใบรับรอง ผู้ใช้แบบอ่านอย่างเดียว", en: "Certificates, read-only user" } },
  { system: "MQTT / Sparkplug B", direction: { th: "subscribe เท่านั้น", en: "Subscribe-only" }, needs: { th: "broker, TLS, ACL", en: "Broker, TLS, ACLs" } },
  { system: "Weighbridge", direction: { th: "อ่าน", en: "Read" }, needs: { th: "การส่งออกข้อมูล เลขตั๋ว บันทึกการสอบเทียบ", en: "Export, ticket numbering, calibration records" } },
  { system: "LIMS", direction: { th: "อ่าน", en: "Read" }, needs: { th: "รหัสจุดเก็บตัวอย่าง วิธีทดสอบ หน่วย", en: "Sample-point codes, methods, units" } },
  { system: "GPS / fleet", direction: { th: "อ่าน", en: "Read" }, needs: { th: "ความยินยอมและการทบทวนความเป็นส่วนตัว", en: "Consent and privacy review" } },
  { system: "Accounting / HR", direction: { th: "อ่าน (สรุปรวม)", en: "Read (aggregated)" }, needs: { th: "ข้อมูลรวมเท่านั้น ไม่มีข้อมูลส่วนบุคคล", en: "Aggregated only, no personal data" } },
];

export const MONOREPO = `apps/
  web/            Next.js App Router · Tailwind v4 · shadcn/Radix · TanStack · ECharts
  ai-api/         FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · scikit-learn
packages/
  contracts/      openapi.json → src/api-types.ts (generated)
infra/docker/     Dockerfiles + compose (configured)
docs/             SPEC · the build plan · DECISIONS (ADRs) · architecture/*`;

export const LIFECYCLE: Bilingual[] = [
  { th: "RequestContextMiddleware: กำหนด X-Request-ID และบันทึก JSON log (แฮช IP)", en: "RequestContextMiddleware: assigns X-Request-ID and writes a JSON access log (IP hashed)" },
  { th: "RateLimitMiddleware: token bucket ต่อ IP และต่อเซสชัน → 429", en: "RateLimitMiddleware: token buckets per IP and per session → 429" },
  { th: "get_demo_context: ตรวจ as_of, scenario_id, X-Demo-Session, X-Demo-Role → 422", en: "get_demo_context: validates as_of, scenario_id, X-Demo-Session, X-Demo-Role → 422" },
  { th: "require_permission: ตรวจสิทธิ์ของบทบาทจำลอง → 403", en: "require_permission: checks the simulated role's permission → 403" },
  { th: "Handler → บริการ → ฐานข้อมูล; การเขียนบันทึก audit ใน transaction เดียวกัน", en: "Handler → service → DB; writes append an audit record in the same transaction" },
  { th: "ข้อผิดพลาดทุกจุด → {\"error\": {code, message, details}}", en: "Any error → {\"error\": {code, message, details}}" },
];
