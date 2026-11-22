import type { Metadata } from "next";
import { CircleDashed, ExternalLink, FileText, Mail } from "lucide-react";
import { getT } from "@/lib/i18n/server";
import pages from "@/content/public/pages.i18n";
import { DEVELOPER } from "@/content/developer";
import { PublicPageHeader } from "@/components/public/public-layout";

export const metadata: Metadata = { title: "Contact" };

export default async function ContactPage() {
  const t = (await getT(pages)).contact;
  const c = DEVELOPER.contact;
  const rows = [
    { icon: Mail, label: t.email, value: c.email, href: `mailto:${c.email}` },
    { icon: ExternalLink, label: t.github, value: "github.com/chavis-mtech", href: c.github, external: true },
    { icon: CircleDashed, label: t.linkedin, value: null },
    { icon: FileText, label: t.resume, value: null },
  ];
  return (
    <>
      <PublicPageHeader title={t.title} lead={t.lead} />
      <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6 lg:px-8">
        <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-surface">
          {rows.map((r) => (
            <li key={r.label} className="flex items-center gap-4 px-5 py-4">
              <r.icon className="size-5 shrink-0 text-muted-foreground" aria-hidden />
              <span className="w-28 shrink-0 text-sm font-medium">{r.label}</span>
              {r.value ? (
                <a href={r.href} className="min-w-0 truncate text-sm text-accent-text hover:underline" {...(r.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
                  {r.value}
                </a>
              ) : (
                <span className="text-sm text-subtle-foreground italic" data-placeholder>
                  {t.notProvided} (TODO)
                </span>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-subtle-foreground">{t.sourceNote}</p>
        <p className="mt-1 text-xs text-subtle-foreground">{t.privacy}</p>
      </div>
    </>
  );
}
