// Triad Proxy Launcher — injected into Codex bootstrap.js
// Starts the Python proxy, logs output, and waits for /health before booting UI.

const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const DEFAULT_PROXY_HOST = process.env.TRIAD_PROXY_HOST?.trim() || "127.0.0.1";
const DEFAULT_PROXY_PORT = Number.parseInt(process.env.TRIAD_PROXY_PORT || "9377", 10) || 9377;
const DEFAULT_HEALTH_TIMEOUT_MS = Number.parseInt(
  process.env.TRIAD_PROXY_HEALTH_TIMEOUT_MS || "15000",
  10,
) || 15000;
const DEFAULT_RESTART_DELAY_MS = Number.parseInt(
  process.env.TRIAD_PROXY_RESTART_DELAY_MS || "2000",
  10,
) || 2000;
const DEFAULT_MAX_RESTARTS = Number.parseInt(
  process.env.TRIAD_PROXY_MAX_RESTARTS || "3",
  10,
) || 3;

let proxyProcess = null;
let proxyReadyPromise = null;
let restartCount = 0;
let shuttingDown = false;
let bootstrapping = false;
let cleanupBound = false;
let logStream = null;

function getHomeDir() {
  return process.env.HOME || "";
}

function getTriadHome() {
  const override = (process.env.TRIAD_HOME || "").trim();
  return override ? path.resolve(override) : path.join(getHomeDir(), ".triad");
}

function getLogPath() {
  const explicit = (process.env.TRIAD_PROXY_LOG_PATH || "").trim();
  if (explicit) return path.resolve(explicit);

  const logDirOverride = (process.env.TRIAD_PROXY_LOG_DIR || "").trim();
  const logDir = logDirOverride ? path.resolve(logDirOverride) : path.join(getTriadHome(), "logs");
  return path.join(logDir, "triad-proxy.log");
}

function ensureLogStream() {
  if (logStream) return logStream;

  try {
    const logPath = getLogPath();
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    logStream = fs.createWriteStream(logPath, { flags: "a" });
    return logStream;
  } catch (err) {
    try {
      process.stderr.write(`[triad-proxy] failed to open log file: ${err.message}\n`);
    } catch (_) {}
    return null;
  }
}

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  const stream = ensureLogStream();
  if (stream) {
    stream.write(line);
    return;
  }
  try {
    process.stderr.write(`[triad-proxy] ${line}`);
  } catch (_) {}
}

function getEnvInt(name, fallback) {
  const parsed = Number.parseInt((process.env[name] || "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function findPython() {
  const home = getHomeDir();
  const candidates = [];
  const envPython = (process.env.TRIAD_PYTHON || process.env.PYTHON || "").trim();
  if (envPython) {
    candidates.push(envPython);
  }
  candidates.push(
    path.join(home, "triad", ".venv", "bin", "python3"),
    path.join(home, ".triad", ".venv", "bin", "python3"),
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "/usr/bin/python3",
  );

  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return candidate;
    } catch (_) {}
  }
  return "python3";
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function readStreamToLog(stream, prefix) {
  if (!stream) return;
  let buffer = "";
  stream.on("data", (chunk) => {
    buffer += chunk.toString("utf8");
    let index = buffer.indexOf("\n");
    while (index !== -1) {
      const line = buffer.slice(0, index).trimEnd();
      buffer = buffer.slice(index + 1);
      if (line) log(`${prefix}${line}`);
      index = buffer.indexOf("\n");
    }
  });
  stream.on("end", () => {
    const tail = buffer.trim();
    if (tail) log(`${prefix}${tail}`);
  });
}

function requestHealth(host, port, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: host,
        port,
        path: "/health",
        method: "GET",
        timeout: timeoutMs,
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode === 200) {
            resolve(body);
            return;
          }
          reject(
            new Error(
              `proxy health returned ${res.statusCode ?? "unknown"}: ${body.slice(0, 200)}`,
            ),
          );
        });
      },
    );

    req.on("timeout", () => {
      req.destroy(new Error(`health request timed out after ${timeoutMs}ms`));
    });
    req.on("error", reject);
    req.end();
  });
}

async function waitForHealth(proc, host, port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;

  while (Date.now() < deadline) {
    if (proc.exitCode !== null || proc.signalCode !== null) {
      throw new Error(
        `proxy exited before readiness (code=${proc.exitCode ?? "null"}, signal=${proc.signalCode ?? "null"})`,
      );
    }

    try {
      await requestHealth(host, port, Math.min(1000, Math.max(100, deadline - Date.now())));
      return;
    } catch (err) {
      lastError = err;
      await delay(250);
    }
  }

  throw new Error(
    `timed out waiting for proxy health on http://${host}:${port}/health${lastError ? ` (${lastError.message})` : ""}`,
  );
}

function stopProxyProcess() {
  if (!proxyProcess) return;
  try {
    proxyProcess.kill("SIGTERM");
  } catch (_) {}
}

function spawnProxyProcess(python, host, port, logPath) {
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    TRIAD_HOME: process.env.TRIAD_HOME || getTriadHome(),
    TRIAD_PROFILES_DIR: process.env.TRIAD_PROFILES_DIR || path.join(getHomeDir(), ".cli-profiles"),
    TRIAD_PROXY_HOST: host,
    TRIAD_PROXY_PORT: String(port),
    TRIAD_PROXY_LOG_PATH: logPath,
    TRIAD_PROXY_HEALTH_TIMEOUT_MS: String(DEFAULT_HEALTH_TIMEOUT_MS),
    TRIAD_PROXY_RESTART_DELAY_MS: String(DEFAULT_RESTART_DELAY_MS),
    TRIAD_PROXY_MAX_RESTARTS: String(DEFAULT_MAX_RESTARTS),
  };

  const child = spawn(python, ["-m", "triad.cli", "proxy", "--port", String(port)], {
    stdio: ["ignore", "pipe", "pipe"],
    env,
    detached: false,
  });

  log(
    `spawned proxy pid=${child.pid ?? "unknown"} python=${python} host=${host} port=${port} log=${logPath}`,
  );

  readStreamToLog(child.stdout, "[proxy stdout] ");
  readStreamToLog(child.stderr, "[proxy stderr] ");

  child.on("error", (err) => {
    log(`proxy spawn error: ${err.message}`);
  });

  child.on("close", (code, signal) => {
    if (proxyProcess === child) {
      proxyProcess = null;
    }
    log(`proxy exited code=${code ?? "null"} signal=${signal ?? "null"}`);

    if (shuttingDown || bootstrapping) {
      return;
    }

    if (code !== 0 && code !== null && restartCount < DEFAULT_MAX_RESTARTS) {
      restartCount += 1;
      log(`restarting proxy in ${DEFAULT_RESTART_DELAY_MS}ms (attempt ${restartCount})`);
      setTimeout(() => {
        void startProxyAttempt();
      }, DEFAULT_RESTART_DELAY_MS);
    }
  });

  return child;
}

async function startProxyAttempt() {
  const python = findPython();
  const host = DEFAULT_PROXY_HOST;
  const port = DEFAULT_PROXY_PORT;
  const logPath = getLogPath();
  const timeoutMs = getEnvInt("TRIAD_PROXY_HEALTH_TIMEOUT_MS", DEFAULT_HEALTH_TIMEOUT_MS);

  const child = spawnProxyProcess(python, host, port, logPath);
  proxyProcess = child;
  await waitForHealth(child, host, port, timeoutMs);
}

async function startTriadProxy() {
  if (proxyReadyPromise) return proxyReadyPromise;

  bootstrapping = true;
  proxyReadyPromise = (async () => {
    let lastError = null;

    try {
      for (let attempt = 0; attempt <= DEFAULT_MAX_RESTARTS; attempt += 1) {
        try {
          await startProxyAttempt();
          log(`proxy ready on http://${DEFAULT_PROXY_HOST}:${DEFAULT_PROXY_PORT}/health`);
          return {
            host: DEFAULT_PROXY_HOST,
            port: DEFAULT_PROXY_PORT,
            logPath: getLogPath(),
          };
        } catch (err) {
          lastError = err;
          log(`proxy startup attempt ${attempt + 1} failed: ${err.message}`);
          stopProxyProcess();
          proxyProcess = null;

          if (attempt >= DEFAULT_MAX_RESTARTS) {
            break;
          }

          await delay(DEFAULT_RESTART_DELAY_MS);
        }
      }

      throw lastError || new Error("proxy failed to start");
    } finally {
      bootstrapping = false;
    }
  })().catch((err) => {
    proxyReadyPromise = null;
    throw err;
  });

  installCleanupHandlers();
  return proxyReadyPromise;
}

function installCleanupHandlers() {
  if (cleanupBound) return;
  cleanupBound = true;

  const cleanup = () => {
    shuttingDown = true;
    stopProxyProcess();
    try {
      if (logStream) logStream.end();
    } catch (_) {}
  };

  process.on("exit", cleanup);
  process.on("SIGINT", () => {
    cleanup();
    process.exit(0);
  });
  process.on("SIGTERM", () => {
    cleanup();
    process.exit(0);
  });
}

module.exports = { startTriadProxy };
