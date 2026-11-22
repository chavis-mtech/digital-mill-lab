import type { Metadata } from "next";
import { AiInsights } from "@/features/palm-mill/ai-insights";

export const metadata: Metadata = { title: "AI insights" };

export default function Page() {
  return <AiInsights />;
}
