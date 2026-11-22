import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";

/** Demo area shell (owned by frontend-foundation). Module pages render inside it. */
export default function DemoLayout({ children }: { children: ReactNode }) {
  return <AppShell area="demo">{children}</AppShell>;
}
