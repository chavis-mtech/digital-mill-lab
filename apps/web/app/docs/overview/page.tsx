import type { Metadata } from "next";
import { DocPage } from "@/features/docs/doc-page";

export const metadata: Metadata = { title: "Overview (technical documentation)" };

export default async function Page({ searchParams }: { searchParams: Promise<{ doc?: string | string[] }> }) {
  const { doc } = await searchParams;
  return <DocPage slug="overview" docKey={typeof doc === "string" ? doc : undefined} />;
}
