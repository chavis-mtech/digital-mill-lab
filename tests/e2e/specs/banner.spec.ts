import { expect, test } from "@playwright/test";
import { API } from "./fixtures";

/**
 * Claim (CLAIMS_LEDGER row 35): every page carries a visible "Synthetic data" banner with the independence notice.
 * Visits every route of the production build (/ui-kit excluded: internal component gallery) in TH and EN and
 * fails with the list of routes where the banner is missing or not visible.
 */
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3109";
const ROUTES = [
  "/", "/about-project", "/business-opportunities", "/technical-architecture", "/implementation-roadmap", "/developer", "/contact",
  "/demo", "/demo/executive", "/demo/business-impact", "/demo/scenarios", "/demo/palm-mill", "/demo/palm-mill/process",
  "/demo/palm-mill/analytics", "/demo/palm-mill/ai-insights", "/demo/maintenance", "/demo/maintenance/equipment",
  "/demo/maintenance/work-orders", "/demo/logistics", "/demo/energy", "/demo/traceability", "/demo/ai-copilot", "/demo/prototypes",
  "/docs/overview", "/docs/architecture", "/docs/data-model", "/docs/ai-methodology", "/docs/integration", "/docs/security", "/docs/roadmap",
];
const TEXT = {
  th: "ข้อมูลสังเคราะห์ — แนวคิดอิสระ ไม่ใช่ข้อมูลของบริษัทใด ๆ",
  en: "Synthetic data — independent concept, not any company's data",
} as const;

for (const locale of ["th", "en"] as const) {
  test(`banner: every route shows the synthetic-data / independence banner (${locale})`, async ({ page, context }) => {
    test.setTimeout(240_000);
    await context.addCookies([{ name: "dml_locale", value: locale, url: BASE }]);
    const missing: string[] = [];
    for (const route of ROUTES) {
      const res = await page.goto(route, { waitUntil: "domcontentloaded" });
      if (!res || res.status() !== 200) {
        missing.push(`${route} (HTTP ${res?.status()})`);
        continue;
      }
      const banner = page.locator("[data-synthetic-banner]").first();
      try {
        await expect(banner).toBeVisible({ timeout: 10_000 });
        await expect(banner).toContainText(TEXT[locale]);
      } catch {
        missing.push(route);
      }
    }
    // clean up the sandbox session the demo pages created
    const id = await page.evaluate(() => localStorage.getItem("dml_demo_session")).catch(() => null);
    if (id) await fetch(`${API}/api/v1/demo/session/reset`, { method: "POST", headers: { "X-Demo-Session": id } });
    expect(missing, `routes without a visible banner (${locale})`).toEqual([]);
  });
}
