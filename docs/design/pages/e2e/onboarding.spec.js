// A10 onboarding guide: first admin login with a pending status opens the
// checklist (never hijacking deep links), mixed auto/skip/pending states
// render honestly, completing leads to the dashboard, and non-admins never
// see it. Default mock = completed, so every other spec boots unchanged.
import { test, expect } from "@playwright/test";

test("pending status opens the guide on boot (aceite 1)", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ONBOARDING = "pending";
  });
  await page.goto("/");
  await expect(page).toHaveURL(/#onboarding$/);
  await expect(page.locator(".page-title")).toContainText("Guia de configuração");
  // Mixed states: 2 auto-detected, 1 skipped, 2 pending (+ progress 3/5).
  await expect(page.getByText("Detectado automaticamente")).toHaveCount(2);
  await expect(page.getByText("Pulado", { exact: true })).toHaveCount(1);
  await expect(page.getByText("Pendente")).toHaveCount(2);
  await expect(page.getByText("3/5")).toBeVisible();
  // Nota 3: the testnet recommendation lives on step 1's card.
  await expect(page.getByText(/Comece em TESTNET/)).toBeVisible();
  // Review step shows the honest system summary.
  await expect(page.getByTestId("onboarding-summary")).toContainText("Binance testnet");
});

test("completing the remaining steps leads to the dashboard (aceite 2)", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ONBOARDING = "pending";
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Revisei — está tudo certo" }).click();
  await page.getByRole("button", { name: "Pular", exact: true }).click();  // start_dryrun
  await expect(page.getByText("Configuração concluída.")).toBeVisible();
  await page.getByRole("button", { name: "Ir ao dashboard" }).click();
  await expect(page).toHaveURL(/#overview$/);
});

test("default mock (completed) boots straight to the dashboard", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/");
  await expect(page.locator(".nav-item.active")).toContainText("Visão Geral");
});

test("an explicit deep link is never hijacked", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ONBOARDING = "pending";
  });
  await page.goto("/#agents");
  await expect(page.locator(".page-title")).toContainText("Agentes");
});

test("guide is reachable again from the avatar menu (admin)", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/");
  await page.getByTestId("user-menu").click();
  await page.getByRole("menuitem", { name: "Guia de configuração" }).click();
  await expect(page).toHaveURL(/#onboarding$/);
});

test("operador and demo never reach the guide", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "operador";
  });
  await page.goto("/#onboarding");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();

  const demo = await page.context().newPage();
  await demo.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "demo";
  });
  await demo.goto("/#onboarding");
  await expect(demo.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
});
