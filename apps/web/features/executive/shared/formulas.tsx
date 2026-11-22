"use client";

import type { ComponentProps } from "react";
import { FormulaPanel as KitFormulaPanel } from "@/components/data/formula-panel";

/**
 * Kit FormulaPanel with wrapping expressions: the kit's `<code class="overflow-x-auto whitespace-pre">` becomes a
 * non-focusable scroll region on phones (axe scrollable-region-focusable). Wrapping removes the scroll region.
 * Kit fix requested in docs/status/frontend-exec.md.
 */
export function FormulaPanel(props: ComponentProps<typeof KitFormulaPanel>) {
  return (
    <div className="min-w-0 [&_code]:break-words [&_code]:whitespace-pre-wrap">
      <KitFormulaPanel {...props} />
    </div>
  );
}
