// A9 system pages: 404 deep-link, 403 coherent with RBAC, boundary error id.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test("unknown deep-link lands on the 404 page, not a blank overview", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/#does-not-exist");
  await expect(page.getByRole("heading", { name: "Página não encontrada" })).toBeVisible();
  await page.getByRole("button", { name: "Voltar ao início" }).click();
  await expect(page).toHaveURL(/#overview$/);
  expect(errors).toEqual([]);
});

test("route without permission shows 403 with the required permission", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "visualizador" });
  await page.goto("/#users");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.getByText("manage_users")).toBeVisible();
  await expect(page.getByText("(visualizador)")).toBeVisible();
});

test("admin still reaches the users screen directly", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/#users");
  await expect(page.locator(".page-title")).toContainText("Usuários & Permissões");
});

test("a screen exception hits the boundary with an error id and recovers", async ({ page }) => {
  // Seam de teste: __E2E_THROW_SCREEN força uma exceção de RENDER no Overview
  // (fault-injection síncrona — o error-boundary precisa de throw em render, não
  // dá para simular por dados do fixture). Inerte na produção (nunca injetado).
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.addInitScript(() => { window.__E2E_THROW_SCREEN = "overview"; });
  await page.goto("/#overview");
  await expect(page.getByText("Erro inesperado nesta tela")).toBeVisible();
  await expect(page.getByText(/erro [a-z0-9]+-[a-z0-9]+/)).toBeVisible();
  // Navigating to another screen recovers (boundary is keyed per screen).
  await page.locator(".nav-item", { hasText: "Mercado" }).click();
  await expect(page.locator(".page-title")).toContainText("Mercado");
});
