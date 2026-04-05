"""Patch definitions for Codex Desktop App."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StringPatch:
    """One string replacement in a file."""
    file: str  # relative path within extracted asar
    find: str
    replace: str
    description: str


# All patches for Codex app
PATCHES: list[StringPatch] = [
    # 1. Redirect main API to Triad Proxy
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find="https://chatgpt.com/backend-api",
        replace="http://127.0.0.1:9377/api",
        description="Redirect ChatGPT backend API to Triad Proxy",
    ),

    # 2. Disable Sentry crash reporting
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="https://6719eaa18601933a26ac21499dcaba2f@o33249.ingest.us.sentry.io/4510999349821440",
        replace="https://disabled@localhost/0",
        description="Disable Sentry crash reporting to OpenAI",
    ),

    # 3. Disable telemetry intake (product-name bundle)
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="https://chat.openai.com/ces/v1/telemetry/intake",
        replace="http://127.0.0.1:9377/api/telemetry/noop",
        description="Disable telemetry in product-name bundle",
    ),

    # 4. Disable telemetry intake (worker bundle)
    StringPatch(
        file=".vite/build/worker.js",
        find="https://chat.openai.com/ces/v1/telemetry/intake",
        replace="http://127.0.0.1:9377/api/telemetry/noop",
        description="Disable telemetry in worker bundle",
    ),

    # 5. Disable Sparkle auto-updater
    StringPatch(
        file="package.json",
        find='"codexSparkleFeedUrl":"https://persistent.oaistatic.com/codex-app-prod/appcast.xml"',
        replace='"codexSparkleFeedUrl":""',
        description="Disable Sparkle auto-updater feed URL",
    ),
]


# CSP patch for index.html — needs special handling (not simple string replace)
CSP_ADDITIONS = "http://127.0.0.1:9377 ws://127.0.0.1:9377"

BOOTSTRAP_INJECTION = '''
// === TRIAD PATCHES ===
// Suppress EPIPE errors — Electron pipes can break when Sentry/telemetry writes to closed streams
process.on("uncaughtException", function(err) {
  if (err && err.code === "EPIPE") return;
  throw err;
});
process.stdout.on("error", function(err) { if (err.code !== "EPIPE") throw err; });
process.stderr.on("error", function(err) { if (err.code !== "EPIPE") throw err; });

// Start Triad Proxy
try {
  var _tl = require("./triad-launcher.js");
  _tl.startTriadProxy();
} catch (e) {}
// === END TRIAD ===
'''
