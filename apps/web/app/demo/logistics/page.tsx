import type { Metadata } from "next";
import { LogisticsPage } from "@/features/logistics/logistics-page";

export const metadata: Metadata = { title: "Logistics & weighbridge" };

export default function Page() {
  return <LogisticsPage />;
}
