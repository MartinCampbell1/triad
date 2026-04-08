import { expect, test } from "@playwright/test";
import { injectTestBridge } from "./support/testBridge";

test.beforeEach(async ({ page }) => {
  await injectTestBridge(page, "shell");
  await page.goto("/");
  await expect(page.getByPlaceholder("Ask Codex anything, @ to add files, / for commands, # for skills")).toBeVisible();
});

test("streams tool, diff, finding and final message surfaces", async ({ page }) => {
  const composer = page.getByPlaceholder("Ask Codex anything, @ to add files, / for commands, # for skills");
  await composer.fill("Review bridge flow");
  await composer.press("Control+Enter");

  await expect(page.getByText("Reply for: Review bridge flow")).toBeVisible();
  await expect(page.getByText("Persist system events")).toBeVisible();
  await expect(page.getByText("desktop/src/lib/rpc.ts").first()).toBeVisible();
});

test("opens and closes the terminal drawer", async ({ page }) => {
  await expect(page.getByText("Загружен 1 терминал")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("button", { name: "Terminal" })).toBeVisible();
  await page.getByRole("button", { name: "Terminal" }).click();
  await expect(page.getByText("Загружен 1 терминал")).toBeVisible();
});

test("@visual desktop shell screenshot is stable", async ({ page }) => {
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page).toHaveScreenshot("desktop-shell.png", { animations: "disabled" });
});
