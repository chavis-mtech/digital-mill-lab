import { type ComponentProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 rounded-md border px-1.5 py-0.5 text-2xs font-medium whitespace-nowrap [&_svg]:size-3 [&_svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "border-border bg-neutral-soft text-neutral-fg",
        accent: "border-transparent bg-accent-soft text-accent-text",
        success: "border-transparent bg-success-soft text-success-fg",
        warning: "border-transparent bg-warning-soft text-warning-fg",
        critical: "border-transparent bg-critical-soft text-critical-fg",
        maintenance: "border-transparent bg-maintenance-soft text-maintenance-fg",
        info: "border-transparent bg-info-soft text-info-fg",
        outline: "border-border-strong bg-transparent text-muted-foreground",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type BadgeProps = ComponentProps<"span"> & VariantProps<typeof badgeVariants>;

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone }), className)} {...props} />;
}
