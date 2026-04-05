// Triad Proxy Launcher — injected into Codex bootstrap.js
// Starts Python proxy server as a child process before the app loads

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

function findPython() {
  const home = process.env.HOME || '';
  const candidates = [
    path.join(home, 'triad', '.venv', 'bin', 'python3'),
    path.join(home, '.triad', '.venv', 'bin', 'python3'),
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
  ];
  for (const p of candidates) {
    try { if (fs.existsSync(p)) return p; } catch(e) {}
  }
  return 'python3';
}

let proxyProcess = null;
let restartCount = 0;
const MAX_RESTARTS = 3;

function startTriadProxy() {
  const python = findPython();

  try {
    proxyProcess = spawn(python, ['-m', 'triad.cli', 'proxy', '--port', '9377'], {
      stdio: ['ignore', 'ignore', 'ignore'],  // Detach all stdio to avoid EPIPE
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      detached: false,
    });

    proxyProcess.on('error', (err) => {
      // Python not found or spawn failed — silently ignore
    });

    proxyProcess.on('close', (code) => {
      proxyProcess = null;
      if (code !== 0 && code !== null && restartCount < MAX_RESTARTS) {
        restartCount++;
        setTimeout(startTriadProxy, 2000);
      }
    });
  } catch (e) {
    // Spawn failed entirely — app still works, just without proxy
  }

  // Cleanup on app exit
  const cleanup = () => {
    try { if (proxyProcess) proxyProcess.kill(); } catch(e) {}
  };
  process.on('exit', cleanup);
  process.on('SIGINT', () => { cleanup(); process.exit(0); });
  process.on('SIGTERM', () => { cleanup(); process.exit(0); });
}

module.exports = { startTriadProxy };
