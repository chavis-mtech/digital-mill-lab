import { type ComponentProps } from "react";
import { cn } from "@/lib/utils";

/** Shimmer placeholder. Decorative: wrap groups in an element with aria-busy / a status message. */
export function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return <div aria-hidden className={cn("animate-pulse rounded-md bg-surface-3/80", className)} {...props} />;
}
