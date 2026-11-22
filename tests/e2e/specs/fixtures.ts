import { test as base, expect, type Page } from "@playwright/test";

export const API = process.env.E2E_API_URL ?? "http://localhost:8109";
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3109";

/**
 * Every test gets a fresh browser context (cold open: no localStorage), the English UI (cookie `dml_locale=en`),
 * and afterwards its sandbox session is reset through POST /api/v1/demo/session/reset (work orders, copilot
 * conversations and other session rows are deleted; the audit log is kept by design).
 */
export const test = base.extend<{ en: Page }>({
  en: async ({ page, context }, use) => {
    await context.addCookies([{ name: "dml_locale", value: "en", url: BASE }]);
    await use(page);
    const sessions = new Set<string>();
    for (const p of context.pages()) {
      const id = await p.evaluate(() => window.localStorage.getItem("dml_demo_session")).catch(() => null);
      if (id) sessions.add(id);
    }
    for (const id of sessions) {
      const r = await fetch(`${API}/api/v1/demo/session/reset`, { method: "POST", headers: { "X-Demo-Session": id } });
      expect(r.status, `reset session ${id}`).toBe(200);
    }
  },
});

export { expect };

/** Demo URL with scenario / clock / simulated role in the query string (the app reads them on load). */
export function demo(path: string, scenario: string, asOf: string | null, role: string) {
  const q = new URLSearchParams({ scenario, role });
  if (asOf) q.set("as_of", asOf);
  return `${path}?${q.toString()}`;
}

/** Collapse whitespace so assertions do not depend on layout line breaks. */
export async function text(page: Page, selector: string) {
  return (await page.locator(selector).first().innerText()).replace(/\s+/g, " ");
}
