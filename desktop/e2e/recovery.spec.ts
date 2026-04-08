import { expect, test } from "@playwright/test";
import { injectTestBridge } from "./support/testBridge";

test("shows bridge recovery and retries into the shell", async ({ page }) => {
  await injectTestBridge(page, "recovery");
  await page.goto("/");

  await expect(page.getByText("Triad cannot talk to the Python bridge")).toBeVisible();
  await page.getByRole("button", { name: "Retry bridge" }).click();
  await expect(page.getByPlaceholder("Ask Codex anything, @ to add files, / for commands, # for skills")).toBeVisible();
});

test("shows project recovery and allows opening a project", async ({ page }) => {
  await injectTestBridge(page, "project-unavailable");
  page.on("dialog", (dialog) => dialog.accept("/tmp/new-project"));
  await page.goto("/");

  await expect(page.getByText("Choose a project before you start a session")).toBeVisible();
  await page.getByRole("button", { name: "Choose project" }).click();
  await expect(page.getByPlaceholder("Ask Codex anything, @ to add files, / for commands, # for skills")).toBeVisible();
});

test("exports diagnostics from the recovery flow", async ({ page }) => {
  await injectTestBridge(page, "recovery");
  await page.goto("/");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export diagnostics" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("triad-diagnostics-");
});

test("@visual recovery screen screenshot is stable", async ({ page }) => {
  await injectTestBridge(page, "recovery");
  await page.goto("/");

  await expect(page).toHaveScreenshot("recovery-screen.png", { animations: "disabled" });
});
