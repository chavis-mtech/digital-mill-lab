import type { Metadata } from "next";
import { ExecutiveDashboard } from "@/features/executive/executive-dashboard";

export const metadata: Metadata = { title: "Executive Control Tower" };

export default function Page() {
  return <ExecutiveDashboard />;
}
