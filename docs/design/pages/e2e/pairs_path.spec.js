// Regressão: o símbolo do par vai no PATH como "BTC-USDT" (hífen), não "%2F".
// Alguns reverse proxies decodificam "%2F" em "/", quebrando /operated/{symbol}
// (dois segmentos → 404). Este teste intercepta a requisição REAL do apiClient
// (não depende de backend nem do mock das telas) e afirma a forma proxy-safe.
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
});

test("apiClient: PATCH/DELETE de par usam hífen no path (não %2F)", async ({ page }) => {
  const urls = [];
  await page.route("**/v1/pairs/operated/**", async (route) => {
    urls.push(route.request().url());
    await route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ data: { operados: [], observaveis: [] } }),
    });
  });
  await page.goto("/#desk");
  await page.evaluate(async () => {
    await CT_API.setPairPaused("BTC/USDT", true);
    await CT_API.removeOperatedPair("ETH/USDT");
  });
  expect(urls).toHaveLength(2);
  for (const u of urls) expect(u).not.toContain("%2F");
  expect(urls[0]).toContain("/operated/BTC-USDT");   // PATCH pausa
  expect(urls[1]).toContain("/operated/ETH-USDT");   // DELETE
});
