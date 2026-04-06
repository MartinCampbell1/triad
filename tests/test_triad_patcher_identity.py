from __future__ import annotations

import json
import plistlib
import re
import subprocess
from pathlib import Path

import pytest

import triad.patcher.apply as patcher_apply


def _write_plist(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(data, handle)


def _make_fake_codex_bundle(root: Path) -> Path:
    source_app = root / "Codex.app"
    contents = source_app / "Contents"
    resources = contents / "Resources"
    frameworks = contents / "Frameworks"
    macos = contents / "MacOS"

    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    frameworks.mkdir(parents=True)

    (resources / "app.asar").write_text("fake asar")
    (macos / "Codex").write_text("fake executable")

    main_plist = {
        "CFBundleDisplayName": "Codex",
        "CFBundleName": "Codex",
        "CFBundleExecutable": "Codex",
        "CFBundleIdentifier": "com.openai.codex",
        "CFBundleURLTypes": [
            {
                "CFBundleURLName": "Codex",
                "CFBundleURLSchemes": ["codex"],
            }
        ],
        "NSBluetoothPeripheralUsageDescription": "This app needs access to Bluetooth",
        "NSCameraUsageDescription": "This app needs access to the camera",
        "NSMicrophoneUsageDescription": "Codex needs access to your microphone for voice input.",
    }
    _write_plist(contents / "Info.plist", main_plist)

    helper_names = [
        "Codex Helper.app",
        "Codex Helper (GPU).app",
        "Codex Helper (Plugin).app",
        "Codex Helper (Renderer).app",
    ]
    for helper_name in helper_names:
        helper_root = frameworks / helper_name / "Contents"
        helper_exec = helper_name.removesuffix(".app")
        _write_plist(
            helper_root / "Info.plist",
            {
                "CFBundleDisplayName": helper_exec,
                "CFBundleName": "Codex" if helper_name == "Codex Helper.app" else helper_exec,
                "CFBundleExecutable": helper_exec,
                "CFBundleIdentifier": "com.openai.codex.helper",
            },
        )
        helper_macos = helper_root / "MacOS"
        helper_macos.mkdir(parents=True, exist_ok=True)
        (helper_macos / helper_exec).write_text("fake helper")

    return source_app


def test_build_standalone_app_renames_main_bundle_identity(tmp_path: Path, monkeypatch):
    source_app = _make_fake_codex_bundle(tmp_path / "source")
    target_app = tmp_path / "Triad.app"
    work_dir = tmp_path / "work"

    monkeypatch.setattr(patcher_apply, "extract_asar", lambda *args, **kwargs: None)
    monkeypatch.setattr(patcher_apply, "repack_asar", lambda *args, **kwargs: None)
    monkeypatch.setattr(patcher_apply, "inject_proxy_launcher", lambda *args, **kwargs: True)
    monkeypatch.setattr(patcher_apply.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0))

    assert patcher_apply.build_standalone_app(
        source_app=source_app,
        target_app=target_app,
        work_dir=work_dir,
    )

    plist = plistlib.loads((target_app / "Contents" / "Info.plist").read_bytes())
    assert plist["CFBundleDisplayName"] == "Triad"
    assert plist["CFBundleName"] == "Triad"
    assert plist["CFBundleExecutable"] == "Triad"
    assert plist["CFBundleIdentifier"] == "com.triad.orchestrator"
    assert plist["CFBundleURLTypes"][0]["CFBundleURLName"] == "Triad"
    assert plist["CFBundleURLTypes"][0]["CFBundleURLSchemes"] == ["triad"]
    assert (target_app / "Contents" / "MacOS" / "Triad").exists()
    assert not (target_app / "Contents" / "MacOS" / "Codex").exists()


def test_build_standalone_app_renames_helper_bundles(tmp_path: Path, monkeypatch):
    source_app = _make_fake_codex_bundle(tmp_path / "source")
    target_app = tmp_path / "Triad.app"
    work_dir = tmp_path / "work"

    monkeypatch.setattr(patcher_apply, "extract_asar", lambda *args, **kwargs: None)
    monkeypatch.setattr(patcher_apply, "repack_asar", lambda *args, **kwargs: None)
    monkeypatch.setattr(patcher_apply, "inject_proxy_launcher", lambda *args, **kwargs: True)
    monkeypatch.setattr(patcher_apply.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0))

    patcher_apply.build_standalone_app(
        source_app=source_app,
        target_app=target_app,
        work_dir=work_dir,
    )

    for spec in patcher_apply.HELPER_RENAMES:
        helper_name = spec["dst_app"]
        helper_plist_path = target_app / "Contents" / "Frameworks" / helper_name / "Contents" / "Info.plist"
        helper_plist = plistlib.loads(helper_plist_path.read_bytes())
        assert helper_plist["CFBundleDisplayName"] == spec["display_name"]
        assert helper_plist["CFBundleName"] == spec["bundle_name"]
        assert helper_plist["CFBundleExecutable"] == spec["dst_exec"]
        assert helper_plist["CFBundleIdentifier"] == "com.triad.orchestrator.helper"
        assert (helper_plist_path.parent / "MacOS" / spec["dst_exec"]).exists()
        assert not (helper_plist_path.parent / "MacOS" / spec["src_exec"]).exists()


def test_build_standalone_app_rewrites_package_metadata(tmp_path: Path, monkeypatch):
    source_app = _make_fake_codex_bundle(tmp_path / "source")
    target_app = tmp_path / "Triad.app"
    work_dir = tmp_path / "work"

    def fake_extract_asar(_asar_path: Path, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "package.json").write_text(
            json.dumps(
                {
                    "productName": "Codex",
                    "name": "codex",
                    "author": "OpenAI",
                    "description": "Codex",
                    "codexBuildFlavor": "prod",
                    "codexBuildNumber": "1272",
                    "codexSparkleFeedUrl": "https://example.invalid/feed",
                    "codexSparklePublicKey": "pubkey",
                }
            )
        )

    monkeypatch.setattr(patcher_apply, "extract_asar", fake_extract_asar)
    monkeypatch.setattr(patcher_apply, "repack_asar", lambda *args, **kwargs: None)
    monkeypatch.setattr(patcher_apply, "inject_proxy_launcher", lambda *args, **kwargs: True)
    monkeypatch.setattr(patcher_apply.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0))

    patcher_apply.build_standalone_app(
        source_app=source_app,
        target_app=target_app,
        work_dir=work_dir,
    )

    pkg = json.loads((work_dir / "triad-source" / "package.json").read_text())
    assert pkg["productName"] == "Triad"
    assert pkg["name"] == "triad-orchestrator"
    assert pkg["author"] == "Triad"
    assert pkg["description"] == "Triad"
    assert pkg["codexBuildFlavor"] == "prod"
    assert pkg["codexBuildNumber"] == "0"
    assert pkg["codexSparkleFeedUrl"] == ""
    assert pkg["codexSparklePublicKey"] == ""


@pytest.mark.xfail(reason="Desktop-safe storage namespace is still inferred from Codex identity")
def test_launcher_sets_desktop_codex_home_from_triad_home():
    launcher_source = Path("/Users/martin/triad/triad/patcher/launcher.js").read_text()
    assert "CODEX_HOME" in launcher_source
    assert "TRIAD_HOME" in launcher_source
    assert ".triad" in launcher_source


def test_paths_exist_handler_treats_permission_denied_as_non_fatal():
    bundle_source = Path("/Users/martin/codex-fork/triad-source/.vite/build/main-8X_hBwW2.js").read_text(
        errors="ignore"
    )
    idx = bundle_source.find('"paths-exist"')
    assert idx != -1

    snippet = bundle_source[max(0, idx - 250) : idx + 1200]
    assert re.search(r'"paths-exist":async\(\{paths:t\}\)=>\{try\{return\{existingPaths:', snippet)
    assert "catch(n){return{existingPaths:[]}}" in snippet
