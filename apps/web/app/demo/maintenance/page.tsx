import type { Metadata } from "next";
import { MaintenanceOverviewPage } from "@/features/maintenance/overview-page";

export const metadata: Metadata = { title: "Predictive maintenance" };

export default function Page() {
  return <MaintenanceOverviewPage />;
}
