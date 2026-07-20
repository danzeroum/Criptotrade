// Fase 10 · N6 + N8¹ — dimensão de símbolo na Observabilidade e a seção
// "Pares operados" nas Configurações. Dados servidos pelo fixture page.route
// (Obs + Config de-mockadas na 5.3). O último teste (seletor no Mercado) segue
// no caminho USE_MOCK_DATA até o Mercado ser de-mockado na 5.3b.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test.beforeEach(async ({ page }) => {
  await installMockApi(page, { authMode: "user" });
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

test("N8¹/N8² — Config: seção 'Pares operados' (operados + observáveis + semântica)", async ({ page }) => {
  await page.goto("/#settings");
  await expect(page.getByText("Pares operados", { exact: true })).toBeVisible();
  await expect(page.getByText(/Operados pelo loop/)).toBeVisible();
  await expect(page.getByText(/Observáveis \(allowlist/)).toBeVisible();
  await expect(page.getByText(/próximo restart/)).toBeVisible();
});

test("N8² — Config: adicionar um par mostra o banner 'pendente de restart'", async ({ page }) => {
  await page.goto("/#settings");
  // Escolhe um par observável ainda não operado e adiciona.
  await page.getByLabel("Adicionar par").selectOption("ADA/USDT");
  await page.getByRole("button", { name: "Adicionar" }).click();
  await expect(page.getByText(/Alterações pendentes/)).toBeVisible();
  await expect(page.locator(".pair-tag", { hasText: "ADA/USDT" })).toBeVisible();
});

test("N9 — Config: par pausado mostra o badge PAUSADO (sem banner de restart)", async ({ page }) => {
  await page.goto("/#settings");
  const bnb = page.locator(".pair-tag", { hasText: "BNB/USDT" });
  await expect(bnb.getByText("PAUSADO")).toBeVisible();
  // Pausar é por-ciclo — nunca dispara o banner de restart.
  await expect(page.getByText(/Alterações pendentes/)).toHaveCount(0);
});

test("N9 — Config: pausar um par aplica sem restart (sem banner)", async ({ page }) => {
  await page.goto("/#settings");
  await page.getByRole("button", { name: "Pausar BTC/USDT" }).click();
  await expect(page.locator(".pair-tag", { hasText: "BTC/USDT" }).getByText("PAUSADO")).toBeVisible();
  await expect(page.getByText(/Alterações pendentes/)).toHaveCount(0);
});

// ------------------------------------------------------------- 11c watchlists

test("11c — Config: criar grupo, atribuir par e excluir devolve a 'sem grupo'", async ({ page }) => {
  await page.goto("/#settings");
  // Criar grupo "majors".
  await page.getByRole("button", { name: "+ Novo grupo" }).click();
  await page.getByLabel("Nome do novo grupo").fill("majors");
  await page.getByLabel("Nome do novo grupo").press("Enter");
  await expect(page.locator(".group-chip", { hasText: "majors" })).toBeVisible();
  // Atribuir BTC/USDT ao grupo.
  await page.getByLabel("Grupo de BTC/USDT").selectOption("majors");
  await expect(page.getByLabel("Grupo de BTC/USDT")).toHaveValue("majors");
  // Um segundo grupo mantém o bloco de atribuição visível após excluir "majors".
  await page.getByRole("button", { name: "+ Novo grupo" }).click();
  await page.getByLabel("Nome do novo grupo").fill("alts");
  await page.getByLabel("Nome do novo grupo").press("Enter");
  // Excluir "majors" → BTC volta a "sem grupo" (nunca exclui o par).
  await page.getByRole("button", { name: "Excluir grupo majors" }).click();
  await expect(page.locator(".group-chip", { hasText: "majors" })).toHaveCount(0);
  await expect(page.getByLabel("Grupo de BTC/USDT")).toHaveValue("");
  await expect(page.locator(".pair-tag", { hasText: "BTC/USDT" })).toBeVisible();
});

test("11c — seletor agrupa os operados pela watchlist", async ({ page }) => {
  // Mercado ainda não de-mockado (5.3b) — este teste segue no caminho mock até lá;
  // o fixture do beforeEach fica dormente (o mock não dispara fetch de /api).
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    localStorage.setItem("ct.groups", JSON.stringify({
      names: ["majors"], members: { "BTC/USDT": "majors" },
    }));
  });
  await page.goto("/#market");
  await page.getByRole("button", { name: "Par" }).click();
  // Cabeçalho do grupo + o "sem grupo" para os demais operados.
  await expect(page.locator(".pair-group", { hasText: "majors" })).toBeVisible();
  await expect(page.locator(".pair-group", { hasText: "sem grupo" })).toBeVisible();
});
