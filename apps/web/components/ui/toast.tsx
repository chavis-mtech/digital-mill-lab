"use client";
import { Toaster as Sonner, toast } from "sonner";
import { useTheme } from "@/lib/theme/theme";

/** App-wide toaster (mounted once in Providers). Use `toast.success(...)`, `toast.error(...)`. */
export function Toaster() {
  const { resolved } = useTheme();
  return (
    <Sonner
      theme={resolved}
      position="bottom-right"
      closeButton
      toastOptions={{
        classNames: {
          toast: "!rounded-lg !border !border-border !bg-surface !text-foreground !shadow-lg !font-sans",
          description: "!text-muted-foreground",
        },
      }}
    />
  );
}

export { toast };
