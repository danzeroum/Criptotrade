// A9 system pages: 404 deep-link, 403 coherent with RBAC, boundary error id.
import { test, expect } from "@playwright/test";

test("unknown deep-link lands on the 404 page, not a blank overview", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#does-not-exist");
  await expect(page.getByRole("heading", { name: "Página não encontrada" })).toBeVisible();
  await page.getByRole("button", { name: "Voltar ao início" }).click();
  await expect(page).toHaveURL(/#overview$/);
  expect(errors).toEqual([]);
});

test("route without permission shows 403 with the required permission", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "visualizador";
  });
  await page.goto("/#users");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.getByText("manage_users")).toBeVisible();
  await expect(page.getByText("(visualizador)")).toBeVisible();
});

test("admin still reaches the users screen directly", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/#users");
  await expect(page.locator(".page-title")).toContainText("Usuários & Permissões");
});

test("a screen exception hits the boundary with an error id and recovers", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    // Test hook: makes the Overview screen throw during render.
    window.MOCK_THROW_SCREEN = "overview";
  });
  await page.goto("/#overview");
  await expect(page.getByText("Erro inesperado nesta tela")).toBeVisible();
  await expect(page.getByText(/erro [a-z0-9]+-[a-z0-9]+/)).toBeVisible();
  // Navigating to another screen recovers (boundary is keyed per screen).
  await page.locator(".nav-item", { hasText: "Mercado" }).click();
  await expect(page.locator(".page-title")).toContainText("Mercado");
});
