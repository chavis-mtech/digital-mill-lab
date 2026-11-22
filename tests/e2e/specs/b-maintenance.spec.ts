import { API, demo, expect, test, text } from "./fixtures";

/** Scenario B — maintenance alert → work order lifecycle → audit trail (PRESS_VIBRATION_ANOMALY, 2026-11-20 08:00Z). */
const SCN = "PRESS_VIBRATION_ANOMALY";
const AT = "2026-11-20T08:00:00Z";

test("B1: PRS-03 is critical with sensor evidence (equipment page, ?equipment_id=PRS-03)", async ({ en: page }) => {
  await page.goto(demo("/demo/maintenance/equipment", SCN, AT, "maintenance_engineer") + "&equipment_id=PRS-03");
  const registry = page.getByRole("region", { name: "Equipment registry" });
  const row = registry.getByRole("row").filter({ hasText: "PRS-03" }).first();
  await expect(row).toContainText("Critical");
  await expect(row).toContainText("PRS-03-VIB-DE >= crit limit 4.5 mm/s");
  // the detail panel follows the URL parameter (code form)
  await expect(page.locator("[data-tour=equipment-sensor-trend]")).toBeVisible();
  await expect(page.getByRole("heading", { level: 2 }).filter({ hasText: "PRS-03" }).first()).toBeVisible();
});

test("B2: alert → work order → assign → in progress → resolved, audit chain verified", async ({ en: page }) => {
  await page.goto(demo("/demo/maintenance/work-orders", SCN, AT, "maintenance_engineer"));
  const eq = page.locator("select").filter({ has: page.locator("option", { hasText: "PRS-03 — Twin-screw press 3" }) }).first();
  await eq.selectOption("18");
  const src = page.locator("select").filter({ has: page.locator("option", { hasText: "ALR-20261119-0018" }) }).first();
  const alertValue = await src.locator("option", { hasText: "ALR-20261119-0018" }).getAttribute("value");
  await src.selectOption(alertValue!);
  // the form is pre-filled from the alert (title + evidence)
  await expect(page.getByLabel("Title", { exact: true })).toHaveValue(/PRS-03-VIB-DE HIGH-HIGH \(critical\)/);

  const created = page.waitForResponse((r) => r.url().includes("/api/v1/work-orders") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Create work order", exact: true }).click();
  await page.getByRole("button", { name: "Confirm and create" }).click();
  const wo = await (await created).json();
  expect((await created).status()).toBe(201);
  expect(wo.code).toMatch(/^WO-\d{6}-\d{4}$/);
  expect(wo.status).toBe("open");
  await expect(page.getByText(`${wo.code} created`, { exact: true })).toBeVisible();

  const detail = page.getByRole("heading", { name: wo.code, exact: true });
  await expect(detail).toBeVisible();

  // assign Technician M-03
  const tech = page.locator("select").filter({ has: page.locator("option", { hasText: "Technician M-03" }) }).first();
  await tech.selectOption({ index: await tech.locator("option").evaluateAll((os) => os.findIndex((o) => o.textContent!.includes("Technician M-03"))) });
  await page.getByRole("button", { name: "Assign", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("button", { name: "Move to In progress" })).toBeVisible();

  await page.getByRole("button", { name: "Move to In progress" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm", exact: true }).click();

  // resolve needs resolution notes
  const resolve = page.getByRole("button", { name: "Move to Resolved" });
  await expect(resolve).toBeDisabled();
  await page.getByLabel("Resolution notes (required to resolve)").fill("Replaced drive-end bearing; vibration back to normal (e2e).");
  await expect(resolve).toBeEnabled();
  await resolve.click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Confirm", exact: true }).click();

  await expect(page.getByText("Hash chain verified")).toBeVisible();
  const panel = page.locator("section, div").filter({ has: detail }).filter({ hasText: "Audit trail" }).last();
  await expect(panel).toContainText("work_order.transition");
  for (const action of ["work_order.create", "work_order.assign", "alert.status_change"]) await expect(panel).toContainText(action);

  // the API agrees (same sandbox session)
  const session = await page.evaluate(() => localStorage.getItem("dml_demo_session"));
  const r = await fetch(`${API}/api/v1/work-orders/${wo.id}/audit`, { headers: { "X-Demo-Role": "maintenance_engineer", "X-Demo-Session": session! } });
  const audit = await r.json();
  expect(audit.chain_verified).toBe(true);
  const d = await (await fetch(`${API}/api/v1/work-orders/${wo.id}?as_of=${AT}&scenario_id=${SCN}`, { headers: { "X-Demo-Role": "maintenance_engineer", "X-Demo-Session": session! } })).json();
  expect(d.status).toBe("resolved");
  expect(d.history.map((h: { to_status: string }) => h.to_status)).toEqual(["open", "assigned", "in_progress", "resolved"]);
  expect(d.resolution_notes).toContain("Replaced drive-end bearing");
  expect(d.assigned_technician?.name ?? JSON.stringify(d.assigned_technician)).toContain("M-03");
});

test("B3: Public Viewer cannot create a work order (UI gate + API 403)", async ({ en: page }) => {
  await page.goto(demo("/demo/maintenance/work-orders", SCN, AT, "public_viewer"));
  await expect(page.getByRole("button", { name: "Create work order", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Switch to Maintenance engineer/i })).toBeVisible();
  const session = await (await page.waitForFunction(() => localStorage.getItem("dml_demo_session"))).jsonValue();
  const r = await fetch(`${API}/api/v1/work-orders`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Demo-Role": "public_viewer", "X-Demo-Session": session! },
    body: JSON.stringify({ equipment_id: 18, title: "e2e", source: "manual", priority: "low", confirm: true }),
  });
  expect(r.status).toBe(403);
  expect((await r.json()).error.details).toEqual({ role: "public_viewer", permission: "workorder:create" });
  expect(await text(page, "main")).toContain("workorder:create");
});
