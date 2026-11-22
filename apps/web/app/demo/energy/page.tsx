import type { Metadata } from "next";
import { EnergyPage } from "@/features/energy/energy-page";

export const metadata: Metadata = { title: "Energy & sustainability" };

export default function Page() {
  return <EnergyPage />;
}
