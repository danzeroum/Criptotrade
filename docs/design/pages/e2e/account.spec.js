// A2 account & profile: the avatar menu opens Conta · Segurança · Sair, the
// regional-format preference is ONE control whose live preview proves the
// acceptance (numbers/dates re-format), e-mail is read-only, and the public
// demo has no account to manage.
import { test, expect } from "@playwright/test";

test("avatar menu opens Conta, Segurança and Sair; Conta navigates", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/");
  await page.getByTestId("user-menu").click();
  const menu = page.getByRole("menu");
  await expect(menu.getByRole("menuitem", { name: "Conta" })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "Segurança" })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "Sair" })).toBeVisible();
  await menu.getByRole("menuitem", { name: "Conta" }).click();
  await expect(page).toHaveURL(/#account$/);
  await expect(page.locator(".page-title")).toContainText("Conta & Perfil");
});

test("regional format is one control and the live preview re-formats", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#account");
  const preview = page.getByTestId("prefs-preview");
  // Default ('auto') keeps the M7 canon: en-US numbers.
  await expect(preview).toContainText("1,234.56");
  await page.getByLabel("Formato regional").selectOption("pt-BR");
  await expect(preview).toContainText("1.234,56");
  await page.getByLabel("Formato regional").selectOption("en-US");
  await expect(preview).toContainText("1,234.56");
});

test("saving pt-BR format re-formats numbers across the console (mock)", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#account");
  await page.getByLabel("Formato regional").selectOption("pt-BR");
  await page.getByRole("button", { name: "Salvar preferências" }).click();
  // Cross-screen proof: the header price (fmtPrice) now renders pt-BR grouping.
  await expect(page.locator(".header")).toContainText("$67.667");
});

test("e-mail field is read-only with the deferral explained", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#account");
  const email = page.locator('input[value="demo@criptotrade.dev"]');
  await expect(email).toBeDisabled();
});

test("public demo has no account: nav hidden, deep-link 403", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "demo";
  });
  await page.goto("/#account");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Conta & Perfil" })).toHaveCount(0);
});
