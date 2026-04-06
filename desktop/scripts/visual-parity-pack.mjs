#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

function printUsage() {
  process.stdout.write(
    [
      "Usage: pnpm --dir desktop visual:pack [--config path] [--base-url url] [--output-dir dir]",
      "",
      "Captures fixed-viewport desktop shell screenshots from the configured pack manifest.",
    ].join("\n")
  );
}

function readArgValue(flagName) {
  const index = process.argv.indexOf(flagName);
  if (index === -1 || index + 1 >= process.argv.length) {
    return null;
  }
  return process.argv[index + 1];
}

function hasFlag(flagName) {
  return process.argv.includes(flagName);
}

function parseViewport(raw) {
  if (!raw) {
    return null;
  }

  if (typeof raw === "object" && raw) {
    const width = Number(raw.width);
    const height = Number(raw.height);
    if (Number.isFinite(width) && Number.isFinite(height)) {
      return { width: Math.round(width), height: Math.round(height) };
    }
    return null;
  }

  const text = String(raw).trim();
  const match = text.match(/^(\d+)x(\d+)$/);
  if (!match) {
    return null;
  }
  return { width: Number(match[1]), height: Number(match[2]) };
}

function resolveUrl(baseUrl, target) {
  if (target.url) {
    return new URL(target.url, baseUrl).toString();
  }
  return new URL(target.path ?? "/", baseUrl).toString();
}

async function main() {
  if (hasFlag("--help") || hasFlag("-h")) {
    printUsage();
    return;
  }

  const cwd = process.cwd();
  const configPath = path.resolve(cwd, readArgValue("--config") ?? "visual-parity.config.json");
  const rawConfig = await fs.readFile(configPath, "utf8");
  const config = JSON.parse(rawConfig);

  const baseUrl = process.env.VISUAL_PARITY_BASE_URL ?? readArgValue("--base-url") ?? config.baseUrl ?? "http://127.0.0.1:1420";
  const outputDir = path.resolve(
    cwd,
    process.env.VISUAL_PARITY_OUTPUT_DIR ?? readArgValue("--output-dir") ?? config.outputDir ?? "visual-parity"
  );
  const viewport = parseViewport(process.env.VISUAL_PARITY_VIEWPORT ?? readArgValue("--viewport")) ?? parseViewport(config.viewport) ?? {
    width: 1440,
    height: 920,
  };
  const targets = Array.isArray(config.targets) ? config.targets : [];

  if (targets.length === 0) {
    throw new Error(`No screenshot targets were found in ${configPath}`);
  }

  await fs.mkdir(outputDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      viewport,
      deviceScaleFactor: Number(process.env.VISUAL_PARITY_DSF ?? "1"),
      colorScheme: "dark",
    });

    const captures = [];
    for (const target of targets) {
      const page = await context.newPage();
      const url = resolveUrl(baseUrl, target);
      const name = String(target.name ?? "capture");
      const screenshotPath = path.resolve(outputDir, `${name}.png`);

      const html = typeof target.html === "string" ? target.html : typeof target.content === "string" ? target.content : null;
      if (html) {
        await page.setContent(html, { waitUntil: "domcontentloaded" });
      } else {
        await page.goto(url, { waitUntil: "domcontentloaded" });
      }
      if (target.waitForSelector) {
        await page.waitForSelector(String(target.waitForSelector), { state: "visible" });
      }
      const waitMs = Number(target.waitMs ?? 0);
      if (Number.isFinite(waitMs) && waitMs > 0) {
        await page.waitForTimeout(waitMs);
      }

      await page.screenshot({
        path: screenshotPath,
        fullPage: false,
      });

      captures.push({
        name,
        url,
        screenshot: path.relative(cwd, screenshotPath),
      });

      await page.close();
    }

    const manifestPath = path.resolve(outputDir, "manifest.json");
    await fs.writeFile(
      manifestPath,
      JSON.stringify(
        {
          created_at: new Date().toISOString(),
          baseUrl,
          viewport,
          targets: captures,
        },
        null,
        2
      ) + "\n",
      "utf8"
    );

    process.stdout.write(`Captured ${captures.length} screenshot(s) into ${path.relative(cwd, outputDir)}\n`);
    process.stdout.write(`Manifest: ${path.relative(cwd, manifestPath)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
  process.exitCode = 1;
});
