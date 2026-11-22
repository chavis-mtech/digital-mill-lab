import type { Metadata } from "next";
import { RoiSimulator } from "@/features/scenarios/roi-simulator";

export const metadata: Metadata = { title: "Business Impact (ROI)" };

export default function Page() {
  return <RoiSimulator />;
}
