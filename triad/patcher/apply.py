"""Apply patches to extracted Codex Desktop App source."""
from __future__ import annotations

import json
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

from triad.patcher.patches import PATCHES, CSP_ADDITIONS, BOOTSTRAP_INJECTION, StringPatch


def backup_asar(asar_path: Path, backup_dir: Path) -> Path:
    """Backup original app.asar."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / "app.asar.original"
    if not backup_path.exists():
        shutil.copy2(asar_path, backup_path)
    return backup_path


def extract_asar(asar_path: Path, dest: Path) -> None:
    """Extract app.asar to destination directory."""
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npx", "@electron/asar", "extract", str(asar_path), str(dest)],
        check=True,
        capture_output=True,
    )


def apply_string_patch(source_dir: Path, patch: StringPatch) -> bool:
    """Apply one string patch. Returns True if patch was applied."""
    file_path = source_dir / patch.file
    if not file_path.exists():
        print(f"  SKIP: {patch.file} not found")
        return False

    content = file_path.read_text(encoding="utf-8", errors="replace")
    if patch.find not in content:
        print(f"  SKIP: pattern not found in {patch.file}")
        return False

    new_content = content.replace(patch.find, patch.replace)
    file_path.write_text(new_content, encoding="utf-8")
    print(f"  PATCHED: {patch.description}")
    return True


def patch_csp(source_dir: Path) -> bool:
    """Patch Content-Security-Policy in webview/index.html."""
    index_path = source_dir / "webview" / "index.html"
    if not index_path.exists():
        print("  SKIP: webview/index.html not found")
        return False

    content = index_path.read_text(encoding="utf-8")

    # Add localhost to connect-src if CSP meta tag exists
    if "connect-src" in content:
        content = content.replace(
            "connect-src 'self'",
            f"connect-src 'self' {CSP_ADDITIONS}",
        )
        index_path.write_text(content, encoding="utf-8")
        print("  PATCHED: CSP — added localhost to connect-src")
        return True
    else:
        print("  SKIP: No connect-src found in CSP")
        return False


def repack_asar(source_dir: Path, asar_path: Path) -> None:
    """Repack patched source back into app.asar."""
    subprocess.run(
        ["npx", "@electron/asar", "pack", str(source_dir), str(asar_path)],
        check=True,
        capture_output=True,
    )


def patch_info_plist(app_path: Path) -> bool:
    """Remove ElectronAsarIntegrity from Info.plist to allow patched asar."""
    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.exists():
        return False

    content = plist_path.read_text(encoding="utf-8")
    if "ElectronAsarIntegrity" not in content:
        return False

    # Remove the ElectronAsarIntegrity block
    pattern = r'<key>ElectronAsarIntegrity</key>\s*<dict>.*?</dict>'
    new_content = re.sub(pattern, '', content, flags=re.DOTALL)
    plist_path.write_text(new_content, encoding="utf-8")
    print("  PATCHED: Removed ElectronAsarIntegrity from Info.plist")
    return True


def inject_proxy_launcher(source_dir: Path) -> bool:
    """Generate launcher.js with absolute Python path and inject into bootstrap."""
    import sys

    # Find the actual Python that has triad installed
    python_path = sys.executable  # The Python running this build script

    # Generate launcher with hardcoded path
    launcher_code = f'''// Triad Proxy Launcher — auto-generated with absolute Python path
const {{ spawn }} = require("child_process");
let _p = null, _r = 0;
function startTriadProxy() {{
  try {{
    _p = spawn("{python_path}", ["-m", "triad.cli", "proxy", "--port", "9377"], {{
      stdio: ["ignore", "ignore", "ignore"],
      env: {{ ...process.env, PYTHONUNBUFFERED: "1" }},
      detached: false,
    }});
    _p.on("error", function() {{}});
    _p.on("close", function(c) {{
      _p = null;
      if (c !== 0 && c !== null && _r < 3) {{ _r++; setTimeout(startTriadProxy, 2000); }}
    }});
  }} catch(e) {{}}
  const cl = function() {{ try {{ if(_p) _p.kill(); }} catch(e) {{}} }};
  process.on("exit", cl);
  process.on("SIGINT", function() {{ cl(); process.exit(0); }});
  process.on("SIGTERM", function() {{ cl(); process.exit(0); }});
}}
module.exports = {{ startTriadProxy }};
'''

    launcher_dst = source_dir / ".vite" / "build" / "triad-launcher.js"
    launcher_dst.write_text(launcher_code, encoding="utf-8")
    print(f"  Generated launcher with Python: {python_path}")

    # Inject require into bootstrap.js
    bootstrap_path = source_dir / ".vite" / "build" / "bootstrap.js"
    if not bootstrap_path.exists():
        print("  SKIP: bootstrap.js not found")
        return False

    content = bootstrap_path.read_text(encoding="utf-8")
    if "triad-launcher" in content:
        print("  SKIP: launcher already injected")
        return True

    new_content = BOOTSTRAP_INJECTION + "\n" + content
    bootstrap_path.write_text(new_content, encoding="utf-8")
    print("  PATCHED: Proxy auto-start injected into bootstrap.js")
    return True


def inject_orchestrator_widget(source_dir: Path) -> bool:
    """No-op — model selection now happens via native dropdown through proxy /api/models."""
    print("  SKIP: Using native model dropdown (no widget needed)")
    return True


def _inject_orchestrator_widget_DEPRECATED(source_dir: Path) -> bool:
    """DEPRECATED: Was floating widget, now using native dropdown via proxy."""
    index_path = source_dir / "webview" / "index.html"
    if not index_path.exists():
        return False

    content = index_path.read_text(encoding="utf-8")
    if "triad-orchestrator-widget" in content:
        return True

    widget_html = '''
<!-- TRIAD ORCHESTRATOR WIDGET -->
<style>
  #triad-orchestrator-widget {
    position: fixed;
    bottom: 60px;
    right: 16px;
    z-index: 99999;
    display: flex;
    gap: 4px;
    background: var(--bg-secondary, #1e1e1e);
    border: 1px solid var(--border-primary, #333);
    border-radius: 8px;
    padding: 4px 8px;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    transition: opacity 0.2s;
    opacity: 0.7;
  }
  #triad-orchestrator-widget:hover {
    opacity: 1;
  }
  .triad-provider-btn {
    padding: 4px 10px;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-secondary, #999);
    background: transparent;
    transition: all 0.15s;
    font-size: 12px;
    font-weight: 500;
  }
  .triad-provider-btn:hover {
    background: var(--bg-tertiary, #2a2a2a);
    color: var(--text-primary, #fff);
  }
  .triad-provider-btn.active {
    background: var(--accent-primary, #0066ff);
    color: white;
    border-color: var(--accent-primary, #0066ff);
  }
  .triad-mode-label {
    color: var(--text-tertiary, #666);
    padding: 4px 4px;
    font-size: 11px;
    align-self: center;
  }
</style>
<div id="triad-orchestrator-widget">
  <span class="triad-mode-label">Triad</span>
  <button class="triad-provider-btn active" data-provider="claude" onclick="triadSetProvider('claude')">Claude</button>
  <button class="triad-provider-btn" data-provider="codex" onclick="triadSetProvider('codex')">Codex</button>
  <button class="triad-provider-btn" data-provider="gemini" onclick="triadSetProvider('gemini')">Gemini</button>
</div>
<script>
  async function triadSetProvider(provider) {
    try {
      await fetch('http://127.0.0.1:9377/api/orchestrator', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({provider: provider})
      });
      document.querySelectorAll('.triad-provider-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.provider === provider);
      });
    } catch(e) {
      console.error('[triad] Failed to switch provider:', e);
    }
  }
  // Load current provider on startup
  (async function() {
    try {
      const r = await fetch('http://127.0.0.1:9377/api/orchestrator');
      const d = await r.json();
      document.querySelectorAll('.triad-provider-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.provider === d.active);
      });
    } catch(e) {
      // Proxy not ready yet, retry in 2s
      setTimeout(arguments.callee, 2000);
    }
  })();
</script>
<!-- END TRIAD WIDGET -->
'''

    # Insert before closing </body>
    content = content.replace("</body>", widget_html + "\n</body>")
    index_path.write_text(content, encoding="utf-8")
    print("  PATCHED: Orchestrator rotation widget injected")
    return True


def build_standalone_app(
    source_app: Path = Path("/Applications/Codex.app"),
    target_app: Path = Path("/Applications/Triad.app"),
    work_dir: Path = Path.home() / "codex-fork",
) -> bool:
    """Build standalone Triad.app from Codex.app."""
    print("=== Building Triad.app ===\n")

    # Step 1: Copy entire app bundle
    if target_app.exists():
        print(f"Removing existing {target_app}...")
        shutil.rmtree(target_app)

    print(f"1. Copying {source_app} -> {target_app}...")
    shutil.copytree(source_app, target_app, symlinks=True)

    # Step 2: Rename in Info.plist
    print("2. Updating Info.plist...")
    plist_path = target_app / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)

    plist["CFBundleDisplayName"] = "Triad"
    # CFBundleName MUST stay "Codex" — Electron uses it to find helper apps
    # (Codex Helper.app, Codex Helper (GPU).app, etc.)
    plist["CFBundleName"] = "Codex"
    plist["CFBundleIdentifier"] = "com.triad.orchestrator"
    plist["CFBundleExecutable"] = "Codex"

    # Remove integrity check
    if "ElectronAsarIntegrity" in plist:
        del plist["ElectronAsarIntegrity"]

    # Remove Sparkle updater
    plist.pop("SUFeedURL", None)
    plist.pop("SUPublicEDKey", None)

    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

    # Step 3: Extract asar from the COPY
    asar_path = target_app / "Contents" / "Resources" / "app.asar"
    extract_dir = work_dir / "triad-source"

    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    print("3. Extracting asar from copy...")
    extract_asar(asar_path, extract_dir)

    # Step 4: Apply all string patches
    print("\n4. Applying patches...")
    applied = 0
    for patch in PATCHES:
        if apply_string_patch(extract_dir, patch):
            applied += 1

    # Step 5: Patch CSP
    print("\n5. Patching CSP...")
    patch_csp(extract_dir)

    # Step 6: Inject proxy launcher
    print("\n6. Injecting proxy auto-start...")
    inject_proxy_launcher(extract_dir)

    # Step 7: Inject orchestrator rotation widget into webview
    print("\n7. Injecting orchestrator rotation UI...")
    inject_orchestrator_widget(extract_dir)

    # Step 8: Update package.json name
    print("\n8. Updating package.json...")
    pkg_path = extract_dir / "package.json"
    if pkg_path.exists():
        pkg = json.loads(pkg_path.read_text())
        pkg["productName"] = "Triad"
        pkg["name"] = "triad-orchestrator"
        pkg["codexSparkleFeedUrl"] = ""
        pkg["codexSparklePublicKey"] = ""
        pkg_path.write_text(json.dumps(pkg, indent=2))

    # Step 9: Repack asar
    print("\n9. Repacking asar...")
    repack_asar(extract_dir, asar_path)

    # Step 10: Disable Electron asar integrity fuse
    print("\n10. Disabling asar integrity fuse...")
    fuse_result = subprocess.run(
        ["npx", "@electron/fuses", "write", "--app", str(target_app),
         "EnableEmbeddedAsarIntegrityValidation=off"],
        capture_output=True, text=True,
    )
    if fuse_result.returncode == 0:
        print("  PATCHED: Asar integrity validation disabled")
    else:
        print(f"  WARNING: Could not disable fuse: {fuse_result.stderr[:200]}")

    # Step 11: Re-sign
    print("\n11. Signing app...")
    subprocess.run(["xattr", "-cr", str(target_app)], capture_output=True)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(target_app)],
        capture_output=True,
    )

    print(f"\n=== Triad.app built at {target_app} ===")
    print(f"Patches applied: {applied}")
    print(f"\nTo launch: open {target_app}")
    return True


def apply_all_patches(
    app_path: Path = Path("/Applications/Codex.app"),
    work_dir: Path = Path.home() / "codex-fork",
) -> dict[str, int]:
    """Apply all patches to Codex Desktop App."""
    asar_path = app_path / "Contents" / "Resources" / "app.asar"
    source_dir = work_dir / "source"
    backup_dir = work_dir / "backups"

    print("=== Triad Codex Patcher ===\n")

    # Step 1: Backup
    print("1. Backing up original asar...")
    backup_asar(asar_path, backup_dir)

    # Step 2: Extract (if not already extracted)
    if not (source_dir / "package.json").exists():
        print("2. Extracting asar...")
        extract_asar(asar_path, source_dir)
    else:
        print("2. Using existing extraction...")

    # Step 3: Apply string patches
    print("\n3. Applying patches...")
    applied = 0
    skipped = 0
    for patch in PATCHES:
        if apply_string_patch(source_dir, patch):
            applied += 1
        else:
            skipped += 1

    # Step 4: Patch CSP
    print("\n4. Patching CSP...")
    if patch_csp(source_dir):
        applied += 1

    # Step 5: Inject proxy launcher
    print("\n5. Injecting proxy auto-start...")
    if inject_proxy_launcher(source_dir):
        applied += 1

    # Step 6: Patch Info.plist
    print("\n6. Patching Info.plist...")
    if patch_info_plist(app_path):
        applied += 1

    # Step 7: Repack
    print("\n7. Repacking asar...")
    repack_asar(source_dir, asar_path)

    # Step 8: Re-sign (remove quarantine)
    print("\n8. Fixing code signature...")
    subprocess.run(["xattr", "-cr", str(app_path)], capture_output=True)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
        capture_output=True,
    )

    print(f"\n=== Done! {applied} patches applied, {skipped} skipped ===")
    return {"applied": applied, "skipped": skipped}


def restore_original(
    app_path: Path = Path("/Applications/Codex.app"),
    work_dir: Path = Path.home() / "codex-fork",
) -> bool:
    """Restore original app.asar from backup."""
    asar_path = app_path / "Contents" / "Resources" / "app.asar"
    backup_path = work_dir / "backups" / "app.asar.original"

    if not backup_path.exists():
        print("No backup found!")
        return False

    shutil.copy2(backup_path, asar_path)
    print("Restored original app.asar from backup.")
    return True
