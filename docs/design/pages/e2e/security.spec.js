// A7 security & sessions: any authenticated user sees the self-service screen
// (sessions with the current one marked, 2FA card, own login history); the
// public demo has no session to manage and lands on the 403 page.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test("authenticated user reaches Segurança & Sessões from the nav", async ({ page }) => {
  // self-service: role does not matter
  await installMockApi(page, { authMode: "user", role: "visualizador" });
  await page.goto("/");
  await page.locator(".nav-item", { hasText: "Segurança & Sessões" }).click();
  await expect(page).toHaveURL(/#security$/);
  await expect(page.locator(".page-title")).toContainText("Segurança & Sessões");
  // Two mock sessions, the current one badged.
  await expect(page.getByText("Sessões ativas")).toBeVisible();
  await expect(page.locator(".tbl").first().locator("tbody tr")).toHaveCount(2);
  await expect(page.getByText("Atual")).toBeVisible();
  // UA heuristic renders friendly device names, not raw strings.
  await expect(page.getByText("Chrome · Linux").first()).toBeVisible();
  await expect(page.getByText("Safari · iOS").first()).toBeVisible();
});

test("login history shows own e-mail attempts with success and failure", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/#security");
  const history = page.locator(".card", { hasText: "Histórico de logins" });
  await expect(history.getByText("somente o seu e-mail")).toBeVisible();
  await expect(history.locator("tbody tr")).toHaveCount(3);
  await expect(history.getByText("falha")).toBeVisible();
});

test("2FA card offers enabling when disabled", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/#security");
  const card = page.locator(".card", { hasText: "Verificação em duas etapas" });
  await expect(card.getByText("Inativa")).toBeVisible();
  await expect(card.getByRole("button", { name: "Ativar 2FA" })).toBeVisible();
});

test("public demo has no session to manage: nav hidden, deep-link 403", async ({ page }) => {
  await installMockApi(page, { authMode: "demo" });
  await page.goto("/#security");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Segurança & Sessões" })).toHaveCount(0);
});
