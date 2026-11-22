import { demo, expect, test, text } from "./fixtures";

/** Scenario C — truck queue congestion (TRUCK_QUEUE_CONGESTION, 2026-11-14 06:00Z): queue baseline → FIFO vs slots → limits. */
const URL = demo("/demo/logistics", "TRUCK_QUEUE_CONGESTION", "2026-11-14T06:00:00Z", "logistics_officer");

test("C1: queue at the demo clock shows 15 trucks waiting (observed)", async ({ en: page }) => {
  await page.goto(URL);
  const queue = page.locator("[data-tour=logistics-queue]");
  await expect(queue).toContainText(/Trucks waiting\s*15\s*trucks/);
  const t = await text(page, "[data-tour=logistics-queue]");
  expect(t).toMatch(/Trucks waiting 15 ?trucks/);
  expect(t).toMatch(/Trucks unloading 1 ?trucks/);
  expect(t).toMatch(/Average wait 57\.2/);
  expect(t).toContain("never an accusation");
});

test("C2: simulation shows observed vs simulated side by side with the honesty banner and limits", async ({ en: page }) => {
  await page.goto(URL);
  const sim = page.locator("[data-tour=logistics-simulation]");
  const resp = page.waitForResponse((r) => r.url().includes("/api/v1/logistics/") && r.request().method() === "POST");
  await sim.getByRole("button", { name: "Run simulation" }).click();
  const body = await (await resp).json();
  await expect(sim).toContainText("The simulation may not match what was observed");
  const t = (await sim.innerText()).replace(/\s+/g, " ");
  // observed and simulated values come from the same API response and are both shown
  expect(t).toMatch(/37\.4/); // observed average wait (min) for the day
  expect(t).toMatch(/Simulated FIFO/);
  expect(t).toMatch(/Simulated slots/);
  expect(t).toContain("Single replication per seed");
  expect(t).toContain("INFERRED");
  expect(JSON.stringify(body)).toContain("37.4");
});
