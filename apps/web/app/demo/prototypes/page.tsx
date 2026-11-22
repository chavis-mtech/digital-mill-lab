import type { Metadata } from "next";
import { PrototypesPage } from "@/features/prototypes/prototypes-page";

export const metadata: Metadata = { title: "P2 prototypes and concepts" };

export default function Page() {
  return <PrototypesPage />;
}
