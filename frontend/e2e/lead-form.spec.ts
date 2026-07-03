import { test, expect } from "@playwright/test";
import { fakeResume, submitLeadViaForm, uniqueLead } from "./helpers";

test.describe("public lead form", () => {
  test("renders the assessment form", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Get an assessment" })).toBeVisible();
    await expect(page.getByLabel("First name")).toBeVisible();
    await expect(page.getByLabel("Last name")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Resume / CV")).toBeVisible();
  });

  test("native validation blocks an empty submit", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Submit" }).click();
    // Required fields keep the browser from submitting; we stay on the form.
    await expect(page.getByRole("heading", { name: "Get an assessment" })).toBeVisible();
    const firstNameInvalid = await page
      .getByLabel("First name")
      .evaluate((el: HTMLInputElement) => !el.checkValidity());
    expect(firstNameInvalid).toBe(true);
  });

  test("submits a lead and shows the success panel", async ({ page }) => {
    await submitLeadViaForm(page, uniqueLead("form"));
    await expect(page.getByText("Check your inbox for a confirmation")).toBeVisible();
  });

  test("'Submit another' returns to a fresh form", async ({ page }) => {
    await submitLeadViaForm(page, uniqueLead("again"));
    await page.getByRole("button", { name: "Submit another" }).click();
    await expect(page.getByRole("heading", { name: "Get an assessment" })).toBeVisible();
    await expect(page.getByLabel("First name")).toHaveValue("");
  });

  test("rejects an unsupported resume type with a field error", async ({ page }) => {
    const lead = uniqueLead("badfile");
    await page.goto("/");
    await page.getByLabel("First name").fill(lead.firstName);
    await page.getByLabel("Last name").fill(lead.lastName);
    await page.getByLabel("Email").fill(lead.email);
    await page.getByLabel("Resume / CV").setInputFiles({
      name: "resume.exe",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("not a resume"),
    });
    await page.getByRole("button", { name: "Submit" }).click();
    // Whatever the backend's exact message, the form must surface an error
    // and must not flip to the success panel.
    await expect(page.locator(".form-error, .field-error").first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Thanks — we got it!" })
    ).not.toBeVisible();
  });
});
