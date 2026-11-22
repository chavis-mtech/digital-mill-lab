import type { Metadata } from "next";
import { DocPage } from "@/features/docs/doc-page";

export const metadata: Metadata = { title: "Integration contracts (technical documentation)" };

export default async function Page({ searchParams }: { searchParams: Promise<{ doc?: string | string[] }> }) {
  const { doc } = await searchParams;
  return <DocPage slug="integration" docKey={typeof doc === "string" ? doc : undefined} />;
}
