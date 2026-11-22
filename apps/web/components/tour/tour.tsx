"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, Compass, Construction, X } from "lucide-react";
import { useLocale, useT } from "@/lib/i18n/client";
import { ROLE_LABELS, SCENARIO_LABELS } from "@/lib/demo/constants";
import { TOUR_STEPS, type TourStep } from "@/content/tour";
import { cn } from "@/lib/utils";
import { Button, type ButtonProps } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import tourMessages from "@/messages/tour.i18n";

type TourContextValue = {
  active: boolean;
  index: number;
  steps: readonly TourStep[];
  start: () => void;
  stop: () => void;
  go: (index: number) => void;
};

const TourCtx = createContext<TourContextValue | null>(null);
const STORAGE = "dml_tour";

function buildHref(step: TourStep) {
  const q = new URLSearchParams({ scenario: step.scenario, playback: step.playback, role: step.role });
  return `${step.route}?${q.toString()}`;
}

/**
 * Tour engine. Step definitions live in `content/tour.ts`; this provider applies each step's demo context,
 * navigates, and the overlay highlights `[data-tour=<target>]` (or degrades to a "not built yet" chip).
 * State persists in sessionStorage so a reload resumes the tour.
 */
export function TourProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [active, setActive] = useState(false);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE);
      if (raw) {
        const s = JSON.parse(raw) as { active?: boolean; index?: number };
        if (s.active && typeof s.index === "number" && s.index >= 0 && s.index < TOUR_STEPS.length) {
          // eslint-disable-next-line react-hooks/set-state-in-effect -- resume from browser-only storage
          setActive(true);
          setIndex(s.index);
        }
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE, JSON.stringify({ active, index }));
    } catch {
      /* ignore */
    }
  }, [active, index]);

  const go = useCallback(
    (i: number) => {
      const step = TOUR_STEPS[i];
      if (!step) return;
      setIndex(i);
      setActive(true);
      // The step's context travels in the URL; DemoProvider adopts URL params after navigation. (Applying
      // state first would let the URL-sync effect rewrite history for the *old* path mid-navigation.)
      router.push(buildHref(step));
    },
    [router],
  );
  const start = useCallback(() => go(0), [go]);
  const stop = useCallback(() => setActive(false), []);

  const value = useMemo(() => ({ active, index, steps: TOUR_STEPS, start, stop, go }), [active, index, start, stop, go]);
  return (
    <TourCtx.Provider value={value}>
      {children}
      <TourOverlay />
    </TourCtx.Provider>
  );
}

export function useTour(): TourContextValue {
  const v = useContext(TourCtx);
  if (!v) throw new Error("useTour must be used inside <TourProvider>");
  return v;
}

/** Button that starts the tour ("ทดลองชมระบบใน 5 นาที"). */
export function StartTourButton({ label, ...props }: ButtonProps & { label?: string }) {
  const t = useT(tourMessages);
  const { start } = useTour();
  return (
    <Button onClick={start} {...props}>
      <Compass aria-hidden />
      {label ?? t.start}
    </Button>
  );
}

type Rect = { top: number; left: number; width: number; height: number };

function TourOverlay() {
  const { active, index, steps, go, stop } = useTour();
  const t = useT(tourMessages);
  const { locale } = useLocale();
  const pathname = usePathname();
  const step = steps[index];
  const [rect, setRect] = useState<Rect | null>(null);
  const [missing, setMissing] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const onRoute = !!step && pathname === step.route;

  // Find the target after navigation; poll briefly because pages load data asynchronously.
  useEffect(() => {
    if (!active || !step || !onRoute) return;
    let el: Element | null = null;
    let frame = 0;
    let tries = 0;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset per step before searching the DOM
    setMissing(false);
    setRect(null);
    const measure = () => {
      if (!el) return;
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    const find = () => {
      el = document.querySelector(`[data-tour="${CSS.escape(step.target)}"]`);
      if (el) {
        setMissing(false);
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
        measure();
        return;
      }
      // Targets render after their data arrives (cold open can take several seconds): only call the view
      // "not built" after ~8 s, but keep looking up to ~20 s so a slow page still gets highlighted.
      tries += 1;
      if (tries === 32) setMissing(true);
      if (tries < 80) frame = window.setTimeout(find, 250);
    };
    find();
    const onMove = () => requestAnimationFrame(measure);
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      window.clearTimeout(frame);
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, [active, step, onRoute]);

  useEffect(() => {
    if (active) headingRef.current?.focus();
  }, [active, index]);

  const finish = useCallback(() => {
    stop();
    toast.success(t.finishedToast);
  }, [stop, t]);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "Escape") stop();
      else if (e.key === "ArrowRight") {
        if (index < steps.length - 1) go(index + 1);
        else finish();
      } else if (e.key === "ArrowLeft" && index > 0) go(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, index, steps.length, go, stop, finish]);

  if (!active || !step) return null;
  const last = index === steps.length - 1;
  const pad = 6;

  return (
    <>
      {rect && onRoute ? (
        <div
          aria-hidden
          className="pointer-events-none fixed z-40 rounded-xl outline-2 outline-offset-0 outline-accent transition-all duration-300 ease-out [outline-style:solid]"
          style={{
            top: rect.top - pad,
            left: rect.left - pad,
            width: rect.width + pad * 2,
            height: rect.height + pad * 2,
            boxShadow: "0 0 0 9999px rgb(10 15 30 / 0.45)",
          }}
        />
      ) : null}
      <AnimatePresence mode="wait">
        <motion.section
          key={step.id}
          role="dialog"
          aria-modal="false"
          aria-labelledby="tour-step-title"
          aria-describedby="tour-step-body"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
          data-print-hide
          className="fixed inset-x-3 bottom-3 z-50 flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 shadow-lg sm:inset-x-auto sm:right-5 sm:bottom-5 sm:w-[25rem]"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-2xs font-semibold tracking-wide text-accent-text uppercase">
              <Compass className="size-3.5" aria-hidden />
              {t.title} · {t.step(index + 1, steps.length)}
            </p>
            <Button variant="ghost" size="icon-sm" onClick={stop} aria-label={t.skip}>
              <X aria-hidden />
            </Button>
          </div>
          <div className="flex gap-1" aria-hidden>
            {steps.map((s, i) => (
              <span key={s.id} className={cn("h-1 flex-1 rounded-full transition-colors", i <= index ? "bg-accent" : "bg-surface-3")} />
            ))}
          </div>
          <h2 id="tour-step-title" ref={headingRef} tabIndex={-1} className="text-base leading-snug font-semibold outline-none">
            {step.title[locale]}
          </h2>
          <p id="tour-step-body" className="text-sm leading-relaxed text-muted-foreground">
            {step.body[locale]}
          </p>
          <p className="text-2xs text-subtle-foreground">
            {t.context}: {SCENARIO_LABELS[step.scenario][locale]} · {ROLE_LABELS[step.role][locale]}
          </p>
          {missing && onRoute ? (
            <div role="status" className="flex items-start gap-2 rounded-lg border border-dashed border-border-strong bg-surface-2 p-2.5 text-xs">
              <Construction className="mt-0.5 size-3.5 shrink-0 text-neutral-fg" aria-hidden />
              <div>
                <p className="font-semibold">{t.notBuilt}</p>
                <p className="text-muted-foreground">{t.notBuiltHint(step.owner)}</p>
              </div>
            </div>
          ) : null}
          <div className="flex items-center justify-between gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={stop}>
              {t.skip}
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => go(index - 1)} disabled={index === 0}>
                <ArrowLeft aria-hidden /> {t.back}
              </Button>
              <Button variant="accent" size="sm" onClick={() => (last ? finish() : go(index + 1))}>
                {last ? t.finish : t.next} {last ? null : <ArrowRight aria-hidden />}
              </Button>
            </div>
          </div>
          <p className="sr-only">{t.keyboard}</p>
        </motion.section>
      </AnimatePresence>
    </>
  );
}
