// A5 connections & keys: admin manages exchange connections (masked key,
// detected permissions, trade scope blocked until the typed confirmation) and
// platform keys (full key shown exactly once); non-admins land on the 403.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test("admin sees connections with masked keys and detected permissions", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/");
  await page.locator(".nav-item", { hasText: "Conexões & Chaves" }).click();
  await expect(page).toHaveURL(/#connections$/);
  await expect(page.locator(".page-title")).toContainText("Conexões & Chaves");
  await expect(page.getByText("key •••b3f1")).toBeVisible();
  await expect(page.getByText("leitura ok")).toBeVisible();
  await expect(page.getByText("trade ok")).toBeVisible();
  // The failing connection shows the real (redacted) reason.
  await expect(page.getByText(/Invalid API-key/)).toBeVisible();
  // Egress-IP guidance for locking the key at the exchange.
  await expect(page.getByText("203.0.113.42")).toBeVisible();
});

test("trade scope demands the typed TRADE confirmation before submitting", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/#connections");
  await page.getByRole("button", { name: "Conectar exchange" }).click();
  const modal = page.getByRole("dialog", { name: "Nova conexão" });
  await modal.getByText("Trade", { exact: true }).click();
  await expect(modal.getByTestId("trade-warning")).toBeVisible();
  await expect(modal.getByText(/ordens\s+reais com o seu dinheiro/)).toBeVisible();
  const submit = modal.getByRole("button", { name: "Conectar" });
  await expect(submit).toBeDisabled();
  await modal.getByLabel("Digite TRADE para confirmar").fill("trade");
  await expect(submit).toBeDisabled();  // case-sensitive, like the backend
  await modal.getByLabel("Digite TRADE para confirmar").fill("TRADE");
  await expect(submit).toBeEnabled();
});

test("platform key is shown exactly once on creation", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  await page.goto("/#connections");
  await page.getByRole("button", { name: "Criar chave" }).click();
  await page.getByPlaceholder("ex.: grafana-readonly").fill("bot-webhooks");
  await page.getByRole("button", { name: "Criar", exact: true }).click();
  const modal = page.getByRole("dialog", { name: "Chave criada" });
  await expect(modal.getByTestId("platform-key-value")).toContainText("ctk_");
  await expect(modal.getByText("não será exibida novamente")).toBeVisible();
  await modal.getByRole("button", { name: "Copiei a chave" }).click();
  await expect(modal).toHaveCount(0);
  // The table shows only the display prefix.
  await expect(page.getByText("ctk_a1b2c3d4…")).toBeVisible();
});

test("operador lands on the 403 with manage_keys", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "operador" });
  await page.goto("/#connections");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.getByText("manage_keys")).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Conexões & Chaves" })).toHaveCount(0);
});

test("public demo never sees the connections screen", async ({ page }) => {
  await installMockApi(page, { authMode: "demo" });
  await page.goto("/#connections");
  await expect(page.getByRole("heading", { name: "Sem permissão" })).toBeVisible();
  await expect(page.locator(".nav-item", { hasText: "Conexões & Chaves" })).toHaveCount(0);
});
