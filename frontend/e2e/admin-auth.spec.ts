import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, loginAsAttorney } from "./helpers";

test.describe("admin authentication", () => {
  test("visiting /admin without a session redirects to login", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/admin\/login$/);
    await expect(page.getByRole("heading", { name: "Attorney sign in" })).toBeVisible();
  });

  test("rejects bad credentials with an error message", async ({ page }) => {
    await page.goto("/admin/login");
    await page.getByLabel("Email").fill(ADMIN_EMAIL);
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.locator(".form-error")).toBeVisible();
    await expect(page).toHaveURL(/\/admin\/login$/);
  });

  test("signs in with fallback credentials and reaches the dashboard", async ({ page }) => {
    await loginAsAttorney(page);
  });

  test("sign out clears the session and re-gates /admin", async ({ page }) => {
    await loginAsAttorney(page);
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/admin\/login$/);
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/admin\/login$/);
  });
});
