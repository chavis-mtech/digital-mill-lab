import { expect, test } from "./fixtures";

/** Scenario E — cold open of the public URL, the 7-step guided tour with Back/Skip, then architecture, developer, contact. */

test("E1: cold open → 7-step tour (every step highlights a real element) with Back and Finish", async ({ en: page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Intelligent Operations for a Smarter Industrial Future");
  await page.getByRole("button", { name: "Take the 5-minute tour" }).first().click();
  const dialog = page.getByRole("dialog");
  const expected = [
    "/demo/executive", "/demo/palm-mill/ai-insights", "/demo/maintenance/equipment", "/demo/maintenance",
    "/demo/maintenance/work-orders", "/demo/scenarios", "/demo/executive",
  ];
  const targets = [
    "exec-kpi-oer", "palm-anomaly-evidence", "equipment-sensor-trend", "maintenance-recommendation",
    "work-order-create", "scenario-impact", "exec-insight-summary",
  ];
  for (let i = 0; i < 7; i++) {
    await expect(dialog).toContainText(`Step ${i + 1} of 7`);
    await expect(page).toHaveURL(new RegExp(`${expected[i]!.replace(/\//g, "\\/")}\\?`));
    // the element the step highlights is really on the page (data-tour target from content/tour.ts)
    await expect(page.locator(`[data-tour="${targets[i]}"]`).first()).toBeVisible({ timeout: 20_000 });
    await expect(dialog).not.toContainText("This view is not built yet");
    if (i === 3) {
      await dialog.getByRole("button", { name: "Back" }).click();
      await expect(dialog).toContainText("Step 3 of 7");
      await dialog.getByRole("button", { name: "Next" }).click();
      await expect(dialog).toContainText("Step 4 of 7");
    }
    if (i < 6) await dialog.getByRole("button", { name: "Next" }).click();
  }
  await dialog.getByRole("button", { name: "Finish tour" }).click();
  await expect(dialog).toHaveCount(0);
});

test("E2: Skip closes the tour", async ({ en: page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Take the 5-minute tour" }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Step 1 of 7");
  await page.getByRole("dialog").getByRole("button", { name: "Skip tour", exact: true }).first().click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("E3: architecture, developer and contact pages load without setup", async ({ en: page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const path of ["/technical-architecture", "/developer", "/contact"]) {
    const r = await page.goto(path);
    expect(r?.status(), path).toBe(200);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator("[data-synthetic-banner]")).toBeVisible();
  }
  expect(errors).toEqual([]);
});
