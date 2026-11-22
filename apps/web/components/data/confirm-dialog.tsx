"use client";

import { useState, type ReactNode } from "react";
import { ShieldCheck } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import common from "@/messages/common.i18n";

/**
 * Human confirmation before modifying records (SPEC §0 rule 4). Wrap every record-changing action:
 * create work order, approve recommendation, change status, reset session. `onConfirm` may be async; the
 * dialog stays open (button disabled) until it resolves and closes on success.
 */
export function ConfirmDialog({
  trigger,
  title,
  description,
  details,
  confirmLabel,
  destructive,
  onConfirm,
  open,
  onOpenChange,
}: {
  trigger?: ReactNode;
  title: string;
  description: ReactNode;
  /** Summary of exactly what will change (fields/values). */
  details?: ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const t = useT(common);
  const [internalOpen, setInternalOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const isOpen = open ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  return (
    <AlertDialog open={isOpen} onOpenChange={(v) => !busy && setOpen(v)}>
      {trigger ? <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger> : null}
      <AlertDialogContent>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription asChild>
          <div className="text-sm text-muted-foreground">{description}</div>
        </AlertDialogDescription>
        {details ? <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs">{details}</div> : null}
        <p className="flex items-start gap-1.5 text-2xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {t.confirm.sandboxNote}
        </p>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <AlertDialogCancel disabled={busy}>{t.confirm.cancel}</AlertDialogCancel>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm();
                setOpen(false);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? t.confirm.working : (confirmLabel ?? t.confirm.confirm)}
          </Button>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}
