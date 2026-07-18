// A1 auth flows against the built console (mock data, no backend).
// MOCK_AUTH='none' boots unauthenticated (login card); default auto-authenticates.
import { test, expect } from "@playwright/test";

test("unauthenticated boot shows the login card, not the shell", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "none";
  });
  await page.goto("/");
  await expect(page.locator(".auth-card")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
  await expect(page.locator(".nav-item")).toHaveCount(0);
});

test("deep links are also gated when unauthenticated", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "none";
  });
  await page.goto("/#market");
  await expect(page.locator(".auth-card")).toBeVisible();
  await expect(page.locator(".nav-item")).toHaveCount(0);
});

test("authenticated boot renders the shell with the user menu", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/");
  await expect(page.locator(".brand-name")).toBeVisible();
  const chip = page.getByTestId("user-menu");
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page.locator(".user-menu")).toContainText("demo@criptotrade.dev");
  await expect(page.locator(".user-menu")).toContainText("Sair");
});

test("forgot-password stage is reachable from the login card", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "none";
  });
  await page.goto("/");
  await page.getByText("Esqueci a senha").click();
  await expect(page.getByRole("heading", { name: "Recuperar acesso" })).toBeVisible();
});
