"""Apply patches to extracted Codex Desktop App source."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from triad.patcher.patches import PATCHES, CSP_ADDITIONS, StringPatch


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

    # Step 5: Patch Info.plist
    print("\n5. Patching Info.plist...")
    if patch_info_plist(app_path):
        applied += 1

    # Step 6: Repack
    print("\n6. Repacking asar...")
    repack_asar(source_dir, asar_path)

    # Step 7: Re-sign (remove quarantine)
    print("\n7. Fixing code signature...")
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
