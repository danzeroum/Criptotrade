// E2E smoke for the React console (P3-5b). Runs against the built dist/ with
// mock data, so it exercises the real shell + hash routing without a backend.
import { test, expect } from "@playwright/test";

const NAV = [
  "Visão Geral", "HITL Controls", "Ordens", "Agentes", "Risco",
  "Mercado", "Observabilidade", "Diário", "Backtest", "Config",
];
// A3: the mock user is an admin, so the Administração group adds these items.
const ADMIN_NAV = ["Usuários & Permissões"];

test.beforeEach(async ({ page }) => {
  // Screens read window.USE_MOCK_DATA and render mock data instead of fetching.
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
});

test("loads the app shell with the full navigation", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/");

  await expect(page.locator(".brand-name")).toContainText("Criptotrade");
  await expect(page.locator(".nav-item")).toHaveCount(NAV.length + ADMIN_NAV.length);
  for (const label of NAV) {
    await expect(page.locator(".nav-item", { hasText: label }).first()).toBeVisible();
  }
  expect(errors, `uncaught page errors: ${errors.join("; ")}`).toEqual([]);
});

test("default screen is Visão Geral and marked active", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".nav-item.active")).toContainText("Visão Geral");
});

test("clicking a nav item routes via the hash and updates the active item", async ({ page }) => {
  await page.goto("/");

  await page.locator(".nav-item", { hasText: "Risco" }).first().click();
  await expect(page).toHaveURL(/#risk$/);
  await expect(page.locator(".nav-item.active")).toContainText("Risco");

  await page.locator(".nav-item", { hasText: "Mercado" }).first().click();
  await expect(page).toHaveURL(/#market$/);
  await expect(page.locator(".nav-item.active")).toContainText("Mercado");
});

test("deep-linking via the URL hash opens that screen", async ({ page }) => {
  await page.goto("/#backtest");
  await expect(page.locator(".nav-item.active")).toContainText("Backtest");
});
