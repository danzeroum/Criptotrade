// A4 audit trail: operador+ sees the screen (nav + table), filters narrow the
// list, the detail modal renders the before→after diff, and roles without
// view_audit (or the public demo) land on the 403 page.
import { test, expect } from "@playwright/test";

test("operador reaches the audit screen from the nav and sees the events", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "operador";
  });
  await page.goto("/");
  await page.locator(".nav-item", { hasText: "Trilha de Auditoria" }).click();
  await expect(page).toHaveURL(/#audit$/);
  await expect(page.locator(".page-title")).toContainText("Trilha de Auditoria");
  // 8 mock events, all on one page.
  await expect(page.locator(".card .tbl tbody tr")).toHaveCount(8);
  await expect(page.getByText("8 evento(s)")).toBeVisible();
});

test("action filter narrows the list (same semantics as the backend SQL)", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "operador";
  });
  await page.goto("/#audit");
  await page.getByLabel("Ação").selectOption("config_changed");
  await page.getByRole("button", { name: "Filtrar" }).click();
  await expect(page.locator(".card .tbl tbody tr")).toHaveCount(1);
  await expect(page.getByText("1 evento(s)")).toBeVisible();
  await page.getByRole("button", { name: "Limpar" }).click();
  await expect(page.locator(".card .tbl tbody tr")).toHaveCount(8);
});

test("event detail opens with the before→after diff", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "operador";
  });
  await page.goto("/#audit");
  await page.locator(".card .tbl tbody tr", { hasText: "Config alterada" }).click();
  const modal = page.getByRole("dialog", { name: "Detalhe do evento" });
  await expect(modal).toBeVisible();
  const diff = modal.getByTestId("audit-diff");
  await expect(diff).toContainText("max_daily_loss_pct");
  await expect(diff).toContainText("5");   // antes
  await expect(diff).toContainText("4");   // depois
  await modal.getByRole("button").first().click();
  await expect(modal).toHaveCount(0);
});

test("visualizador gets the 403 page on a direct #audit deep-link", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "visualizador";
  });
  await page.goto("/#audit");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.getByText("view_audit")).toBeVisible();
  // And the nav never offered the item in the first place.
  await expect(page.locator(".nav-item", { hasText: "Trilha de Auditoria" })).toHaveCount(0);
});

test("public demo never sees the audit trail (real e-mails/IPs live there)", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "demo";
  });
  await page.goto("/#audit");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Trilha de Auditoria" })).toHaveCount(0);
});
