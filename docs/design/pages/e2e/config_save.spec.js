// M1 — Config de Risco não salvava pela UI: o front disparava PATCH a cada onChange
// e sem confirm, e o backend exige confirm=true (400 confirmation_required). Fluxo
// novo: edição acumula num draft; "Salvar" abre a confirmação (before→after); só ao
// confirmar o PATCH é enviado, com confirm:true. O fixture espelha o gate (400 sem
// confirm) — se o front regredir e parar de mandar confirm, este teste quebra.
import { test, expect } from "@playwright/test";
import { installMockApi } from "./fixtures/mockApi.js";

test("Config de Risco: edição acumula, Salvar confirma before→after, PATCH com confirm:true", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  const riskPatches = [];
  page.on("request", (r) => {
    if (r.method() === "PATCH" && r.url().includes("/v1/risk/config")) {
      riskPatches.push(r.postDataJSON());
    }
  });
  await page.goto("/#settings");
  await expect(page.locator(".page-title")).toContainText("Configurações");

  const riskCard = page.locator(".card", { hasText: "Gestão de Risco" });
  const saveBtn = riskCard.getByRole("button", { name: "Salvar risco" });

  // Sem alterações → Salvar desabilitado.
  await expect(saveBtn).toBeDisabled();

  // Editar (toggle do circuit breaker) só acumula no draft — NENHUM PATCH no onChange.
  await riskCard.locator(".toggle").click();
  await expect(saveBtn).toBeEnabled();
  expect(riskPatches).toHaveLength(0);

  // Salvar abre a confirmação com o resumo before→after.
  await saveBtn.click();
  const diff = page.getByTestId("config-confirm-diff");
  await expect(diff).toBeVisible();
  await expect(diff).toContainText("Circuit breaker");

  // Confirmar dispara o PATCH — com confirm:true (senão o fixture responde 400).
  await page.getByRole("button", { name: "Confirmar e salvar" }).click();
  await expect(page.getByTestId("config-confirm-diff")).toHaveCount(0);   // modal fechou
  await expect(page.getByText("Risco salvo")).toBeVisible();              // sucesso (200)

  expect(riskPatches).toHaveLength(1);
  expect(riskPatches[0].confirm).toBe(true);
  expect(riskPatches[0]).toHaveProperty("circuit_breaker_enabled");
});

test("Config de Risco: cancelar a confirmação não envia PATCH", async ({ page }) => {
  await installMockApi(page, { authMode: "user", role: "admin" });
  const riskPatches = [];
  page.on("request", (r) => {
    if (r.method() === "PATCH" && r.url().includes("/v1/risk/config")) riskPatches.push(r.url());
  });
  await page.goto("/#settings");
  const riskCard = page.locator(".card", { hasText: "Gestão de Risco" });
  await riskCard.locator(".toggle").click();
  await riskCard.getByRole("button", { name: "Salvar risco" }).click();
  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByTestId("config-confirm-diff")).toHaveCount(0);
  expect(riskPatches).toHaveLength(0);
});
