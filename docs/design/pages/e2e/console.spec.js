// E2E smoke for the React console (P3-5b). Runs against the built dist/ with
// mock data, so it exercises the real shell + hash routing without a backend.
import { test, expect } from "@playwright/test";

const NAV = [
  // N2: "Mesa" (multi-asset hub) is the first Operação item and the landing
  // when the loop trades >1 pair — the mock operates 5, so it lands here.
  "Mesa", "Visão Geral", "HITL Controls", "Ordens", "Agentes", "Risco",
  "Mercado", "Observabilidade", "Diário", "Backtest", "Config",
];
// A2/A3/A4/A5/A6/A7: the mock user is an admin, so the Administração group adds these items.
const ADMIN_NAV = ["Conta & Perfil", "Usuários & Permissões", "Conexões & Chaves",
  "Trilha de Auditoria", "Notificações & Canais", "Segurança & Sessões"];

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

test("default landing is the Mesa when >1 pair is operated (N2)", async ({ page }) => {
  // Mock operates 5 pairs → Mesa is the landing (par único mantém Visão Geral).
  await page.goto("/");
  await expect(page).toHaveURL(/#desk$/);
  await expect(page.locator(".nav-item.active")).toContainText("Mesa");
  await expect(page.locator(".page-title")).toContainText("Mesa Multi-Ativo");
});

test("single operated pair keeps Visão Geral as the landing", async ({ page }) => {
  await page.addInitScript(() => { window.MOCK_OPERATED = ["BTC/USDT"]; });
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
