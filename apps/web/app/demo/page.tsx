import type { Metadata } from "next";
import { DemoHub } from "@/components/hub/demo-hub";

export const metadata: Metadata = { title: "Demo hub" };

export default function DemoHubPage() {
  return <DemoHub />;
}
