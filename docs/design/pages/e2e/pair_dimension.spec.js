// Fase 10 · N4 + N5 — dimensão de par nas telas existentes.
// N4: HITL ganha mini-contexto do par (preço/regime) + filtro por par na fila.
// N5: Ordens ganham o rodapé de P&L realizado por par no modo ∑.
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
});

test("N4 — HITL: cada ordem mostra o mini-contexto do par (preço atual)", async ({ page }) => {
  await page.goto("/#hitl");
  await expect(page.locator(".page-title")).toContainText("HITL Controls");
  await expect(page.locator(".hitl-ctx").first()).toContainText("Agora");
});

test("N4 — HITL: a fila filtra por par (chips com contagem)", async ({ page }) => {
  await page.goto("/#hitl");
  // 2 ordens pendentes em 2 pares → chips aparecem.
  await expect(page.locator(".hitl-chips")).toBeVisible();
  await expect(page.locator(".chip-btn", { hasText: "Todos" })).toBeVisible();
  const all = await page.locator(".hitl-ctx").count();
  expect(all).toBeGreaterThan(1);            // a fila mistura pares
  await page.locator(".chip-btn", { hasText: "BTC/USDT" }).click();
  const btc = await page.locator(".hitl-ctx").count();
  expect(btc).toBeGreaterThan(0);
  expect(btc).toBeLessThan(all);             // filtrou fora os outros pares
  await page.locator(".chip-btn", { hasText: "Todos" }).click();
  await expect(page.locator(".hitl-ctx")).toHaveCount(all);  // "Todos" restaura
});

test("N5 — Ordens: rodapé de P&L realizado por par no modo ∑", async ({ page }) => {
  await page.goto("/#orders");
  // Entra no modo Portfólio (∑) pelo seletor de par.
  await page.locator(".pair-btn").click();
  await page.locator(".pair-opt", { hasText: "Portfólio (∑)" }).click();
  const footer = page.locator(".pnl-by-pair");
  await expect(footer).toBeVisible();
  await expect(footer).toContainText("P&L realizado por par");
  await expect(footer).toContainText("trades fechados");
  await expect(footer.locator(".pnl-by-pair-cell", { hasText: "BTC/USDT" })).toBeVisible();
});
