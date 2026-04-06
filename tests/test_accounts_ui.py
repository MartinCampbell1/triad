from pathlib import Path

from triad.patcher.accounts_ui import inject_accounts_ui


def test_inject_accounts_ui_uses_head_marker_and_dynamic_bundle_name(tmp_path: Path):
    webview_dir = tmp_path / "webview"
    assets_dir = webview_dir / "assets"
    assets_dir.mkdir(parents=True)

    (webview_dir / "index.html").write_text(
        '<html><head><script type="module" crossorigin src="./assets/index--abc123.js"></script></head><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (assets_dir / "index--abc123.js").write_text(
        "(0,$.jsx)(_,{path:`/skills/plugins/:pluginId`,element:(0,$.jsx)(ms,{})}),(0,$.jsx)(_,{path:`/skills`,element:(0,$.jsx)(Sl,{})})]})]})]});"
        "!de&&xt?(0,$.jsx)(_g,{icon:Ug,onClick:()=>{l.get(Vs).log({eventName:`codex_app_nav_clicked`,metadata:{item:`automations`}}),s(`/inbox`)},isActive:c.pathname.startsWith(`/inbox`),badge:ht>0?ht:void 0,label:(0,$.jsx)(Y,{id:`sidebarElectron.inboxRouteNavLink`,defaultMessage:`Automations`,description:`Nav link that opens the inbox (automations) route`})}):null,"
        "ue===`dev`||ue===`agent`?(0,$.jsx)(_g,{icon:pc,onClick:zx,label:(0,$.jsx)(Y,{id:`sidebarElectron.debugNavLink`,defaultMessage:`Debug`,description:`Nav link that opens the debug window`})}):null",
        encoding="utf-8",
    )

    assert inject_accounts_ui(tmp_path) is True

    index_html = (webview_dir / "index.html").read_text(encoding="utf-8")
    assert "./assets/triad-accounts.css" in index_html
    assert "./assets/triad-accounts-injection.js" in index_html
    assert index_html.index("./assets/triad-accounts-injection.js") < index_html.index("./assets/index--abc123.js")

    bundle = (assets_dir / "index--abc123.js").read_text(encoding="utf-8")
    assert "path:`/accounts`" in bundle
    assert "window.__triadAccountsPage?(0,$.jsx)(window.__triadAccountsPage,{}):(0,$.jsx)(KUe,{})" in bundle


def test_inject_accounts_ui_is_noop_when_bundle_missing(tmp_path: Path):
    webview_dir = tmp_path / "webview"
    webview_dir.mkdir(parents=True)
    (webview_dir / "index.html").write_text(
        "<html><head></head><body></body></html>",
        encoding="utf-8",
    )

    assert inject_accounts_ui(tmp_path) is False
