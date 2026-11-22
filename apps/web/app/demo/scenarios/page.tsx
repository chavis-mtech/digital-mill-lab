import type { Metadata } from "next";
import { ScenarioSimulator } from "@/features/scenarios/scenario-simulator";

export const metadata: Metadata = { title: "Scenario Simulator" };

export default function Page() {
  return <ScenarioSimulator />;
}
