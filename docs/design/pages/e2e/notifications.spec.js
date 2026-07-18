// A6 notifications: admin manages channels/rules (secrets masked, test button
// shows the masked destination), quiet-hours copy makes clear nothing leaves
// the console, and non-admins (operador/demo) never reach the screen.
import { test, expect } from "@playwright/test";

test("admin sees channels with masked secrets and the test destination", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/");
  await page.locator(".nav-item", { hasText: "Notificações & Canais" }).click();
  await expect(page).toHaveURL(/#notifications$/);
  await expect(page.locator(".page-title")).toContainText("Notificações & Canais");
  // Masked destination visible; raw secret nowhere in the DOM.
  await expect(page.getByText("chat -100200300 · token •••4821")).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain("AAAbbb");
  // UX nota 2: the test button says where it will send.
  const testBtn = page.getByRole("button", { name: "Testar" }).first();
  await expect(testBtn).toHaveAttribute("data-tip", /Enviar teste para chat -100200300/);
});

test("rules render event × severity → channels", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#notifications");
  const rules = page.locator(".card", { hasText: "Regras de entrega" });
  await expect(rules.getByText("Circuit breaker")).toBeVisible();
  await expect(rules.getByText("≥ critical")).toBeVisible();
  await expect(rules.getByText("→ Ops crítico, E-mail do dono")).toBeVisible();
});

test("quiet-hours copy says nothing disappears from the console", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#notifications");
  const card = page.locator(".card", { hasText: "Silêncio & agrupamento" });
  await expect(card.getByText("Nada some do console")).toBeVisible();
  await expect(card.getByText("high/critical passam sempre")).toBeVisible();
});

test("operador has no nav item and deep-link lands on 403", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "operador";
  });
  await page.goto("/#notifications");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.getByText("edit_settings")).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Notificações & Canais" })).toHaveCount(0);
});

test("public demo never sees the channels screen (secrets live there)", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "demo";
  });
  await page.goto("/#notifications");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Notificações & Canais" })).toHaveCount(0);
});
