import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";
import { Builder, By, Capabilities, until } from "selenium-webdriver";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const desktopRoot = path.resolve(__dirname, "..");
const appBinary = path.resolve(desktopRoot, "src-tauri", "target", "debug", process.platform === "win32" ? "triad-desktop.exe" : "triad-desktop");

if (process.platform === "darwin") {
  console.log("tauri WebDriver is not available on macOS; skipping local tauri smoke");
  process.exit(0);
}

const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), "triad-tauri-e2e-"));
const tempHome = path.join(tempRoot, "home");
const projectPath = path.join(tempRoot, "project");
await fs.mkdir(tempHome, { recursive: true });
await fs.mkdir(projectPath, { recursive: true });

const launcherPath = path.join(tempRoot, process.platform === "win32" ? "launch.cmd" : "launch.sh");
const launcherBody = process.platform === "win32"
  ? `@echo off\r\nset HOME=${tempHome}\r\nset USERPROFILE=${tempHome}\r\n"${appBinary}"\r\n`
  : `#!/bin/sh\nexport HOME="${tempHome}"\nexec "${appBinary}"\n`;
await fs.writeFile(launcherPath, launcherBody, "utf-8");
if (process.platform !== "win32") {
  await fs.chmod(launcherPath, 0o755);
}

const buildResult = spawnSync("pnpm", ["tauri", "build", "--debug", "--no-bundle"], {
  cwd: desktopRoot,
  stdio: "inherit",
  shell: true,
});
if (buildResult.status !== 0) {
  process.exit(buildResult.status ?? 1);
}

const tauriDriver = spawn(path.join(os.homedir(), ".cargo", "bin", process.platform === "win32" ? "tauri-driver.exe" : "tauri-driver"), [], {
  stdio: ["ignore", "inherit", "inherit"],
});

let driver;
try {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch("http://127.0.0.1:4444/status");
      if (response.ok) {
        break;
      }
    } catch {
      // wait for tauri-driver to become ready
    }
    await sleep(200);
  }

  const capabilities = new Capabilities();
  capabilities.set("tauri:options", { application: launcherPath });
  capabilities.setBrowserName("wry");
  driver = await new Builder().withCapabilities(capabilities).usingServer("http://127.0.0.1:4444/").build();

  await driver.wait(until.elementLocated(By.xpath("//*[contains(., 'Choose a project before you start a session')]")), 30000);
  const chooseProjectButton = await driver.findElement(By.xpath("//button[contains(., 'Choose project')]"));
  await chooseProjectButton.click();

  await driver.wait(until.alertIsPresent(), 10000);
  const prompt = await driver.switchTo().alert();
  await prompt.sendKeys(projectPath);
  await prompt.accept();

  await driver.wait(until.elementLocated(By.css("textarea[placeholder*='Ask Codex anything']")), 30000);
  console.log("tauri-smoke passed");
} finally {
  if (driver) {
    await driver.quit().catch(() => undefined);
  }
  tauriDriver.kill();
}
