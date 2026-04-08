from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class BridgeClient:
    def __init__(self) -> None:
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(REPO_ROOT))
        env.setdefault("TRIAD_ALLOW_MEMORY_LEDGER", "1")
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "triad.desktop.bridge"],
            cwd=REPO_ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._request_id = 0
        self.notifications: list[dict] = []

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def request(self, method: str, params: dict | None = None) -> dict:
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("Bridge stdio is unavailable")

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

        while True:
            line = self._proc.stdout.readline()
            if not line:
                stderr = (
                    self._proc.stderr.read() if self._proc.stderr is not None else ""
                )
                raise RuntimeError(
                    f"Bridge exited before replying to {method}: {stderr}"
                )
            message = json.loads(line)
            if "id" in message:
                if message["id"] != self._request_id:
                    continue
                if "error" in message:
                    raise RuntimeError(
                        message["error"].get("message") or f"RPC {method} failed"
                    )
                return message["result"]
            self.notifications.append(message)

    def wait_for_notification(self, method: str, timeout: float = 2.0) -> dict:
        if self._proc.stdout is None:
            raise RuntimeError("Bridge stdout is unavailable")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select(
                [self._proc.stdout], [], [], max(0.0, deadline - time.monotonic())
            )
            if not ready:
                continue
            line = self._proc.stdout.readline()
            if not line:
                break
            message = json.loads(line)
            self.notifications.append(message)
            if message.get("method") == method:
                return message

        raise AssertionError(f"Timed out waiting for notification: {method}")


def main() -> None:
    client = BridgeClient()
    try:
        ping = client.request("ping")
        assert ping["status"] == "ok"

        diagnostics = client.request("diagnostics")
        assert diagnostics["version"]
        assert diagnostics["python_version"]
        assert diagnostics["triad_home"]
        assert diagnostics["db_path"]
        assert {"claude", "codex", "gemini"}.issubset(diagnostics["providers"])

        with tempfile.TemporaryDirectory(prefix="triad-desktop-smoke-") as tmp_dir:
            project_path = Path(tmp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)

            opened = client.request("project.open", {"path": str(project_path)})
            assert opened["path"] == str(project_path.resolve())

            created = client.request(
                "session.create",
                {
                    "project_path": str(project_path),
                    "mode": "critic",
                    "provider": "claude",
                    "title": "Desktop smoke session",
                },
            )
            session_id = created["id"]

            archive_path = Path(tmp_dir) / "import-archive.json"
            archive = {
                "type": "triad_desktop_session_archive",
                "version": 1,
                "exported_at": "2026-04-08T00:00:00Z",
                "session": {
                    "id": "source-session",
                    "source_session_id": "source-session",
                    "title": "Imported smoke session",
                    "task": "Imported smoke session",
                    "mode": "critic",
                    "status": "completed",
                    "provider": "claude",
                    "project_path": str(project_path),
                    "created_at": "2026-04-08T00:00:00Z",
                    "updated_at": "2026-04-08T00:00:00Z",
                },
                "project": {
                    "path": str(project_path),
                    "name": project_path.name,
                    "git_root": str(project_path),
                },
                "events": [
                    {
                        "session_id": "source-session",
                        "seq": 1,
                        "type": "review_finding",
                        "provider": "codex",
                        "role": "critic",
                        "timestamp": "2026-04-08T00:00:00Z",
                        "data": {
                            "severity": "P1",
                            "file": "desktop/src/hooks/useStreamEvents.ts",
                            "title": "Persist system events",
                            "explanation": "Keep recovery banners visible in the transcript.",
                        },
                    },
                    {
                        "session_id": "source-session",
                        "seq": 2,
                        "type": "tool_use",
                        "provider": "claude",
                        "role": "writer",
                        "timestamp": "2026-04-08T00:00:01Z",
                        "data": {
                            "tool": "Edit",
                            "status": "running",
                            "input": {
                                "file_path": "desktop/src/lib/rpc.ts",
                                "old_string": "legacy mock bridge",
                                "new_string": "fail-closed bridge",
                            },
                        },
                    },
                    {
                        "session_id": "source-session",
                        "seq": 3,
                        "type": "message_finalized",
                        "provider": "claude",
                        "role": "assistant",
                        "timestamp": "2026-04-08T00:00:02Z",
                        "data": {
                            "content": "Smoke run reply",
                        },
                    },
                ],
            }
            archive_path.write_text(json.dumps(archive, indent=2), encoding="utf-8")

            imported = client.request("session.import", {"path": str(archive_path)})
            assert any(
                message.get("review_finding", {}).get("title")
                == "Persist system events"
                for message in imported["messages"]
            )
            assert any(
                message.get("diff_snapshot", {}).get("path") == "desktop/src/lib/rpc.ts"
                for message in imported["messages"]
            )

            exported = client.request(
                "session.export",
                {
                    "session_id": session_id,
                    "format": "archive",
                    "path": str(Path(tmp_dir) / "session-export.json"),
                },
            )
            assert exported["format"] == "archive"

            terminal = client.request(
                "terminal.create", {"cwd": str(project_path), "cols": 80, "rows": 24}
            )
            assert terminal["terminal_id"]
            client.wait_for_notification("event.stream")
            client.request("terminal.close", {"terminal_id": terminal["terminal_id"]})

        print("desktop-smoke passed")
    finally:
        client.close()


if __name__ == "__main__":
    main()
