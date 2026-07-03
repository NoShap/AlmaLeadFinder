import { Page, expect } from "@playwright/test";

export const API_URL = process.env.API_URL ?? "http://localhost:8000";
// Defaults mirror the fallback credentials in docker-compose.yml / .env.example;
// override with env vars when the stack runs with different ones.
export const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "attorney@example.com";
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "Password1234!";

/** A minimal but valid-enough PDF payload for the resume upload. */
export function fakeResume(name: string) {
  return {
    name,
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 fake resume for e2e tests"),
  };
}

/** Fill and submit the public lead form; resolves once the success panel shows. */
export async function submitLeadViaForm(
  page: Page,
  lead: { firstName: string; lastName: string; email: string; resumeName?: string }
) {
  await page.goto("/");
  await page.getByLabel("First name").fill(lead.firstName);
  await page.getByLabel("Last name").fill(lead.lastName);
  await page.getByLabel("Email").fill(lead.email);
  await page
    .getByLabel("Resume / CV")
    .setInputFiles(fakeResume(lead.resumeName ?? "resume.pdf"));
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByRole("heading", { name: "Thanks — we got it!" })).toBeVisible();
}

/** Sign in with the fallback credentials; resolves on the dashboard. */
export async function loginAsAttorney(page: Page) {
  await page.goto("/admin/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { name: "Leads" })).toBeVisible();
}

/** Unique-per-run identity so tests can find their own rows in a shared database. */
export function uniqueLead(tag: string) {
  const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  return {
    firstName: `E2E-${tag}`,
    lastName: stamp,
    email: `e2e-${tag}-${stamp}@example.com`,
    resumeName: `resume-${stamp}.pdf`,
  };
}
