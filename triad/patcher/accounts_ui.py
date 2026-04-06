"""Desktop Accounts UI injection for the Triad webview bundle."""
from __future__ import annotations

import shutil
from pathlib import Path

from triad.patcher.patches import (
    TRIAD_ACCOUNTS_ROUTE,
    TRIAD_ACCOUNTS_SCRIPT,
    TRIAD_ACCOUNTS_STYLESHEET,
)


_ASSET_DIR = Path(__file__).with_name("assets")


def _copy_asset(source_name: str, dest_path: Path) -> None:
    src_path = _ASSET_DIR / source_name
    if not src_path.exists():
        raise FileNotFoundError(f"missing patcher asset: {src_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest_path)


def _inject_html_tag(content: str, tag: str, marker: str) -> str:
    if tag in content:
        return content
    if marker not in content:
        return content
    return content.replace(marker, f"{tag}\n{marker}")


def _inject_bundle_string(content: str, find: str, replace: str) -> tuple[str, bool]:
    if replace in content:
        return content, False
    if find not in content:
        return content, False
    return content.replace(find, replace), True


def _find_webview_bundle(webview_dir: Path) -> Path | None:
    assets_dir = webview_dir / "assets"
    candidates = sorted(assets_dir.glob("index-*.js"))
    return candidates[0] if candidates else None


def inject_accounts_ui(source_dir: Path) -> bool:
    """Inject the Triad accounts sidebar entry and accounts page into the webview."""
    webview_dir = source_dir / "webview"
    index_path = webview_dir / "index.html"
    bundle_path = _find_webview_bundle(webview_dir)
    css_path = webview_dir / "assets" / TRIAD_ACCOUNTS_STYLESHEET
    js_path = webview_dir / "assets" / TRIAD_ACCOUNTS_SCRIPT

    if not index_path.exists():
        print("  SKIP: webview/index.html not found")
        return False
    if bundle_path is None or not bundle_path.exists():
        print("  SKIP: webview bundle not found")
        return False

    _copy_asset(TRIAD_ACCOUNTS_STYLESHEET, css_path)
    _copy_asset(TRIAD_ACCOUNTS_SCRIPT, js_path)

    index_content = index_path.read_text(encoding="utf-8")
    changed = False

    css_tag = (
        f'<link rel="stylesheet" crossorigin href="./assets/{TRIAD_ACCOUNTS_STYLESHEET}">'
    )
    script_tag = (
        f'<script type="module" crossorigin src="./assets/{TRIAD_ACCOUNTS_SCRIPT}"></script>'
    )
    bundle_script_tag = (
        f'<script type="module" crossorigin src="./assets/{bundle_path.name}"></script>'
    )

    if TRIAD_ACCOUNTS_STYLESHEET not in index_content:
        updated = _inject_html_tag(index_content, css_tag, "</head>")
        changed |= updated != index_content
        index_content = updated
    if TRIAD_ACCOUNTS_SCRIPT not in index_content:
        script_marker = bundle_script_tag if bundle_script_tag in index_content else "</head>"
        updated = _inject_html_tag(index_content, script_tag, script_marker)
        changed |= updated != index_content
        index_content = updated

    if changed:
        index_path.write_text(index_content, encoding="utf-8")
        print("  PATCHED: Accounts CSS/JS injection tags added to webview/index.html")

    bundle_content = bundle_path.read_text(encoding="utf-8")
    bundle_changed = False

    route_find = (
        "(0,$.jsx)(_,{path:`/skills/plugins/:pluginId`,element:(0,$.jsx)(ms,{})}),"
        "(0,$.jsx)(_,{path:`/skills`,element:(0,$.jsx)(Sl,{})})]})]})]});"
    )
    route_replace = (
        "(0,$.jsx)(_,{path:`/skills/plugins/:pluginId`,element:(0,$.jsx)(ms,{})}),"
        f"(0,$.jsx)(_,{{path:`{TRIAD_ACCOUNTS_ROUTE}`,element:window.__triadAccountsPage?(0,$.jsx)(window.__triadAccountsPage,{{}}):(0,$.jsx)(KUe,{{}})}}),"
        "(0,$.jsx)(_,{path:`/skills`,element:(0,$.jsx)(Sl,{})})]})]})]});"
    )
    bundle_content, route_applied = _inject_bundle_string(bundle_content, route_find, route_replace)
    bundle_changed |= route_applied

    sidebar_find = (
        "!de&&xt?(0,$.jsx)(_g,{icon:Ug,onClick:()=>{l.get(Vs).log({eventName:`codex_app_nav_clicked`,metadata:{item:`automations`}}),s(`/inbox`)},isActive:c.pathname.startsWith(`/inbox`),badge:ht>0?ht:void 0,label:(0,$.jsx)(Y,{id:`sidebarElectron.inboxRouteNavLink`,defaultMessage:`Automations`,description:`Nav link that opens the inbox (automations) route`})}):null,"
        "ue===`dev`||ue===`agent`?(0,$.jsx)(_g,{icon:pc,onClick:zx,label:(0,$.jsx)(Y,{id:`sidebarElectron.debugNavLink`,defaultMessage:`Debug`,description:`Nav link that opens the debug window`})}):null"
    )
    sidebar_replace = (
        "!de&&xt?(0,$.jsx)(_g,{icon:Ug,onClick:()=>{l.get(Vs).log({eventName:`codex_app_nav_clicked`,metadata:{item:`automations`}}),s(`/inbox`)},isActive:c.pathname.startsWith(`/inbox`),badge:ht>0?ht:void 0,label:(0,$.jsx)(Y,{id:`sidebarElectron.inboxRouteNavLink`,defaultMessage:`Automations`,description:`Nav link that opens the inbox (automations) route`})}):null,"
        f"window.__triadAccountsPage?(0,$.jsx)(_g,{{icon:window.__triadAccountsIcon,onClick:()=>{{l.get(Vs).log({{eventName:`codex_app_nav_clicked`,metadata:{{item:`accounts`}}}}),s(`{TRIAD_ACCOUNTS_ROUTE}`)}},isActive:c.pathname.startsWith(`{TRIAD_ACCOUNTS_ROUTE}`),label:(0,$.jsx)(Y,{{id:`sidebarElectron.accountsRouteNavLink`,defaultMessage:`Accounts`,description:`Nav link that opens the accounts page`}})}}):null,"
        "ue===`dev`||ue===`agent`?(0,$.jsx)(_g,{icon:pc,onClick:zx,label:(0,$.jsx)(Y,{id:`sidebarElectron.debugNavLink`,defaultMessage:`Debug`,description:`Nav link that opens the debug window`})}):null"
    )
    bundle_content, sidebar_applied = _inject_bundle_string(bundle_content, sidebar_find, sidebar_replace)
    bundle_changed |= sidebar_applied

    if bundle_changed:
        bundle_path.write_text(bundle_content, encoding="utf-8")
        print("  PATCHED: Accounts route and sidebar entry injected into webview bundle")
    else:
        print("  SKIP: Accounts injection already present or bundle patterns changed")

    return changed or bundle_changed
