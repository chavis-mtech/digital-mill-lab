"use client";
import { type ComponentProps } from "react";
import { Dialog as Primitive } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = Primitive.Root;
export const DialogTrigger = Primitive.Trigger;
export const DialogClose = Primitive.Close;

export function DialogContent({
  className,
  children,
  side,
  closeLabel = "Close",
  ...props
}: ComponentProps<typeof Primitive.Content> & { side?: "left" | "right" | "bottom"; closeLabel?: string }) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-black/45 backdrop-blur-[2px] animate-in fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
      <Primitive.Content
        className={cn(
          "fixed z-50 flex flex-col gap-4 border border-border bg-surface shadow-lg outline-none animate-in data-[state=closed]:animate-out",
          !side && "top-1/2 left-1/2 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-xl p-6 fade-in-0 zoom-in-95",
          side === "left" && "inset-y-0 left-0 h-full w-[min(20rem,88vw)] slide-in-from-left data-[state=closed]:slide-out-to-left",
          side === "right" && "inset-y-0 right-0 h-full w-[min(24rem,92vw)] slide-in-from-right data-[state=closed]:slide-out-to-right",
          side === "bottom" && "inset-x-0 bottom-0 max-h-[85vh] rounded-t-xl p-5 slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
          className,
        )}
        {...props}
      >
        {children}
        <Primitive.Close className="absolute top-3 right-3 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          <X className="size-4" aria-hidden />
          <span className="sr-only">{closeLabel}</span>
        </Primitive.Close>
      </Primitive.Content>
    </Primitive.Portal>
  );
}

export function DialogTitle({ className, ...props }: ComponentProps<typeof Primitive.Title>) {
  return <Primitive.Title className={cn("text-base font-semibold text-foreground", className)} {...props} />;
}
export function DialogDescription({ className, ...props }: ComponentProps<typeof Primitive.Description>) {
  return <Primitive.Description className={cn("text-sm text-muted-foreground", className)} {...props} />;
}
