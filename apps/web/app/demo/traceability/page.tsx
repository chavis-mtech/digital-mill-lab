import type { Metadata } from "next";
import { TraceabilityPage } from "@/features/traceability/traceability-page";

export const metadata: Metadata = { title: "Supplier traceability" };

export default function Page() {
  return <TraceabilityPage />;
}
