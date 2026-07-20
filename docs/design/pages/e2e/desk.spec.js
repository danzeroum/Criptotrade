// N2 — Mesa Multi-Ativo: the multi-asset hub. The mock operates 5 pairs in
// mixed states (open position, active signal, awaiting), so we assert the grid,
// the summary row, and the row → Mercado drill-down (sets the global pair).
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test.beforeEach(async ({ page }) => {
  // A Mesa chama GET /v1/desk/summary; o fixture serve as 5 linhas ricas (estados
  // mistos, BNB paused) que antes vinham do _mockDesk() removido.
  await installMockApi(page, { authMode: "user", role: "admin" });
});

test("Mesa is the landing and shows every operated pair (aceite 1)", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/#desk$/);
  await expect(page.locator(".page-title")).toContainText("Mesa Multi-Ativo");
  // 5 operated pairs → 5 data rows (excludes the header row).
  await expect(page.locator(".desk-row:not(.desk-head)")).toHaveCount(5);
  for (const sym of ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]) {
    await expect(page.locator(".desk-sym", { hasText: sym })).toBeVisible();
  }
});

test("mixed states render honestly: position, active signal, awaiting", async ({ page }) => {
  await page.goto("/#desk");
  // An open position with a P&L figure...
  await expect(page.locator(".desk-pnl").first()).toBeVisible();
  // ...an active BUY signal with a confidence %...
  await expect(page.getByText(/BUY · \d+%/).first()).toBeVisible();
  // ...and a pair still awaiting its first cycle.
  await expect(page.locator(".desk-muted", { hasText: "aguardando" }).first()).toBeVisible();
});

test("the summary row reports slots, capital and active signals", async ({ page }) => {
  await page.goto("/#desk");
  await expect(page.locator(".desk-summary")).toContainText("Slots de posição");
  await expect(page.locator(".desk-summary")).toContainText("2 / 3");   // slots_used / max
  await expect(page.locator(".desk-summary")).toContainText("Sinais ativos");
});

test("clicking a row opens the Mercado for that pair (aceite 3)", async ({ page }) => {
  await page.goto("/#desk");
  await page.locator(".desk-row:not(.desk-head)", { hasText: "SOL/USDT" }).click();
  await expect(page).toHaveURL(/#market$/);
  await expect(page.locator(".nav-item.active")).toContainText("Mercado");
});

test("sort toggle reorders the grid without a new request", async ({ page }) => {
  await page.goto("/#desk");
  await page.getByRole("button", { name: "Variação" }).click();
  // Highest 24h change (SOL +4.81%) rises to the top row.
  await expect(page.locator(".desk-row:not(.desk-head)").first().locator(".desk-sym"))
    .toContainText("SOL/USDT");
});

test("N9 — a paused pair carries the PAUSADO badge on the Mesa", async ({ page }) => {
  await page.goto("/#desk");
  const bnb = page.locator(".desk-row:not(.desk-head)", { hasText: "BNB/USDT" });
  await expect(bnb).toHaveClass(/paused/);
  await expect(bnb.getByText("PAUSADO")).toBeVisible();
});

test("N9 — resuming from the Mesa clears paused without navigating away", async ({ page }) => {
  await page.goto("/#desk");
  // The toggle stops propagation → clicking it must not open the Mercado.
  await page.getByRole("button", { name: "Retomar BNB/USDT" }).click();
  await expect(page).toHaveURL(/#desk$/);
  await expect(page.locator(".desk-row:not(.desk-head)", { hasText: "BNB/USDT" })
    .getByText("PAUSADO")).toHaveCount(0);
});

// --------------------------------------------------------------- 11c heatmap

test("11c — toggle Lista⇄Heatmap troca a visão e persiste", async ({ page }) => {
  await page.goto("/#desk");
  await expect(page.locator(".desk-grid")).toBeVisible();  // default = lista
  await page.getByRole("button", { name: "Heatmap" }).click();
  await expect(page.locator(".desk-heat-grid")).toBeVisible();
  await expect(page.locator(".heat-cell")).toHaveCount(5);
  // Preferência persistida: recarregar mantém o heatmap.
  await page.reload();
  await expect(page.locator(".desk-heat-grid")).toBeVisible();
});

test("11c — célula do heatmap: regime legível (M8) e clique abre o Mercado", async ({ page }) => {
  await page.goto("/#desk");
  await page.getByRole("button", { name: "Heatmap" }).click();
  const sol = page.locator(".heat-cell", { hasText: "SOL/USDT" });
  await expect(sol).toContainText("Alta forte");  // regime por rótulo, não só cor
  await sol.click();
  await expect(page).toHaveURL(/#market$/);
});

test("11c — heatmap respeita o badge PAUSADO", async ({ page }) => {
  await page.goto("/#desk");
  await page.getByRole("button", { name: "Heatmap" }).click();
  await expect(page.locator(".heat-cell", { hasText: "BNB/USDT" }).getByText("PAUSADO")).toBeVisible();
});

test("11c — hint aparece com muitos pares (pós-filtro) e some ao dispensar", async ({ page }) => {
  // 14 linhas no desk summary → o hint de heatmap dispara (visible.length > 10).
  await installMockApi(page, { authMode: "user", role: "admin", desk: 14 });
  await page.goto("/#desk");
  const hint = page.getByText(/experimente o modo heatmap/);
  await expect(hint).toBeVisible();
  await page.getByRole("button", { name: "Dispensar dica" }).click();
  await expect(hint).toHaveCount(0);
  // Persistido: não reaparece após reload.
  await page.reload();
  await expect(page.getByText(/experimente o modo heatmap/)).toHaveCount(0);
});

// ------------------------------------------------------------- 11c watchlists

test("11c — filtro de grupo filtra a Mesa; grupo vazio mostra o estado vazio", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("ct.groups", JSON.stringify({
      names: ["majors", "vazio"],
      members: { "BTC/USDT": "majors", "ETH/USDT": "majors" },
    }));
  });
  await page.goto("/#desk");
  // Filtrar por "majors" → só BTC e ETH.
  await page.getByRole("button", { name: "majors" }).click();
  await expect(page.locator(".desk-row:not(.desk-head)")).toHaveCount(2);
  // Grupo sem pares → estado vazio + Ver Todos.
  await page.getByRole("button", { name: "vazio" }).click();
  await expect(page.getByText("Nenhum par operado neste grupo")).toBeVisible();
  await page.getByRole("button", { name: "Ver Todos" }).click();
  await expect(page.locator(".desk-row:not(.desk-head)")).toHaveCount(5);
});
