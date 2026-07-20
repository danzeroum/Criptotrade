// N3 — Risco ganha slots + exposição por par e o feed "decisões do ciclo"
// (por que um sinal não virou ordem). Dados servidos pelo fixture page.route.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test.beforeEach(async ({ page }) => {
  await installMockApi(page, { authMode: "user" });
});

test("slots + exposição por par aparecem no Risco", async ({ page }) => {
  await page.goto("/#risk");
  await expect(page.getByText("Slots & exposição por par")).toBeVisible();
  await expect(page.getByText("2 / 3 slots")).toBeVisible();
  // Barras de exposição por par (BTC domina).
  await expect(page.locator(".slot-row", { hasText: "BTC/USDT" })).toBeVisible();
  await expect(page.getByText(/Capital livre:/)).toBeVisible();
});

test("feed de skips mostra o motivo de cada sinal recusado", async ({ page }) => {
  await page.goto("/#risk");
  await expect(page.getByText("Decisões do ciclo")).toBeVisible();
  await expect(page.locator(".skip-row", { hasText: "ETH/USDT" })).toContainText("Confiança baixa");
  await expect(page.locator(".skip-row", { hasText: "XRP/USDT" })).toContainText("Sem slot livre");
  // Contador de repetições (×N) na persistência do mesmo motivo.
  await expect(page.getByText("×4")).toBeVisible();
});
