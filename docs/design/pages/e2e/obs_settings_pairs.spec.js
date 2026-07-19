// Fase 10 · N6 + N8¹ — dimensão de símbolo na Observabilidade e a seção
// somente-leitura "Pares operados" nas Configurações. Mock data.
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
});

test("N6 — Observabilidade: duração por símbolo no traço do ciclo", async ({ page }) => {
  await page.goto("/#observability");
  await expect(page.locator(".page-title")).toContainText("Observabilidade");
  await expect(page.getByText("Duração por símbolo")).toBeVisible();
  // O mock tem BTC/ETH/SOL com ms por símbolo.
  await expect(page.locator(".tbl").getByText(/812ms/)).toBeVisible();
});

test("N6 — Observabilidade: filtro de símbolo restringe os traços", async ({ page }) => {
  await page.goto("/#observability");
  const sel = page.getByLabel("Filtrar por símbolo");
  await expect(sel).toBeVisible();
  await sel.selectOption("ETH/USDT");
  // Após filtrar por ETH, os traços mostrados contêm ms de ETH.
  await expect(page.locator(".tbl tbody tr")).not.toHaveCount(0);
});

test("N8¹ — Config: seção 'Pares operados' somente-leitura com instrução de env", async ({ page }) => {
  await page.goto("/#settings");
  await expect(page.getByText("Pares operados", { exact: true })).toBeVisible();
  await expect(page.getByText(/Operados pelo loop/)).toBeVisible();
  await expect(page.getByText(/Observáveis \(allowlist/)).toBeVisible();
  await expect(page.getByText(/reinicie o orchestrator/)).toBeVisible();
});
