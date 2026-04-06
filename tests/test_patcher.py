from pathlib import Path
from triad.patcher.patches import PATCHES, StringPatch
from triad.patcher.apply import (
    apply_string_patch,
    inject_orchestrator_widget,
    inject_proxy_launcher,
    patch_csp,
)


def test_patches_have_required_fields():
    for patch in PATCHES:
        assert patch.file
        assert patch.find
        assert patch.replace
        assert patch.description


def test_patch_count():
    assert len(PATCHES) >= 6


def test_patch_set_includes_triad_identity_and_onboarding_redirects():
    descriptors = {(patch.file, patch.description) for patch in PATCHES}
    assert (
        ".vite/build/product-name-CswjKXkf.js",
        "Rename desktop product name to Triad",
    ) in descriptors
    assert (
        "webview/assets/index--dL9tGqL.js",
        "Start desktop directly in the main app shell without onboarding workspace mode",
    ) in descriptors
    assert (
        "webview/assets/index--dL9tGqL.js",
        "Keep the desktop window in full app mode during Triad startup",
    ) in descriptors
    assert (
        "webview/assets/index--dL9tGqL.js",
        "Always query workspace root options in desktop wrapper",
    ) in descriptors
    assert (
        "webview/assets/index--dL9tGqL.js",
        "Avoid blank renderer by redirecting pending auth fallback to root",
    ) in descriptors
    assert (
        "webview/assets/index--dL9tGqL.js",
        "Disable plugin feature sync that still triggers Codex plugin auth paths",
    ) in descriptors
    assert (
        "webview/assets/index--dL9tGqL.js",
        "Disable Codex new-model announcement modal inside Triad",
    ) in descriptors


def test_apply_string_patch_replaces(tmp_path: Path):
    test_file = tmp_path / "test.js"
    test_file.write_text('var url = "https://chatgpt.com/backend-api";')

    patch = StringPatch(
        file="test.js",
        find="https://chatgpt.com/backend-api",
        replace="http://127.0.0.1:9377/api",
        description="test",
    )

    result = apply_string_patch(tmp_path, patch)
    assert result is True
    assert "127.0.0.1:9377" in test_file.read_text()
    assert "chatgpt.com" not in test_file.read_text()


def test_apply_string_patch_missing_file(tmp_path: Path):
    patch = StringPatch(file="missing.js", find="x", replace="y", description="test")
    result = apply_string_patch(tmp_path, patch)
    assert result is False


def test_apply_string_patch_pattern_not_found(tmp_path: Path):
    test_file = tmp_path / "test.js"
    test_file.write_text("var x = 1;")

    patch = StringPatch(file="test.js", find="not_here", replace="y", description="test")
    result = apply_string_patch(tmp_path, patch)
    assert result is False


def test_inject_proxy_launcher(tmp_path: Path):
    build_dir = tmp_path / ".vite" / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "bootstrap.js").write_text(
        "n.app.whenReady().then(async()=>{let{desktopSentry:r,sparkleManager:i}=t;await i.initialize();try{let{runMainAppStartup:e}=await Promise.resolve().then(()=>require(`./main-8X_hBwW2.js`));await e()}})"
    )
    result = inject_proxy_launcher(tmp_path)
    assert result is True

    bootstrap = (build_dir / "bootstrap.js").read_text()
    launcher = (build_dir / "triad-launcher.js").read_text()
    assert "triad-launcher" in bootstrap
    assert "globalThis.__triadProxyReady" in bootstrap
    assert "await globalThis.__triadProxyReady()" in bootstrap
    assert "TRIAD_PROXY_HEALTH_TIMEOUT_MS" in launcher
    assert "waitForHealth" in launcher
    assert "spawned proxy" in launcher


def test_patch_csp_handles_html_escaped_self(tmp_path: Path):
    webview_dir = tmp_path / "webview"
    webview_dir.mkdir()
    index = webview_dir / "index.html"
    index.write_text(
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; connect-src &#39;self&#39; https://ab.chatgpt.com https://cdn.openai.com;">',
        encoding="utf-8",
    )

    assert patch_csp(tmp_path) is True
    updated = index.read_text(encoding="utf-8")
    assert "http://127.0.0.1:9377" in updated
    assert "ws://127.0.0.1:9377" in updated


def test_inject_orchestrator_widget(tmp_path: Path):
    webview_dir = tmp_path / "webview"
    webview_dir.mkdir()
    index = webview_dir / "index.html"
    original = "<html><body><div id='root'></div></body></html>"
    index.write_text(original)

    result = inject_orchestrator_widget(tmp_path)
    assert result is True

    assert index.read_text() == original


def test_inject_orchestrator_widget_idempotent(tmp_path: Path):
    webview_dir = tmp_path / "webview"
    webview_dir.mkdir()
    index = webview_dir / "index.html"
    index.write_text("<html><body><div id='root'></div></body></html>")

    inject_orchestrator_widget(tmp_path)
    first_content = index.read_text()

    inject_orchestrator_widget(tmp_path)
    second_content = index.read_text()

    assert first_content == second_content  # No double injection
