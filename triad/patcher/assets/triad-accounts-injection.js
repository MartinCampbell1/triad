import { t as ReactModule } from "./react-CmOmxWgC.js";
import { t as jsxRuntimeModule } from "./jsx-runtime-C0i2Pncv.js";

const React = ReactModule();
const jsxRuntime = jsxRuntimeModule();
const { useCallback, useEffect, useMemo, useRef, useState } = React;
const { jsx, jsxs, Fragment } = jsxRuntime;

const API_BASE = "http://127.0.0.1:9377/api";
const PROVIDER_TITLES = {
  claude: "Claude",
  codex: "Codex",
  gemini: "Gemini",
};

function request(path, options = {}) {
  return fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  }).then(async (response) => {
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = text;
    }
    if (!response.ok) {
      const message = typeof payload === "string" ? payload : payload?.detail ?? response.statusText;
      throw new Error(message || `Request failed with ${response.status}`);
    }
    return payload;
  });
}

function shortCount(value) {
  return new Intl.NumberFormat().format(value ?? 0);
}

function formatCooldown(sec) {
  if (!sec || sec <= 0) {
    return "ready";
  }
  if (sec < 60) {
    return `${sec}s cooldown`;
  }
  const minutes = Math.max(1, Math.ceil(sec / 60));
  return `${minutes}m cooldown`;
}

function providerTitle(provider) {
  return PROVIDER_TITLES[provider] ?? provider;
}

function toneForProfile(profile) {
  if (profile.cooldown_remaining_sec > 0) return "warning";
  if (profile.available) return "success";
  return "muted";
}

function AccountsIcon(props) {
  return jsx("svg", {
    viewBox: "0 0 20 20",
    fill: "none",
    xmlns: "http://www.w3.org/2000/svg",
    ...props,
    children: jsxs(Fragment, {
      children: [
        jsx("path", {
          d: "M10 11.25C12.0711 11.25 13.75 9.57107 13.75 7.5C13.75 5.42893 12.0711 3.75 10 3.75C7.92893 3.75 6.25 5.42893 6.25 7.5C6.25 9.57107 7.92893 11.25 10 11.25Z",
          stroke: "currentColor",
          strokeWidth: "1.5",
          strokeLinecap: "round",
          strokeLinejoin: "round",
        }),
        jsx("path", {
          d: "M4.5 16.25C5.41 13.67 7.55 12.5 10 12.5C12.45 12.5 14.59 13.67 15.5 16.25",
          stroke: "currentColor",
          strokeWidth: "1.5",
          strokeLinecap: "round",
          strokeLinejoin: "round",
        }),
        jsx("path", {
          d: "M15.75 6.25H18M16.875 5.125V7.375",
          stroke: "currentColor",
          strokeWidth: "1.5",
          strokeLinecap: "round",
          strokeLinejoin: "round",
        }),
      ],
    }),
  });
}

function Pill({ tone = "neutral", children }) {
  return jsx("span", {
    className: `triad-pill triad-pill--${tone}`,
    children,
  });
}

function ActionButton({ children, onClick, disabled = false, variant = "secondary" }) {
  return jsx("button", {
    type: "button",
    disabled,
    onClick,
    className: `triad-button triad-button--${variant}`,
    children,
  });
}

function CountCard({ label, value, accent = "default" }) {
  return jsxs("div", {
    className: `triad-accounts-stat triad-accounts-stat--${accent}`,
    children: [
      jsx("div", {
        className: "triad-accounts-stat__label",
        children: label,
      }),
      jsx("div", {
        className: "triad-accounts-stat__value",
        children: value,
      }),
    ],
  });
}

function ProfileRow({ profile }) {
  const tone = toneForProfile(profile);
  const label =
    tone === "success"
      ? "available"
      : profile.cooldown_remaining_sec > 0
        ? formatCooldown(profile.cooldown_remaining_sec)
        : "offline";
  return jsxs("div", {
    className: "triad-profile-row",
    children: [
      jsxs("div", {
        className: "triad-profile-row__meta",
        children: [
          jsx("div", {
            className: "triad-profile-row__name",
            children: profile.name,
          }),
          jsx("div", {
            className: "triad-profile-row__summary",
            children: `${shortCount(profile.requests_made)} requests · ${shortCount(profile.errors)} errors`,
          }),
        ],
      }),
      jsxs("div", {
        className: "triad-profile-row__status",
        children: [
          jsx(Pill, { tone, children: label }),
        ],
      }),
    ],
  });
}

function ProviderCard({ provider, info, refresh, notify }) {
  const profiles = info?.profiles ?? [];
  const available = info?.available_profile_count ?? 0;
  const cooldown = info?.cooldown_profile_count ?? 0;
  const hasSource = Boolean(info?.source_session_available);

  const doOpenLogin = useCallback(async () => {
    try {
      await request(`/accounts/${provider}/open-login`, { method: "POST" });
      notify(`${providerTitle(provider)} login opened.`, "success");
      await refresh();
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error), "error");
    }
  }, [notify, provider, refresh]);

  const doImport = useCallback(async () => {
    try {
      const payload = await request(`/accounts/${provider}/import`, { method: "POST" });
      notify(payload?.message ?? `${providerTitle(provider)} session imported.`, "success");
      await refresh();
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error), "error");
    }
  }, [notify, provider, refresh]);

  return jsxs("section", {
    className: "triad-provider-card triad-accounts-fade-in",
    children: [
      jsxs("div", {
        className: "triad-provider-card__top",
        children: [
          jsxs("div", {
            className: "triad-provider-card__identity",
            children: [
              jsx("div", {
                className: "triad-provider-card__eyebrow",
                children: provider,
              }),
              jsx("h3", {
                className: "triad-provider-card__title",
                children: providerTitle(provider),
              }),
              jsx("div", {
                className: "triad-provider-card__command",
                children: info?.login_command ? `Login: ${info.login_command}` : "No login command available",
              }),
            ],
          }),
          jsx(Pill, {
            tone: hasSource ? "success" : "muted",
            children: hasSource ? "session detected" : "no session",
          }),
        ],
      }),
      jsxs("div", {
        className: "triad-provider-card__toolbar",
        children: [
          jsx(ActionButton, { variant: "primary", onClick: doOpenLogin, children: "Open login" }),
          jsx(ActionButton, { onClick: doImport, disabled: !hasSource, children: "Import session" }),
          jsx(Pill, { tone: available > 0 ? "success" : "warning", children: `${shortCount(available)} available` }),
          jsx(Pill, { tone: cooldown > 0 ? "warning" : "muted", children: `${shortCount(cooldown)} cooldown` }),
        ],
      }),
      jsx("div", {
        className: "triad-provider-card__profiles",
        children:
          profiles.length > 0
            ? profiles.map((profile) => jsx(ProfileRow, { profile }, profile.name))
            : jsx("div", {
                className: "triad-provider-card__empty",
                children: "No managed profiles found for this provider.",
              }),
      }),
    ],
  });
}

function AccountsPage() {
  const [diagnostics, setDiagnostics] = useState(null);
  const [health, setHealth] = useState(null);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const noticeTimerRef = useRef(null);

  const notify = useCallback((message, tone = "info") => {
    if (noticeTimerRef.current != null) {
      window.clearTimeout(noticeTimerRef.current);
      noticeTimerRef.current = null;
    }
    if (tone === "error") {
      setError(message);
      setNotice(null);
    } else {
      setNotice(message);
      setError(null);
      noticeTimerRef.current = window.setTimeout(() => {
        setNotice(null);
        noticeTimerRef.current = null;
      }, 2400);
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [diag, healthPayload] = await Promise.all([
        request("/accounts/diagnostics"),
        request("/accounts/health"),
      ]);
      setDiagnostics(diag);
      setHealth(healthPayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const providers = useMemo(() => {
    const payload = diagnostics?.providers ?? {};
    const priority = diagnostics?.providers_priority ?? Object.keys(payload);
    return priority.map((provider) => ({
      provider,
      info: payload[provider] ?? { profiles: [] },
    }));
  }, [diagnostics]);

  const totals = {
    total: health?.total ?? 0,
    available: health?.available ?? 0,
    on_cooldown: health?.on_cooldown ?? 0,
  };

  return jsxs("div", {
    className: "triad-accounts-shell",
    children: [
      jsxs("div", {
        className: "triad-accounts-page",
        children: [
          jsxs("header", {
            className: "triad-accounts-header",
            children: [
              jsxs("div", {
                className: "triad-accounts-header__top",
                children: [
                  jsxs("div", {
                    className: "triad-accounts-header__copy",
                    children: [
                      jsx("div", {
                        className: "triad-accounts-kicker",
                        children: [
                          jsx(AccountsIcon, { className: "triad-accounts-kicker__icon" }),
                          "Accounts",
                        ],
                      }),
                      jsx("h1", {
                        className: "triad-accounts-title",
                        children: "Accounts",
                      }),
                      jsx("p", {
                        className: "triad-accounts-subtitle",
                        children:
                          "Monitor provider profiles, open login flows, import active CLI sessions, and check cooldown status inside the main Triad workspace.",
                      }),
                    ],
                  }),
                  jsx("div", {
                    className: "triad-accounts-header__actions",
                    children: jsx(ActionButton, {
                      onClick: refresh,
                      children: loading ? "Refreshing..." : "Reload",
                    }),
                  }),
                ],
              }),
              notice
                ? jsx("div", {
                    className: "triad-accounts-notice triad-accounts-notice--info",
                    children: notice,
                  })
                : null,
              error
                ? jsx("div", {
                    className: "triad-accounts-notice triad-accounts-notice--error",
                    children: error,
                  })
                : null,
              jsx("div", {
                className: "triad-accounts-section-grid",
                children: [
                  jsx(CountCard, { label: "Profiles", value: shortCount(totals.total), accent: "blue" }),
                  jsx(CountCard, { label: "Available", value: shortCount(totals.available), accent: "green" }),
                  jsx(CountCard, { label: "Cooldown", value: shortCount(totals.on_cooldown) }),
                ],
              }),
            ],
          }),
          jsx("section", {
            className: "triad-accounts-card-grid",
            children: providers.map(({ provider, info }) =>
              jsx(ProviderCard, {
                provider,
                info,
              refresh: async () => {
                  await refresh();
                },
                notify,
              }, provider),
            ),
          }),
        ],
      }),
    ],
  });
}

window.__triadAccountsIcon = AccountsIcon;
window.__triadAccountsPage = AccountsPage;
