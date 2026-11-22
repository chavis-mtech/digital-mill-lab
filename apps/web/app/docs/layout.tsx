import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";

/** Docs area shell. Pages use <DocsLayout> from components/layouts. */
export default function DocsAreaLayout({ children }: { children: ReactNode }) {
  return <AppShell area="docs">{children}</AppShell>;
}
