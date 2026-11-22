import type { Metadata } from "next";
import Link from "next/link";
import { CircleDashed, ExternalLink, GraduationCap } from "lucide-react";
import { getLocale, getT } from "@/lib/i18n/server";
import pages from "@/content/public/pages.i18n";
import { DEVELOPER, PLACEHOLDERS } from "@/content/developer";
import { PublicPageHeader } from "@/components/public/public-layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Developer" };

export default async function DeveloperPage() {
  const locale = await getLocale();
  const t = (await getT(pages)).developer;
  const d = DEVELOPER;
  return (
    <>
      <PublicPageHeader kicker={t.title} title={d.name} lead={d.summary[locale]}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="neutral" className="px-2.5 py-1 text-xs">{d.currentTitle}</Badge>
          <Badge tone="accent" className="px-2.5 py-1 text-xs">
            {t.positionSought}: {d.positionSought}
          </Badge>
        </div>
        <p className="mt-4 max-w-3xl text-xs text-subtle-foreground">
          {t.sourceNote}{" "}
          <a href={d.source.url} className="underline underline-offset-2 hover:text-foreground" rel="noopener noreferrer" target="_blank">
            {d.source.label}
          </a>
        </p>
      </PublicPageHeader>
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-[1.6fr_1fr] lg:px-8">
        <div className="flex flex-col gap-8">
          <section aria-labelledby="exp">
            <h2 id="exp" className="mb-4 text-lg font-semibold">{t.experience}</h2>
            {d.experience.map((e) => (
              <div key={e.company} className="mb-4 rounded-2xl border border-border bg-surface p-6 last:mb-0">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-base font-semibold">{e.company}</h3>
                  <span className="tabular text-xs text-muted-foreground">{e.period}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{e.role}</p>
                {e.summary ? (
                  <ul className="mt-3 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                    {e.summary[locale].map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                ) : null}
                <div className={e.projects.length > 0 ? "mt-4 flex flex-col gap-5" : "hidden"}>
                  {e.projects.map((p) => (
                    <div key={p.name} className="border-l-2 border-accent/40 pl-4">
                      <p className="text-sm font-semibold">{p.name}</p>
                      <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Stack">
                        {p.stack.map((s) => (
                          <li key={s}>
                            <Badge tone="outline">{s}</Badge>
                          </li>
                        ))}
                      </ul>
                      <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                        {p.points[locale].map((x) => (
                          <li key={x}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>
          <section aria-labelledby="skills">
            <h2 id="skills" className="mb-4 text-lg font-semibold">{t.skills}</h2>
            <dl className="grid gap-4 rounded-2xl border border-border bg-surface p-6 sm:grid-cols-2">
              {Object.entries(d.skills).map(([group, items]) => (
                <div key={group}>
                  <dt className="text-2xs font-semibold tracking-wide text-muted-foreground uppercase">{group}</dt>
                  <dd className="mt-2 flex flex-wrap gap-1.5">
                    {items.map((s) => (
                      <Badge key={s} tone="neutral" className="text-xs">{s}</Badge>
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <section aria-labelledby="edu" className="rounded-2xl border border-border bg-surface p-6">
            <h2 id="edu" className="flex items-center gap-2 text-lg font-semibold">
              <GraduationCap className="size-5 text-accent-text" aria-hidden />
              {t.education}
            </h2>
            <p className="mt-2 text-sm font-medium">{d.education.institution}</p>
            <p className="text-sm text-muted-foreground">{d.education.degree}</p>
          </section>
          <section aria-labelledby="proj" className="rounded-2xl border border-border bg-surface-2/60 p-6">
            <h2 id="proj" className="text-lg font-semibold">{t.thisProject}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{t.thisProjectBody}</p>
            <Button asChild variant="link" className="mt-1 px-0">
              <Link href="/demo">/demo</Link>
            </Button>
          </section>
        </div>
        <aside className="flex flex-col gap-6">
          <section aria-labelledby="todo" className="rounded-2xl border border-dashed border-border-strong bg-surface p-6">
            <h2 id="todo" className="text-sm font-semibold">{t.placeholders}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{t.placeholdersNote}</p>
            <ul className="mt-4 flex flex-col gap-2">
              {PLACEHOLDERS.map((p) => (
                <li key={p.key} className="flex items-center gap-2 text-sm text-muted-foreground" data-placeholder={p.key}>
                  <CircleDashed className="size-4 shrink-0 text-subtle-foreground" aria-hidden />
                  {p.label[locale]}
                </li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="dev-contact" className="rounded-2xl border border-border bg-surface p-6">
            <h2 id="dev-contact" className="text-sm font-semibold">{t.contact}</h2>
            <ul className="mt-3 flex flex-col gap-2 text-sm">
              <li>
                <a className="text-accent-text hover:underline" href={`mailto:${d.contact.email}`}>{d.contact.email}</a>
              </li>
              <li>
                <a className="inline-flex items-center gap-1 text-accent-text hover:underline" href={d.contact.github} target="_blank" rel="noopener noreferrer">
                  github.com/chavis-mtech <ExternalLink className="size-3.5" aria-hidden />
                </a>
              </li>
            </ul>
            <Button asChild variant="outline" size="sm" className="mt-4">
              <Link href="/contact">{t.contact}</Link>
            </Button>
          </section>
        </aside>
      </div>
    </>
  );
}
