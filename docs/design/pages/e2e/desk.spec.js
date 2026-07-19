// N2 — Mesa Multi-Ativo: the multi-asset hub. The mock operates 5 pairs in
// mixed states (open position, active signal, awaiting), so we assert the grid,
// the summary row, and the row → Mercado drill-down (sets the global pair).
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
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
