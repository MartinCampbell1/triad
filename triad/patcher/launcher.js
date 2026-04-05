// Triad Proxy Launcher — injected into Codex bootstrap.js
// Starts Python proxy server as a child process before the app loads

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

function findPython() {
  const candidates = [
    path.join(process.env.HOME || '', '.triad', '.venv', 'bin', 'python3'),
    path.join(process.env.HOME || '', 'triad', '.venv', 'bin', 'python3'),
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return 'python3';
}

let proxyProcess = null;

function startTriadProxy() {
  const python = findPython();
  proxyProcess = spawn(python, ['-m', 'triad.cli', 'proxy', '--port', '9377'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    detached: false,
  });

  proxyProcess.stdout.on('data', (data) => {
    console.log(`[triad-proxy] ${data.toString().trim()}`);
  });

  proxyProcess.stderr.on('data', (data) => {
    console.error(`[triad-proxy] ${data.toString().trim()}`);
  });

  proxyProcess.on('close', (code) => {
    console.log(`[triad-proxy] exited with code ${code}`);
    // Restart if crashed
    if (code !== 0 && code !== null) {
      console.log('[triad-proxy] restarting in 2s...');
      setTimeout(startTriadProxy, 2000);
    }
  });

  // Cleanup on app exit
  process.on('exit', () => {
    if (proxyProcess) proxyProcess.kill();
  });
  process.on('SIGINT', () => {
    if (proxyProcess) proxyProcess.kill();
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    if (proxyProcess) proxyProcess.kill();
    process.exit(0);
  });
}

module.exports = { startTriadProxy };
