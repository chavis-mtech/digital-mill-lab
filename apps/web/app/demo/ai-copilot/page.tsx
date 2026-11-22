import type { Metadata } from "next";
import { CopilotPage } from "@/features/copilot/copilot-page";

export const metadata: Metadata = { title: "Industrial AI Copilot" };

export default function Page() {
  return <CopilotPage />;
}
