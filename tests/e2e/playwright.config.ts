import { existsSync } from "node:fs";
import { defineConfig, devices } from "@playwright/test";

/**
 * Acceptance scenarios A–E (docs/SPEC.md §15) against LOCAL servers:
 *   web  E2E_BASE_URL (default http://localhost:3109, production build)
 *   api  E2E_API_URL  (default http://localhost:8109, on a COPY of the snapshot DB — see run-servers.sh)
 * Tests run serially (one shared DB copy) and reset their own sandbox sessions afterwards.
 *
 * Browser: Playwright's own Chromium (`pnpm --dir tests/e2e exec playwright install chromium`), or an
 * existing browser build via PW_CHROMIUM_PATH. Without it Playwright uses the browser it installed itself.
 */
const cached = process.env.PW_CHROMIUM_PATH;
const executablePath = cached && existsSync(cached) ? cached : undefined;

export default defineConfig({
  testDir: "./specs",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3109",
    viewport: { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "Asia/Bangkok",
    trace: "retain-on-failure",
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
