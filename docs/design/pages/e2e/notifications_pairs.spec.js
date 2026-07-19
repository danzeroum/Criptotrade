// N7 — regras de notificação ganham escopo de par (pairs). Regra escopada
// mostra "só <par>"; o editor de nova regra oferece "Todos" + os pares da
// fonte dinâmica (N1). Mock data.
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#notifications");
});

test("uma regra escopada por par mostra o badge 'só <par>'", async ({ page }) => {
  await expect(page.locator(".page-title")).toContainText("Notificações & Canais");
  await expect(page.getByText("só BTC/USDT")).toBeVisible();
});

test("o editor de nova regra oferece 'Todos' + os pares da fonte dinâmica", async ({ page }) => {
  await page.getByRole("button", { name: "Nova regra" }).click();
  await expect(page.getByText("Pares", { exact: true })).toBeVisible();
  // Default = Todos os pares (retrocompatível).
  await expect(page.getByText("Todos", { exact: true })).toBeVisible();
  // Desmarcar "Todos" revela os pares individuais (BTC entre eles).
  await page.getByText("Todos", { exact: true }).locator("input[type=checkbox]").uncheck();
  await expect(page.getByText("BTC/USDT").first()).toBeVisible();
});
