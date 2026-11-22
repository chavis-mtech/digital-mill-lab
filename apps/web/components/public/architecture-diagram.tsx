"use client";

/**
 * System architecture diagram as React/SVG (not an image). Mirrors docs/architecture/SYSTEM_ARCHITECTURE.md:
 * browser → same-origin /api/v1 → FastAPI (middleware → DemoContext/RBAC → routers → services / ML / copilot
 * → audit) → SQLite/PostgreSQL ← seed engine; packages/contracts types the web app; integrations are
 * future contracts (dashed). Node status chips read content/status.ts. Below md the figure scrolls
 * horizontally inside its own container; a text equivalent is always rendered (`ArchitectureList`).
 */
import type { ReactNode } from "react";
import { useLocale } from "@/lib/i18n/client";
import type { Bilingual } from "@/lib/i18n/define";
import { cn } from "@/lib/utils";
import type { FeatureKey } from "@/content/status";
import { StatusChip } from "@/components/demo/status-chip";

type Node = { id: string; x: number; y: number; w: number; h: number; title: Bilingual; lines: Bilingual<string[]>; feature: FeatureKey; tone?: "web" | "api" | "data" | "future" };

const NODES: Node[] = [
  {
    id: "web",
    x: 24,
    y: 70,
    w: 236,
    h: 190,
    title: { th: "เว็บแอป Next.js", en: "Next.js web app" },
    lines: {
      th: ["apps/web · ชั้นแสดงผลเท่านั้น", "เว็บไซต์ + โมดูลเดโม + ทัวร์", "TH/EN · ป้ายข้อมูลสังเคราะห์", "TanStack Query · ECharts"],
      en: ["apps/web · rendering only", "Public site + demo modules + tour", "TH/EN · Synthetic-data banner", "TanStack Query · ECharts"],
    },
    feature: "design_system",
    tone: "web",
  },
  {
    id: "contracts",
    x: 24,
    y: 300,
    w: 236,
    h: 112,
    title: { th: "packages/contracts", en: "packages/contracts" },
    lines: { th: ["OpenAPI → ชนิดข้อมูล TypeScript", "สร้างอัตโนมัติ · CI ตรวจความสด"], en: ["OpenAPI → TypeScript types", "Generated · CI freshness check"] },
    feature: "api_contract",
    tone: "web",
  },
  {
    id: "core",
    x: 330,
    y: 70,
    w: 430,
    h: 92,
    title: { th: "Middleware · DemoContext · RBAC", en: "Middleware · DemoContext · RBAC" },
    lines: {
      th: ["request id + JSON log · rate limit (IP + session)", "as_of · scenario_id · X-Demo-Session · X-Demo-Role"],
      en: ["Request id + JSON logs · rate limit (IP + session)", "as_of · scenario_id · X-Demo-Session · X-Demo-Role"],
    },
    feature: "api_foundation",
    tone: "api",
  },
  {
    id: "routers",
    x: 330,
    y: 182,
    w: 430,
    h: 78,
    title: { th: "Router /api/v1 (94 operations)", en: "/api/v1 routers (94 operations)" },
    lines: {
      th: ["executive · production · process · ai · maintenance · work-orders", "logistics · energy · traceability · scenarios · roi · copilot · kb"],
      en: ["executive · production · process · ai · maintenance · work-orders", "logistics · energy · traceability · scenarios · roi · copilot · kb"],
    },
    feature: "api_contract",
    tone: "api",
  },
  {
    id: "services",
    x: 330,
    y: 280,
    w: 136,
    h: 132,
    title: { th: "บริการโดเมน", en: "Domain services" },
    lines: { th: ["KPI · การผลิต", "ซ่อมบำรุง · ROI", "ไม่อ่านเวลาจริง"], en: ["KPI · production", "maintenance · ROI", "no wall-clock reads"] },
    feature: "domain_services",
    tone: "api",
  },
  {
    id: "ml",
    x: 477,
    y: 280,
    w: 136,
    h: 132,
    title: { th: "ML (scikit-learn)", en: "ML (scikit-learn)" },
    lines: { th: ["พยากรณ์ · ความผิดปกติ", "เทียบ baseline", "model card"], en: ["forecast · anomaly", "vs naive baseline", "model cards"] },
    feature: "ml_models",
    tone: "api",
  },
  {
    id: "copilot",
    x: 624,
    y: 280,
    w: 136,
    h: 132,
    title: { th: "Copilot", en: "Copilot" },
    lines: { th: ["intent → เครื่องมือที่อนุญาต", "RAG เอกสารตัวอย่าง", "ไม่มี SQL อิสระ"], en: ["intent → allow-listed tools", "RAG over sample docs", "no free-form SQL"] },
    feature: "copilot",
    tone: "api",
  },
  {
    id: "db",
    x: 840,
    y: 120,
    w: 236,
    h: 130,
    title: { th: "ฐานข้อมูล", en: "Database" },
    lines: { th: ["SQLite data/demo.db", "PostgreSQL ผ่าน DATABASE_URL", "audit log แบบ hash chain"], en: ["SQLite data/demo.db", "PostgreSQL via DATABASE_URL", "hash-chained audit log"] },
    feature: "database_schema",
    tone: "data",
  },
  {
    id: "seed",
    x: 840,
    y: 290,
    w: 236,
    h: 122,
    title: { th: "เอนจินข้อมูลสังเคราะห์", en: "Synthetic data engine" },
    lines: { th: ["deterministic (seeded) · 120 วัน", "สมดุลมวล · 6 สถานการณ์"], en: ["Deterministic (seeded) · 120 days", "Mass balance · 6 scenarios"] },
    feature: "synthetic_data",
    tone: "data",
  },
];

const INTEGRATIONS = ["ERP / CMMS", "MES", "SCADA historian", "OPC UA", "MQTT", "Weighbridge", "LIMS", "GPS / fleet", "Accounting / HR"];

function NodeBox({ node }: { node: Node }) {
  const { locale } = useLocale();
  return (
    <foreignObject x={node.x} y={node.y} width={node.w} height={node.h}>
      <div
        className={cn(
          "flex h-full flex-col gap-1 rounded-xl border bg-surface p-3 text-left shadow-xs",
          node.tone === "web" && "border-info/40",
          node.tone === "api" && "border-border-strong",
          node.tone === "data" && "border-accent/40",
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
          <p className="text-[12.5px] leading-tight font-semibold text-foreground">{node.title[locale]}</p>
          <StatusChip feature={node.feature} showTooltip={false} />
        </div>
        <ul className="mt-0.5 space-y-0.5 text-[11px] leading-snug text-muted-foreground">
          {node.lines[locale].map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </div>
    </foreignObject>
  );
}

function Label({ x, y, children, anchor = "middle" }: { x: number; y: number; children: ReactNode; anchor?: "start" | "middle" | "end" }) {
  return (
    <text x={x} y={y} textAnchor={anchor} className="fill-muted-foreground text-[11px] font-medium" style={{ fontFamily: "var(--font-sans)" }}>
      {children}
    </text>
  );
}

export function ArchitectureDiagram({ title, description }: { title: string; description: string }) {
  const { locale } = useLocale();
  return (
    <figure className="flex flex-col gap-3">
      <div tabIndex={0} role="region" aria-label={title} className="overflow-x-auto rounded-2xl border border-border bg-surface-2/40 p-3 scrollbar-thin focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
        <svg viewBox="0 0 1100 600" className="h-auto w-full min-w-[920px]" role="img" aria-labelledby="arch-title arch-desc">
          <title id="arch-title">{title}</title>
          <desc id="arch-desc">{description}</desc>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" className="fill-muted-foreground" />
            </marker>
          </defs>

          {/* Group frames */}
          <rect x="10" y="30" width="264" height="400" rx="16" className="fill-none stroke-border" strokeDasharray="0" />
          <Label x={24} y={52} anchor="start">
            {locale === "th" ? "เบราว์เซอร์ / ชั้นเว็บ" : "Browser / web tier"}
          </Label>
          <rect x="316" y="30" width="458" height="400" rx="16" className="fill-none stroke-border-strong" />
          <Label x={330} y={52} anchor="start">
            {locale === "th" ? "บริการ FastAPI (apps/ai-api) — modular monolith" : "FastAPI service (apps/ai-api) — modular monolith"}
          </Label>
          <rect x="826" y="100" width="264" height="330" rx="16" className="fill-none stroke-border" />
          <Label x={840} y={92} anchor="start">
            {locale === "th" ? "ข้อมูล" : "Data"}
          </Label>

          {/* Connectors */}
          <path d="M260 160 H330" className="stroke-muted-foreground" strokeWidth="1.5" fill="none" markerEnd="url(#arrow)" />
          <Label x={295} y={148}>/api/v1</Label>
          <Label x={295} y={180}>{locale === "th" ? "โดเมนเดียวกัน" : "same origin"}</Label>
          <path d="M142 300 V260" className="stroke-muted-foreground" strokeWidth="1.5" strokeDasharray="4 3" fill="none" markerEnd="url(#arrow)" />
          <Label x={196} y={286}>{locale === "th" ? "ชนิดข้อมูล" : "types"}</Label>
          <path d="M545 162 V182" className="stroke-muted-foreground" strokeWidth="1.5" fill="none" markerEnd="url(#arrow)" />
          <path d="M398 260 V280 M545 260 V280 M692 260 V280" className="stroke-muted-foreground" strokeWidth="1.5" fill="none" markerEnd="url(#arrow)" />
          <path d="M692 346 H613" className="stroke-muted-foreground" strokeWidth="1.2" strokeDasharray="3 3" fill="none" markerEnd="url(#arrow)" />
          <path d="M760 220 H800 V185 H840" className="stroke-muted-foreground" strokeWidth="1.5" fill="none" markerEnd="url(#arrow)" />
          <Label x={800} y={206}>SQL</Label>
          <path d="M958 290 V250" className="stroke-muted-foreground" strokeWidth="1.5" fill="none" markerEnd="url(#arrow)" />
          <Label x={1010} y={276}>{locale === "th" ? "seed" : "seed"}</Label>
          {/* contracts generated from the API */}
          <path d="M330 395 H260" className="stroke-muted-foreground" strokeWidth="1.2" strokeDasharray="4 3" fill="none" markerEnd="url(#arrow)" />
          <Label x={295} y={388}>OpenAPI</Label>

          {NODES.map((n) => (
            <NodeBox key={n.id} node={n} />
          ))}

          {/* Future integrations */}
          <rect x="10" y="470" width="1080" height="118" rx="16" className="fill-none stroke-border-strong" strokeDasharray="6 5" />
          <Label x={24} y={492} anchor="start">
            {locale === "th"
              ? "สัญญาการเชื่อมต่อในอนาคต — วางแผนไว้ · เป็นสัญญาเท่านั้น · อ่านอย่างเดียวต่อ OT"
              : "Future integration contracts — planned · contract only · read-only towards OT"}
          </Label>
          <path d="M398 470 V412" className="stroke-muted-foreground" strokeWidth="1.2" strokeDasharray="5 4" fill="none" markerEnd="url(#arrow)" />
          {INTEGRATIONS.map((name, i) => {
            const w = 108;
            const gap = (1080 - 28 - INTEGRATIONS.length * w) / (INTEGRATIONS.length - 1);
            const x = 24 + i * (w + gap);
            return (
              <g key={name}>
                <rect x={x} y={512} width={w} height={56} rx="10" className="fill-surface stroke-border-strong" strokeDasharray="4 3" />
                <text x={x + w / 2} y={536} textAnchor="middle" className="fill-foreground text-[11.5px] font-medium" style={{ fontFamily: "var(--font-sans)" }}>
                  {name}
                </text>
                <text x={x + w / 2} y={553} textAnchor="middle" className="fill-subtle-foreground text-[10px]" style={{ fontFamily: "var(--font-sans)" }}>
                  {locale === "th" ? "วางแผนไว้" : "planned"}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <figcaption className="text-xs text-muted-foreground">{description}</figcaption>
    </figure>
  );
}
