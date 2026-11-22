import type { Metadata } from "next";
import { ProductionOverview } from "@/features/palm-mill/production-overview";

export const metadata: Metadata = { title: "Production overview" };

export default function Page() {
  return <ProductionOverview />;
}
