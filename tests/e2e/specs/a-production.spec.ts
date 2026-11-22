import { API, demo, expect, test, text } from "./fixtures";

/** Scenario A — NORMAL_DAY baseline → OER_DEGRADATION: KPIs change, anomaly evidence, scenario simulator from the API. */

test("A1: executive OER KPI changes from NORMAL_DAY to OER_DEGRADATION (values match the API)", async ({ en: page }) => {
  await page.goto(demo("/demo/executive", "NORMAL_DAY", "2026-10-21T08:00:00Z", "executive"));
  await expect(page.locator("[data-tour=exec-kpi-oer]")).toContainText("18.45%");
  await expect(page.locator("[data-tour=exec-insight-summary]")).toContainText("No rule-based finding at this moment");

  await page.goto(demo("/demo/executive", "OER_DEGRADATION", "2026-10-02T09:00:00Z", "executive"));
  const oer = page.locator("[data-tour=exec-kpi-oer]");
  await expect(oer).toContainText("17.64%");
  await expect(oer).toContainText("worse");
  await expect(page.locator("[data-tour=exec-insight-summary]")).toContainText("Production anomaly: Total oil loss");

  for (const [scn, at, want] of [["NORMAL_DAY", "2026-10-21T08:00:00Z", "18.45"], ["OER_DEGRADATION", "2026-10-02T09:00:00Z", "17.64"]]) {
    const k = await (await fetch(`${API}/api/v1/executive/kpis?scenario_id=${scn}&as_of=${at}`, { headers: { "X-Demo-Role": "executive" } })).json();
    expect(k.kpis.find((x: { key: string }) => x.key === "oer_pct").value.toFixed(2)).toBe(want);
  }
});

test("A2: AI insights shows anomaly evidence with observed vs expected and 'not proven causes'", async ({ en: page }) => {
  await page.goto(demo("/demo/palm-mill/ai-insights", "OER_DEGRADATION", "2026-10-02T09:00:00Z", "production_engineer"));
  const ev = page.locator("[data-tour=palm-anomaly-evidence]");
  await expect(ev).toContainText("Total oil loss (% FFB)");
  const t = await text(page, "[data-tour=palm-anomaly-evidence]");
  expect(t).toMatch(/Observed 1\.65 % FFB Expected 1\.03 % FFB/);
  expect(t).toContain("Clarifier temperature");
  expect(t).toMatch(/not proven causes/i);
});

test("A3: scenario simulator shows the baselines and formulas returned by the API (UI computes nothing)", async ({ en: page }) => {
  // The page may fire one request with the default clock before it has read ?as_of= from the URL; the response that
  // matters is the one computed at the clock under test (as_of=2026-10-02), which is what the page finally renders.
  const base = page.waitForResponse((r) => r.url().includes("/api/v1/scenarios/production/calculate") && r.url().includes("as_of=2026-10-02") && r.request().method() === "POST" && r.status() === 200);
  await page.goto(demo("/demo/scenarios", "OER_DEGRADATION", "2026-10-02T09:00:00Z", "factory_manager"));
  const body = await (await base).json();
  const mainEl = page.locator("main");
  // wait for the page to render the API result (it shows "Calculating…" first; under CPU load that takes a while)
  await expect(mainEl).toContainText("the UI computes nothing itself", { timeout: 20_000 });
  // the baselines printed on the page are the ones the API returned (trailing 30 days at the demo clock)
  const b = body.baseline_inputs as Record<string, number>;
  await expect(mainEl).toContainText(new RegExp(`OER \\(%\\)\\s*Baseline: ${b.oer_pct!.toFixed(2).replace(".", "\\.")}`), { timeout: 20_000 }); // label and value are adjacent elements (no space in textContent)
  await expect(mainEl).toContainText(new RegExp(`Availability \\(%\\)\\s*Baseline: ${b.availability_pct!.toFixed(2).replace(".", "\\.")}`), { timeout: 20_000 });
  expect(Array.isArray(body.formulas) && body.formulas.length > 0).toBe(true);
});
