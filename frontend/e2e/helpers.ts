import { Page, expect, request as playwrightRequest } from "@playwright/test";

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

/** Emails of leads this worker has submitted, so cleanupSubmittedLeads can remove them. */
const submittedLeadEmails: string[] = [];

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
  submittedLeadEmails.push(lead.email.toLowerCase());
}

/**
 * Delete every lead this worker submitted, so test runs don't clutter the real
 * leads list. Verifies each one actually landed in the list before removing it.
 * Call from test.afterAll in any spec that submits leads.
 */
export async function cleanupSubmittedLeads() {
  if (submittedLeadEmails.length === 0) return;
  const api = await playwrightRequest.newContext({ baseURL: API_URL });
  try {
    const login = await api.post("/api/auth/login", {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    expect(login.ok(), "cleanup login should succeed").toBeTruthy();
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };

    const list = await api.get("/api/leads?limit=200", { headers });
    expect(list.ok(), "cleanup lead listing should succeed").toBeTruthy();
    const items: Array<{ id: string; email: string }> = (await list.json()).items;

    for (const email of submittedLeadEmails.splice(0)) {
      const lead = items.find((item) => item.email === email);
      expect(lead, `submitted lead ${email} should appear in the list`).toBeTruthy();
      const deleted = await api.delete(`/api/leads/${lead!.id}`, { headers });
      expect(deleted.status(), `deleting lead ${email}`).toBe(204);
    }
  } finally {
    await api.dispose();
  }
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
