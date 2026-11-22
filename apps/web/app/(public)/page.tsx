import Link from "next/link";
import { ArrowRight, ArrowUpRight, Boxes, BrainCircuit, Briefcase, Factory, Gauge, GitBranch, Bot, Truck, Wrench, Zap, Network } from "lucide-react";
import { getLocale, getT } from "@/lib/i18n/server";
import { FEATURES, type FeatureKey } from "@/content/status";
import { OPPORTUNITIES } from "@/content/public/opportunities";
import { ROADMAP } from "@/content/public/roadmap";
import { DEVELOPER } from "@/content/developer";
import landing from "@/content/public/landing.i18n";
import pages from "@/content/public/pages.i18n";
import { Button } from "@/components/ui/button";
import { StatusChip, StatusLegend } from "@/components/demo/status-chip";
import { StartTourButton } from "@/components/tour/tour";
import { Section } from "@/components/public/public-layout";
import { ProcessLine } from "@/components/public/process-line";

const OPP_ICONS = { gauge: Gauge, wrench: Wrench, truck: Truck, zap: Zap, "git-branch": GitBranch, bot: Bot } as const;
const PILLAR_ICONS = { process: Factory, ai: BrainCircuit, architecture: Network, value: Gauge, leadership: Briefcase } as const;

const SOLUTIONS: FeatureKey[] = [
  "executive_control_tower",
  "palm_mill_production",
  "predictive_maintenance",
  "copilot",
  "scenario_simulator",
  "business_impact",
  "digital_twin_lite",
  "logistics",
  "energy",
  "traceability",
  "work_orders",
  "cv_grading",
];

export default async function LandingPage() {
  const locale = await getLocale();
  const t = await getT(landing);
  const r = await getT(pages);

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div aria-hidden className="surface-grid absolute inset-0 [mask-image:radial-gradient(ellipse_80%_70%_at_30%_0%,black,transparent)] opacity-70" />
        <div aria-hidden className="absolute -top-40 right-[-10%] size-[36rem] rounded-full bg-accent/10 blur-3xl" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 pt-14 pb-16 sm:px-6 sm:pt-20 lg:grid-cols-[1.15fr_1fr] lg:items-center lg:px-8 lg:pb-24">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted-foreground shadow-xs">
              <span className="size-1.5 rounded-full bg-accent" aria-hidden />
              {t.eyebrow}
            </p>
            <h1 lang="en" className="mt-5 text-4xl leading-[1.08] font-semibold tracking-tight text-foreground sm:text-5xl">
              {t.headline}
            </h1>
            {locale === "th" ? <p className="mt-3 text-xl font-medium text-accent-text">{t.headlineTranslation}</p> : null}
            <p lang="en" className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              {t.subtitle}
            </p>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-subtle-foreground">{t.subtitleTranslation}</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link href="/demo">
                  {t.ctaDemo} <ArrowRight aria-hidden />
                </Link>
              </Button>
              <StartTourButton variant="outline" size="lg" label={t.ctaTour} />
            </div>
            <p className="mt-6 text-xs text-subtle-foreground">{t.heroNote}</p>
          </div>
          <ProcessLine label={t.heroFlowLabel} caption={t.heroFlowCaption} />
        </div>
      </section>

      {/* Overview */}
      <Section id="overview" kicker={t.overviewKicker} title={t.overviewTitle} lead={t.overviewBody}>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {(Object.keys(t.pillars) as (keyof typeof t.pillars)[]).map((k) => {
            const Icon = PILLAR_ICONS[k];
            return (
              <li key={k} className="rounded-xl border border-border bg-surface p-5 shadow-xs">
                <Icon className="size-5 text-accent-text" aria-hidden />
                <h3 className="mt-3 text-sm font-semibold">{t.pillars[k].title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{t.pillars[k].body}</p>
              </li>
            );
          })}
        </ul>
      </Section>

      {/* Opportunities (challenges framed as opportunities) */}
      <Section id="opportunities" tone="muted" kicker={t.challengesKicker} title={t.challengesTitle} lead={t.challengesBody}>
        <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {OPPORTUNITIES.map((o) => {
            const Icon = OPP_ICONS[o.icon];
            return (
              <li key={o.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-5">
                <div className="flex items-center justify-between gap-2">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent-text">
                    <Icon className="size-4.5" aria-hidden />
                  </span>
                  <StatusChip feature={o.feature} />
                </div>
                <h3 className="text-sm font-semibold">{o.title[locale]}</h3>
                <p className="text-xs leading-relaxed text-muted-foreground">{o.summary[locale]}</p>
              </li>
            );
          })}
        </ul>
        <div className="mt-6">
          <Button asChild variant="outline">
            <Link href="/business-opportunities">
              {t.seeAll} <ArrowRight aria-hidden />
            </Link>
          </Button>
        </div>
      </Section>

      {/* AI solutions with maturity */}
      <Section id="solutions" kicker={t.solutionsKicker} title={t.solutionsTitle} lead={t.solutionsBody}>
        <StatusLegend className="mb-5" />
        <ul className="grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {SOLUTIONS.map((k) => {
            const f = FEATURES[k];
            return (
              <li key={k} className="flex items-center justify-between gap-3 bg-surface px-4 py-3.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{f.label[locale]}</p>
                  <p className="text-2xs text-subtle-foreground">{f.priority}</p>
                </div>
                <StatusChip feature={k} />
              </li>
            );
          })}
        </ul>
      </Section>

      {/* Explore live demo */}
      <section className="px-4 sm:px-6 lg:px-8">
        <div className="relative mx-auto max-w-7xl overflow-hidden rounded-2xl bg-primary px-6 py-12 text-primary-foreground sm:px-12">
          <div aria-hidden className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(to_right,currentColor_1px,transparent_1px),linear-gradient(to_bottom,currentColor_1px,transparent_1px)] [background-size:28px_28px]" />
          <div className="relative grid gap-6 lg:grid-cols-[1.5fr_1fr] lg:items-center">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t.demoTitle}</h2>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed opacity-85">{t.demoBody}</p>
            </div>
            <div className="flex flex-wrap gap-3 lg:justify-end">
              <Button asChild variant="accent" size="lg">
                <Link href="/demo">
                  {t.ctaDemo} <ArrowUpRight aria-hidden />
                </Link>
              </Button>
              <StartTourButton variant="outline" size="lg" label={t.ctaTour} className="border-primary-foreground/30 bg-transparent text-primary-foreground hover:bg-primary-foreground/10" />
            </div>
          </div>
        </div>
      </section>

      {/* Architecture preview */}
      <Section id="architecture" kicker={t.architectureKicker} title={t.architectureTitle} lead={t.architectureBody}>
        <ol className="grid gap-3 md:grid-cols-4">
          {[
            { icon: Boxes, th: "เว็บแอป Next.js", en: "Next.js web app", f: "design_system" as FeatureKey },
            { icon: Network, th: "FastAPI /api/v1", en: "FastAPI /api/v1", f: "api_contract" as FeatureKey },
            { icon: BrainCircuit, th: "บริการ · ML · Copilot", en: "Services · ML · Copilot", f: "ml_models" as FeatureKey },
            { icon: Factory, th: "ข้อมูลสังเคราะห์ 120 วัน", en: "120-day synthetic data", f: "synthetic_data" as FeatureKey },
          ].map((s, i, arr) => (
            <li key={s.en} className="relative flex items-center gap-3 rounded-xl border border-border bg-surface p-4">
              <s.icon className="size-5 shrink-0 text-accent-text" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{locale === "th" ? s.th : s.en}</p>
                <StatusChip feature={s.f} className="mt-1" />
              </div>
              {i < arr.length - 1 ? <ArrowRight className="absolute top-1/2 -right-3 z-10 hidden size-4 -translate-y-1/2 rounded-full bg-background text-subtle-foreground md:block" aria-hidden /> : null}
            </li>
          ))}
        </ol>
        <Button asChild variant="link" className="mt-4">
          <Link href="/technical-architecture">
            {t.viewArchitecture} <ArrowRight aria-hidden />
          </Link>
        </Button>
      </Section>

      {/* Roadmap preview */}
      <Section id="roadmap" tone="muted" kicker={t.roadmapKicker} title={t.roadmapTitle} lead={t.roadmapBody}>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {ROADMAP.map((p, i) => (
            <li key={p.id} className="relative rounded-xl border border-border bg-surface p-4">
              <p className="tabular text-2xs font-semibold tracking-wide text-accent-text uppercase">{p.horizon[locale]}</p>
              <p className="mt-1 text-sm font-semibold">{p.title[locale]}</p>
              <p className="mt-1.5 line-clamp-4 text-xs leading-relaxed text-muted-foreground">{p.goal[locale]}</p>
              <span aria-hidden className="absolute top-4 right-4 text-2xs font-semibold text-subtle-foreground tabular">
                {String(i + 1).padStart(2, "0")}
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-muted-foreground">{r.roadmap.tag}</p>
        <Button asChild variant="link" className="mt-2">
          <Link href="/implementation-roadmap">
            {t.viewRoadmap} <ArrowRight aria-hidden />
          </Link>
        </Button>
      </Section>

      {/* Developer / contact */}
      <Section id="developer" kicker={t.developerKicker} title={t.developerTitle} lead={t.developerBody}>
        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-lg font-semibold">{DEVELOPER.name}</p>
            <p className="text-sm text-muted-foreground">
              {DEVELOPER.currentTitle} → {DEVELOPER.positionSought}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/developer">{t.viewDeveloper}</Link>
            </Button>
            <Button asChild>
              <Link href="/contact">{t.contact}</Link>
            </Button>
          </div>
        </div>
      </Section>
    </>
  );
}
