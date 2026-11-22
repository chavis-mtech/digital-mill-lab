"use client";

import { Suspense, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { LocaleProvider } from "@/lib/i18n/client";
import type { Locale } from "@/lib/i18n/config";
import { ThemeProvider } from "@/lib/theme/theme";
import { DemoProvider } from "@/lib/demo/context";
import { isApiRequestError } from "@/lib/api/errors";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/toast";
import { TourProvider } from "@/components/tour/tour";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        // Never retry contract stubs (501), auth/validation errors or rate limits; retry network blips once.
        retry: (count, error) => {
          if (isApiRequestError(error) && (error.isNotImplemented || (error.status >= 400 && error.status < 500))) return false;
          return count < 1;
        },
      },
    },
  });
}

export function Providers({ locale, children }: { locale: Locale; children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  return (
    <LocaleProvider initialLocale={locale}>
      <ThemeProvider>
        <QueryClientProvider client={client}>
          <MotionConfig reducedMotion="user">
            <TooltipProvider>
              <Suspense fallback={null}>
                <DemoProvider>
                  <TourProvider>{children}</TourProvider>
                </DemoProvider>
              </Suspense>
              <Toaster />
            </TooltipProvider>
          </MotionConfig>
        </QueryClientProvider>
      </ThemeProvider>
    </LocaleProvider>
  );
}
