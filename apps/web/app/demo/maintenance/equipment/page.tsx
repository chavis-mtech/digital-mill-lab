import type { Metadata } from "next";
import { EquipmentPage } from "@/features/maintenance/equipment-page";

export const metadata: Metadata = { title: "Equipment health & sensors" };

export default function Page() {
  return <EquipmentPage />;
}
