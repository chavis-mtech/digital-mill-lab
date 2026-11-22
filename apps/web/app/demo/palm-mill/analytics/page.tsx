import type { Metadata } from "next";
import { ProductionAnalytics } from "@/features/palm-mill/production-analytics";

export const metadata: Metadata = { title: "Analytics & OER trend" };

export default function Page() {
  return <ProductionAnalytics />;
}
