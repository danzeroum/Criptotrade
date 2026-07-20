// A1 auth flows against the built console, driven by the fail-loud e2e API fixture
// (page.route interception — production takes the REAL apiClient path, no in-app
// mock branch, no backend). Auth scenarios come from the /v1/auth/me stub, which
// replaces the old window.MOCK_AUTH / MOCK_ROLE globals.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test("unauthenticated boot shows the login card, not the shell", async ({ page }) => {
  await installMockApi(page, { authMode: "none" });
  await page.goto("/");
  await expect(page.locator(".auth-card")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Entrar" })).toBeVisible();
  await expect(page.locator(".nav-item")).toHaveCount(0);
});

test("deep links are also gated when unauthenticated", async ({ page }) => {
  await installMockApi(page, { authMode: "none" });
  await page.goto("/#market");
  await expect(page.locator(".auth-card")).toBeVisible();
  await expect(page.locator(".nav-item")).toHaveCount(0);
});

test("authenticated boot renders the shell with the user menu", async ({ page }) => {
  await installMockApi(page, { authMode: "user" });
  await page.goto("/");
  await expect(page.locator(".brand-name")).toBeVisible();
  const chip = page.getByTestId("user-menu");
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page.locator(".user-menu")).toContainText("demo@criptotrade.dev");
  await expect(page.locator(".user-menu")).toContainText("Sair");
});

test("forgot-password stage is reachable from the login card", async ({ page }) => {
  await installMockApi(page, { authMode: "none" });
  await page.goto("/");
  await page.getByText("Esqueci a senha").click();
  await expect(page.getByRole("heading", { name: "Recuperar acesso" })).toBeVisible();
});
