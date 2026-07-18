// A3 RBAC in the console: role-driven visibility (visualizador hides actions,
// demo shows them disabled with the discovery tooltip, admin sees everything).
import { test, expect } from "@playwright/test";

test("visualizador sees no approve/reject and no admin nav", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "visualizador";
  });
  await page.goto("/#hitl");
  await expect(page.locator(".page-title")).toContainText("HITL");
  await expect(page.getByRole("button", { name: "Aprovar" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Rejeitar" })).toHaveCount(0);
  await expect(page.getByText("Somente leitura — seu perfil não aprova ordens.").first())
    .toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Usuários & Permissões" }))
    .toHaveCount(0);
});

test("demo mode shows actions disabled with the discovery tooltip", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_AUTH = "demo";
  });
  await page.goto("/#hitl");
  const approve = page.getByRole("button", { name: "Aprovar" }).first();
  await expect(approve).toBeVisible();
  await expect(approve).toBeDisabled();
  await expect(approve).toHaveAttribute("data-tip", /demonstração/);
  // Demo banner is on, admin nav is off.
  await expect(page.locator(".demo-banner")).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Usuários & Permissões" }))
    .toHaveCount(0);
});

test("admin sees the Administração group and the users screen", async ({ page }) => {
  await page.addInitScript(() => { window.USE_MOCK_DATA = true; });
  await page.goto("/");
  await page.locator(".nav-item", { hasText: "Usuários & Permissões" }).click();
  await expect(page).toHaveURL(/#users$/);
  await expect(page.locator(".page-title")).toContainText("Usuários & Permissões");
  await expect(page.locator(".tbl tbody tr")).toHaveCount(3);
  await expect(page.getByText("Matriz de permissões")).toBeVisible();
});

test("operador keeps approve buttons but has no admin nav", async ({ page }) => {
  await page.addInitScript(() => {
    window.USE_MOCK_DATA = true;
    window.MOCK_ROLE = "operador";
  });
  await page.goto("/#hitl");
  await expect(page.getByRole("button", { name: "Aprovar" }).first()).toBeEnabled();
  await expect(page.locator(".nav-item", { hasText: "Usuários & Permissões" }))
    .toHaveCount(0);
});
