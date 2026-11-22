import type { Metadata } from "next";
import { ProcessTwin } from "@/features/palm-mill/process-twin";

export const metadata: Metadata = { title: "Process flow (Digital Twin Lite)" };

export default function Page() {
  return <ProcessTwin />;
}
