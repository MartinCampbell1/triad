"""Patch definitions for Codex Desktop App."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StringPatch:
    """One string replacement in a file."""
    file: str  # relative path within extracted asar
    find: str
    replace: str
    description: str


# All patches for Codex app
PATCHES: list[StringPatch] = [
    # 1. Redirect main API to Triad Proxy
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find="https://chatgpt.com/backend-api",
        replace="http://127.0.0.1:9377/api",
        description="Redirect ChatGPT backend API to Triad Proxy",
    ),

    # 2. Disable Sentry crash reporting
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="https://6719eaa18601933a26ac21499dcaba2f@o33249.ingest.us.sentry.io/4510999349821440",
        replace="https://disabled@localhost/0",
        description="Disable Sentry crash reporting to OpenAI",
    ),

    # 3. Disable telemetry intake (product-name bundle)
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="https://chat.openai.com/ces/v1/telemetry/intake",
        replace="http://127.0.0.1:9377/api/telemetry/noop",
        description="Disable telemetry in product-name bundle",
    ),

    # 3b. Rewrite desktop product identity away from Codex
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="var Q9=`Codex`;",
        replace="var Q9=`Triad`;",
        description="Rename desktop product name to Triad",
    ),
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="Ib=`Codex Desktop`",
        replace="Ib=`Triad Desktop`",
        description="Rename desktop branding string to Triad Desktop",
    ),
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="function Aue(e){switch(e){case V.Agent:return`com.openai.codex.agent`;case V.Dev:return`com.openai.codex.dev`;case V.Nightly:return`com.openai.codex.nightly`;case V.InternalAlpha:return`com.openai.codex.alpha`;case V.PublicBeta:return`com.openai.codex.beta`;case V.Prod:return`com.openai.codex`}}",
        replace="function Aue(e){switch(e){case V.Agent:return`com.triad.orchestrator.agent`;case V.Dev:return`com.triad.orchestrator.dev`;case V.Nightly:return`com.triad.orchestrator.nightly`;case V.InternalAlpha:return`com.triad.orchestrator.alpha`;case V.PublicBeta:return`com.triad.orchestrator.beta`;case V.Prod:return`com.triad.orchestrator`}}",
        description="Rewrite bundle identifiers to Triad namespace",
    ),
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="if(!e.startsWith(`codex://`))return null;",
        replace="if(!e.startsWith(`triad://`))return null;",
        description="Rewrite deep-link scheme to triad://",
    ),
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="if(t.protocol!==`codex:`)return null;",
        replace="if(t.protocol!==`triad:`)return null;",
        description="Rewrite deep-link protocol guard to triad:",
    ),
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="e.setAsDefaultProtocolClient(`codex`)",
        replace="e.setAsDefaultProtocolClient(`triad`)",
        description="Register triad protocol handler instead of codex",
    ),
    StringPatch(
        file=".vite/build/product-name-CswjKXkf.js",
        find="Failed to register codex:// protocol handler",
        replace="Failed to register triad:// protocol handler",
        description="Rewrite protocol handler warning text",
    ),

    # 4. Disable telemetry intake (worker bundle)
    StringPatch(
        file=".vite/build/worker.js",
        find="https://chat.openai.com/ces/v1/telemetry/intake",
        replace="http://127.0.0.1:9377/api/telemetry/noop",
        description="Disable telemetry in worker bundle",
    ),

    # 5. Disable Sparkle auto-updater
    StringPatch(
        file="package.json",
        find='"codexSparkleFeedUrl":"https://persistent.oaistatic.com/codex-app-prod/appcast.xml"',
        replace='"codexSparkleFeedUrl":""',
        description="Disable Sparkle auto-updater feed URL",
    ),

    # 6. Move devtools reset cache paths off the shared Codex support directory
    StringPatch(
        file="package.json",
        find="$HOME/Library/Application Support/Codex",
        replace="$HOME/Library/Application Support/Triad",
        description="Redirect devtools cache reset path to Triad",
    ),

    # 7. Rewrite remaining desktop UI identity and auth text.
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find="$e=`Codex Desktop`",
        replace="$e=`Triad Desktop`",
        description="Rename main desktop branding string to Triad Desktop",
    ),
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find="Codex Desktop",
        replace="Triad Desktop",
        description="Rewrite remaining main-bundle Codex Desktop strings",
    ),
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find="throw Error(`Sign in to ChatGPT in Codex Desktop to ${e}.`);",
        replace="throw Error(`Open Accounts in Triad to ${e}.`);",
        description="Replace ChatGPT auth prompt with Triad Accounts guidance",
    ),
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find="Sign in to ChatGPT in Triad Desktop to ${e}.",
        replace="Open Accounts in Triad to ${e}.",
        description="Rewrite remaining Triad Desktop auth prompt to Accounts guidance",
    ),
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find='"app-connect-oauth-callback-url":async()=>({callbackUrl:`codex://connector/oauth_callback`}),',
        replace='"app-connect-oauth-callback-url":async()=>({callbackUrl:`triad://connector/oauth_callback`}),',
        description="Rewrite app-connect OAuth callback to triad://",
    ),

    # 8. Do not let workspace-root permission errors fail the entire desktop UI.
    StringPatch(
        file=".vite/build/main-8X_hBwW2.js",
        find='"paths-exist":async({paths:t})=>({existingPaths:tr(await e.Qt(ir(t??[],this.shouldUseWslPaths()),this.appServerClient),this.shouldUseWslPaths())}),',
        replace='"paths-exist":async({paths:t})=>{try{return{existingPaths:tr(await e.Qt(ir(t??[],this.shouldUseWslPaths()),this.appServerClient),this.shouldUseWslPaths())}}catch(n){return{existingPaths:[]}}},',
        description="Treat inaccessible workspace roots as missing instead of fatal",
    ),

    # 9. Rewrite onboarding UI to Triad branding and Accounts flow.
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="defaultMessage:`Codex`,description:`Title shown in the draggable header on the desktop onboarding pages`",
        replace="defaultMessage:`Triad`,description:`Title shown in the draggable header on the desktop onboarding pages`",
        description="Rename onboarding shell title to Triad",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="defaultMessage:`Welcome to Codex`,description:`Title on the desktop onboarding login page`",
        replace="defaultMessage:`Welcome to Triad`,description:`Title on the desktop onboarding login page`",
        description="Rename onboarding welcome title to Triad",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="defaultMessage:`Codex`",
        replace="defaultMessage:`Triad`",
        description="Rewrite remaining webview fallback Codex titles to Triad",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="return e===`electron`?i||(t.isLoading?null:!t.authMethod&&t.requiresAuth?`login`:a&&(o===CUe||o===wUe)?`welcome`:r?null:(n?.roots??[]).length===0?`workspace`:`app`):`app`}",
        replace="return e===`electron`?i||(t.isLoading?null:r?null:`app`):`app`}",
        description="Start desktop directly in the main app shell without onboarding workspace mode",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="let e=h===`app`?`app`:`onboarding`;k.dispatchMessage(`electron-set-window-mode`,{mode:e})",
        replace="let e=`app`;k.dispatchMessage(`electron-set-window-mode`,{mode:e})",
        description="Keep the desktop window in full app mode during Triad startup",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="c=t===`electron`&&(a!==`auto`||r.authMethod!=null||r.requiresAuth===!1),",
        replace="c=t===`electron`,",
        description="Always query workspace root options in desktop wrapper",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="t.pathname.startsWith(`/settings`)||n(`${t.pathname}${t.search}${t.hash}`)",
        replace="t.pathname.startsWith(`/settings`)||t.pathname.startsWith(`/accounts`)||n(`${t.pathname}${t.search}${t.hash}`)",
        description="Do not persist the Accounts route as the startup location",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="onChatGptSignIn:O,onShowApiKeyEntry:()=>{i.get(Vs).log({eventName:`codex_onboarding_login_method_selected`,metadata:{method:`apikey`}}),m(!0)},",
        replace="onChatGptSignIn:()=>n(`/`),onShowApiKeyEntry:()=>n(`/`),",
        description="Keep onboarding actions inside the main app shell",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="e=()=>{i(!1),a(`/login`)}",
        replace="e=()=>{i(!1),a(`/`)}",
        description="Redirect profile sign-in action back to the main app shell",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="onClick:async()=>{i(!1),await b(!1),await o.logout(),a(`/login`)}",
        replace="onClick:async()=>{i(!1),await b(!1),await o.logout(),a(`/`)}",
        description="Redirect logout flow back to the main app shell",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="(i=(0,$.jsx)(b,{to:`/login`,replace:!0}),e[2]=i)",
        replace="(i=(0,$.jsx)(b,{to:`/`,replace:!0}),e[2]=i)",
        description="Redirect auth-required fallback to the main app shell",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="if(r){let t;return e[0]===Symbol.for(`react.memo_cache_sentinel`)?(t=(0,$.jsx)($.Fragment,{}),e[0]=t):t=e[0],t}",
        replace="if(r){let t;return e[0]===Symbol.for(`react.memo_cache_sentinel`)?(t=(0,$.jsx)(b,{to:`/`,replace:!0}),e[0]=t):t=e[0],t}",
        description="Avoid blank renderer by redirecting pending auth fallback to root",
    ),
    StringPatch(
        file="webview/assets/onboarding-login-content-Cl3BGi_s.js",
        find="defaultMessage:`Continue with ChatGPT`",
        replace="defaultMessage:`Open Accounts`",
        description="Rename onboarding primary button to Open Accounts",
    ),
    StringPatch(
        file="webview/assets/onboarding-login-content-Cl3BGi_s.js",
        find="defaultMessage:`Enter API key`",
        replace="defaultMessage:`Open Accounts`",
        description="Rename onboarding secondary button to Open Accounts",
    ),
    StringPatch(
        file="webview/assets/remote-connections-settings-DKy-UXgi.js",
        find="defaultMessage:`Sign in to ChatGPT in Codex Desktop, then refresh to load remote control environments.`",
        replace="defaultMessage:`Open Accounts in Triad, then refresh to load remote control environments.`",
        description="Rewrite remote connections auth guidance to Triad Accounts",
    ),
    StringPatch(
        file="webview/assets/ru-RU-CH6yIUWS.js",
        find='"electron.onboarding.login.chatgpt.continue":`Продолжить с ChatGPT`',
        replace='"electron.onboarding.login.chatgpt.continue":`Открыть аккаунты`',
        description="Localize onboarding primary action to Accounts in Russian",
    ),
    StringPatch(
        file="webview/assets/ru-RU-CH6yIUWS.js",
        find='"electron.onboarding.login.apikey.open":`Введите API-ключ`',
        replace='"electron.onboarding.login.apikey.open":`Открыть аккаунты`',
        description="Localize onboarding secondary action to Accounts in Russian",
    ),
    StringPatch(
        file="webview/assets/ru-RU-CH6yIUWS.js",
        find='"electron.onboarding.login.title":`Добро пожаловать в Codex`',
        replace='"electron.onboarding.login.title":`Добро пожаловать в Triad`',
        description="Localize onboarding title to Triad in Russian",
    ),
    StringPatch(
        file="webview/assets/ru-RU-CH6yIUWS.js",
        find='"electron.onboarding.shell.title":`Codex`',
        replace='"electron.onboarding.shell.title":`Triad`',
        description="Localize onboarding shell title to Triad in Russian",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="var PJe=[`apps`,`plugins`,`tool_call_mcp_elicitation`,`tool_search`,`tool_suggest`];",
        replace="var PJe=[`apps`,`tool_call_mcp_elicitation`,`tool_search`,`tool_suggest`];",
        description="Disable plugin feature sync that still triggers Codex plugin auth paths",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="function ep(){let e=(0,Q.c)(11),{announcementContent:t,dismissAnnouncement:n,showAnnouncement:r}=Nf(),i=r&&t!=null",
        replace="function ep(){let e=(0,Q.c)(11),{announcementContent:t,dismissAnnouncement:n,showAnnouncement:r}=Nf(),i=!1",
        description="Disable Codex new-model announcement modal inside Triad",
    ),
    StringPatch(
        file="webview/assets/index--dL9tGqL.js",
        find="function $f(){ep(),np(),ip();let e=pn(zf),[t,n]=St(Lf),r=(0,Z.useRef)(null);if(t)return r.current=null,null;let i=e.find(e=>e.id===r.current);return i?.enabled||(i=e.find(e=>e.enabled),r.current=i?.id??null),i==null?null:i.render(()=>{n(!0),r.current=null,i.dismissAnnouncement()})}",
        replace="function $f(){return null}",
        description="Disable all startup announcement modals in Triad",
    ),
    StringPatch(
        file="triad-accounts-injection.js",
        find="without leaving the Codex UI.",
        replace="without leaving the Triad UI.",
        description="Rename injected Accounts helper copy to Triad UI",
    ),
]


# CSP patch for index.html — needs special handling (not simple string replace)
CSP_ADDITIONS = "http://127.0.0.1:9377 ws://127.0.0.1:9377"

TRIAD_ACCOUNTS_ROUTE = "/accounts"
TRIAD_ACCOUNTS_STYLESHEET = "triad-accounts.css"
TRIAD_ACCOUNTS_SCRIPT = "triad-accounts-injection.js"

BOOTSTRAP_INJECTION = '''
// === TRIAD PATCHES ===
try {
  var __triadPath = require("node:path");
  var __triadFs = require("node:fs");
  var __triadHome = (process.env.TRIAD_HOME || "").trim() || __triadPath.join(process.env.HOME || "", ".triad");
  process.env.TRIAD_HOME = __triadHome;
  process.env.CODEX_HOME = __triadHome;
  __triadFs.mkdirSync(__triadHome, { recursive: true });
} catch (e) {}

// Suppress EPIPE errors — Electron pipes can break when Sentry/telemetry writes to closed streams
process.on("uncaughtException", function(err) {
  if (err && err.code === "EPIPE") return;
  throw err;
});
process.stdout.on("error", function(err) { if (err.code !== "EPIPE") throw err; });
process.stderr.on("error", function(err) { if (err.code !== "EPIPE") throw err; });

// Start Triad Proxy before the rest of the desktop bootstrap continues.
try {
  globalThis.__triadProxyReady = function() {
    var _tl = require("./triad-launcher.js");
    return _tl.startTriadProxy();
  };
} catch (e) {}
// === END TRIAD ===
'''
