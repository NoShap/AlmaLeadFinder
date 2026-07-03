import { test, expect } from "@playwright/test";
import {
  cleanupSubmittedLeads,
  loginAsAttorney,
  submitLeadViaForm,
  uniqueLead,
} from "./helpers";

test.afterAll(async () => {
  await cleanupSubmittedLeads();
});

/**
 * The full product walk-through from the README demo: a prospect submits the
 * public form, then an attorney signs in, downloads the resume, and marks the
 * lead as reached out.
 */
test("prospect submits → attorney reviews, downloads resume, marks reached out", async ({
  page,
}) => {
  const lead = uniqueLead("journey");

  await test.step("prospect submits the public form", async () => {
    await submitLeadViaForm(page, lead);
  });

  await test.step("attorney signs in and sees the new lead as PENDING", async () => {
    await loginAsAttorney(page);
  });

  const row = page.getByRole("row", { name: new RegExp(lead.lastName) });

  await test.step("the lead row shows the submitted details", async () => {
    await expect(row).toBeVisible();
    await expect(row).toContainText(`${lead.firstName} ${lead.lastName}`);
    await expect(row).toContainText(lead.email);
    await expect(row.locator(".badge.pending")).toHaveText("PENDING");
  });

  await test.step("attorney downloads the resume", async () => {
    const downloadPromise = page.waitForEvent("download");
    await row.getByRole("button", { name: lead.resumeName }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(lead.resumeName);
  });

  await test.step("attorney marks the lead reached out", async () => {
    await row.getByRole("button", { name: "Mark reached out" }).click();
    await expect(row.locator(".badge.reached-out")).toHaveText("REACHED OUT");
    await expect(row.getByRole("button", { name: "Mark reached out" })).toHaveCount(0);
  });

  await test.step("the state survives a reload", async () => {
    await page.reload();
    const rowAfterReload = page.getByRole("row", { name: new RegExp(lead.lastName) });
    await expect(rowAfterReload.locator(".badge.reached-out")).toHaveText("REACHED OUT");
  });
});
