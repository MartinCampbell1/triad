# Codex Fork + Triad Proxy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Patch Codex Desktop App to use Triad Proxy instead of OpenAI API. Full 1:1 UI preserved, backend swapped to Claude/Codex/Gemini via Triad orchestration with orchestrator rotation.

**Architecture:** Patched Codex .asar → Triad Proxy (FastAPI on localhost:9377) → Provider CLIs. Proxy auto-starts as child process of Electron app.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, asar tools, string-replacement patching

---

## Phase 1: Build Triad Proxy

### Task 1: Proxy server skeleton

Create FastAPI server that accepts OpenAI-format requests and returns OpenAI-format responses.

**Files:**
- Create: `triad/proxy/__init__.py`
- Create: `triad/proxy/server.py`
- Create: `triad/proxy/translator.py`
- Create: `triad/proxy/streaming.py`
- Create: `tests/test_proxy.py`

### Task 2: OpenAI ↔ Provider translation

Translate between OpenAI Responses API format and provider CLI output format.

### Task 3: Orchestrator rotation endpoint

API endpoint to switch active orchestrator (Claude/Codex/Gemini) at runtime.

---

## Phase 2: Patch Codex App

### Task 4: Create patcher script

Automated script that extracts .asar, applies all patches, repacks.

### Task 5: Patch API URLs

String-replace `chatgpt.com/backend-api` → `localhost:9377/api`

### Task 6: Disable telemetry + updater

Neutralize Sentry DSN and Sparkle feed URL.

### Task 7: Patch CSP

Allow localhost in Content-Security-Policy.

### Task 8: Auto-start proxy from Electron

Inject proxy launch into bootstrap.js.

---

## Phase 3: Integration

### Task 9: End-to-end test

Launch patched app, verify chat works through proxy.

### Task 10: Orchestrator rotation UI widget

Inject floating mode selector into webview.
