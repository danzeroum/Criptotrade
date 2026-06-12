// Playwright E2E for the React console (P3-5b).
// Serves the *built* dist/ statically and drives it with Chromium. Screens render
// from mock data (window.USE_MOCK_DATA=true, set per-test), so no backend is needed.
import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;
const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "line",
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // Serve the production build (must be built first: `npm run build`).
    command: `python3 -m http.server ${PORT} --bind 127.0.0.1 --directory dist`,
    url: BASE,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
