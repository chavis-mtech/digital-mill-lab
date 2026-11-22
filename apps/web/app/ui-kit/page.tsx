import type { Metadata } from "next";
import { UiKit } from "./ui-kit";

export const metadata: Metadata = { title: "UI kit (internal)", robots: { index: false, follow: false } };

/** Hidden internal showcase for visual QA (not linked from navigation). */
export default function UiKitPage() {
  return <UiKit />;
}
