import type { Metadata } from "next";
import { WorkOrdersPage } from "@/features/maintenance/work-orders-page";

export const metadata: Metadata = { title: "Maintenance work orders" };

export default function Page() {
  return <WorkOrdersPage />;
}
