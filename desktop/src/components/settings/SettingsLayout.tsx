import { useState } from "react";
import {
  surfaceBadge,
  surfaceFooter,
  surfaceHeader,
  surfaceShell,
} from "../shared/surfaceStyles";

interface SettingsNavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: SettingsNavItem[] = [
  {
    id: "general",
    label: "General",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
        <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "appearance",
    label: "Appearance",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2" />
        <path d="M8 1.5V8h6.5" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    ),
  },
  {
    id: "configuration",
    label: "Configuration",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "personalization",
    label: "Personalization",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.2" />
        <path d="M2 14c0-3.3 2.7-5 6-5s6 1.7 6 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "usage",
    label: "Usage",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="1.5" y="3.5" width="13" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
        <path d="M4 7h3M4 9.5h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "mcp",
    label: "MCP Servers",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="3" y="2" width="10" height="4" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="3" y="10" width="10" height="4" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <path d="M8 6v4" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    ),
  },
  {
    id: "git",
    label: "Git",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="4" cy="4" r="1.5" stroke="currentColor" strokeWidth="1.2" />
        <circle cx="4" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.2" />
        <circle cx="12" cy="8" r="1.5" stroke="currentColor" strokeWidth="1.2" />
        <path d="M4 5.5V10.5M5.5 4h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "environments",
    label: "Environments",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.2" />
        <path d="M5 6l2 2-2 2M8.5 10H11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "worktrees",
    label: "Worktrees",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M3 3v10M3 8h5M8 5v6M8 8h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "archived",
    label: "Archived Threads",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="12" height="3" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <path d="M3 5v8a1 1 0 001 1h8a1 1 0 001-1V5" stroke="currentColor" strokeWidth="1.2" />
        <path d="M6.5 8.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    ),
  },
];

interface Props {
  onBack: () => void;
}

export function SettingsLayout({ onBack }: Props) {
  const [activeSection, setActiveSection] = useState("general");

  return (
    <div className="flex h-full w-full bg-[var(--color-bg-surface)]">
      {/* Settings sidebar */}
      <nav className="flex w-[220px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-surface)] pt-6">
        <button
          onClick={onBack}
          className="mx-3 mb-4 flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-[var(--color-text-secondary)] transition-colors duration-150 hover:text-[var(--color-text-primary)]"
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M10 4L6 8L10 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Back to app</span>
        </button>
        <div className="flex-1 overflow-y-auto px-2">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveSection(item.id)}
              className={[
                "flex w-full items-center gap-2.5 rounded-lg px-3 py-[6px] text-left text-[13px] transition-colors duration-150",
                activeSection === item.id
                  ? "bg-[rgba(255,255,255,0.06)] text-[var(--color-text-primary)]"
                  : "text-[var(--color-text-secondary)] hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-text-primary)]",
              ].join(" ")}
            >
              <span className="shrink-0 text-[var(--color-text-tertiary)]">{item.icon}</span>
              <span className="truncate">{item.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Settings content */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className={`mx-auto flex min-h-full max-w-[880px] flex-col ${surfaceShell}`}>
          <div className={surfaceHeader}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[12px] uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">Settings</div>
                <div className="mt-1 text-[14px] text-[var(--color-text-primary)]">Unified sheet layout for search, commands, and preferences</div>
              </div>
              <span className={surfaceBadge}>Esc back</span>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-8 py-7">
            <div className="max-w-[720px]">
              {activeSection === "general" && <GeneralSettings />}
              {activeSection === "appearance" && <AppearanceSettings />}
              {activeSection === "configuration" && <ConfigurationSettings />}
              {activeSection === "personalization" && <PersonalizationSettings />}
              {activeSection === "usage" && <UsageSettings />}
              {activeSection === "mcp" && <MCPSettings />}
              {activeSection === "git" && <GitSettings />}
              {activeSection === "environments" && <PlaceholderSection title="Environments" />}
              {activeSection === "worktrees" && <PlaceholderSection title="Worktrees" />}
              {activeSection === "archived" && <PlaceholderSection title="Archived Threads" />}
            </div>
          </div>

          <div className={surfaceFooter}>
            <span>Categories stay fixed on the left</span>
            <span>{activeSection}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-[24px] font-semibold text-[var(--color-text-primary)]">{title}</h1>
      {subtitle ? <p className="mt-1 text-[13px] text-[var(--color-text-tertiary)]">{subtitle}</p> : null}
    </div>
  );
}

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <div className="text-[13px] text-[var(--color-text-primary)]">{label}</div>
        {description ? <div className="mt-0.5 text-[12px] text-[var(--color-text-tertiary)]">{description}</div> : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function SelectInput({ value, options, onChange }: { value: string; options: Array<{ value: string; label: string }>; onChange?: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      className="rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-3 py-1.5 text-[13px] text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange?: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange?.(!checked)}
      className={`relative h-[22px] w-[40px] rounded-full transition-colors duration-150 ${checked ? "bg-[var(--blue-400)]" : "bg-[var(--color-bg-elevated)]"}`}
    >
      <span className={`absolute top-[2px] h-[18px] w-[18px] rounded-full bg-white shadow transition-transform duration-150 ${checked ? "left-[20px]" : "left-[2px]"}`} />
    </button>
  );
}

function GeneralSettings() {
  return (
    <div>
      <SectionTitle title="General" />
      <SettingRow label="Default destination" description="Choose where files and folders open by default.">
        <SelectInput value="terminal" options={[{ value: "terminal", label: "Terminal" }, { value: "finder", label: "Finder" }]} />
      </SettingRow>
      <SettingRow label="Language" description="Choose the application language.">
        <SelectInput value="auto" options={[{ value: "auto", label: "Auto detect" }, { value: "ru", label: "Russian" }, { value: "en", label: "English" }]} />
      </SettingRow>
      <SettingRow label="Thread details" description="Choose how much execution detail appears in threads.">
        <SelectInput value="code" options={[{ value: "code", label: "Code steps only" }, { value: "all", label: "All steps" }]} />
      </SettingRow>
      <div className="my-4 border-t border-[var(--color-border)]" />
      <SettingRow label="Prevent sleep while working" description="Keep the computer awake while Codex is running a task.">
        <Toggle checked={true} />
      </SettingRow>
      <SettingRow label="Require ⌥ + Enter for multiline prompts" description="When enabled, use ⌥ + Enter to send multi-line prompts.">
        <Toggle checked={false} />
      </SettingRow>
      <div className="my-4 border-t border-[var(--color-border)]" />
      <SettingRow label="Speed" description="Choose how quickly inference runs across threads, subagents, and compute.">
        <SelectInput value="standard" options={[{ value: "standard", label: "Standard" }, { value: "fast", label: "Fast" }]} />
      </SettingRow>
      <SettingRow label="Follow-up behavior" description="Controls whether tasks queue automatically or wait for confirmation.">
        <div className="flex gap-2">
          <button className="rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-3 py-1 text-[12px] text-[var(--color-text-primary)]">Queue</button>
          <button className="rounded-md border border-[var(--color-border)] px-3 py-1 text-[12px] text-[var(--color-text-tertiary)]">Prompt</button>
        </div>
      </SettingRow>
      <div className="my-6 border-t border-[var(--color-border)]" />
      <h2 className="mb-3 text-[16px] font-medium text-[var(--color-text-primary)]">Notifications</h2>
      <SettingRow label="Completion notifications" description="Choose when Codex notifies you that work is complete.">
        <SelectInput value="unfocused" options={[{ value: "unfocused", label: "Only when unfocused" }, { value: "always", label: "Always" }, { value: "never", label: "Never" }]} />
      </SettingRow>
      <SettingRow label="Permission notifications" description="Show a notification when permission is required to send notifications.">
        <Toggle checked={true} />
      </SettingRow>
    </div>
  );
}

function AppearanceSettings() {
  return (
    <div>
      <SectionTitle title="Appearance" subtitle="Use the light, dark, or system theme." />
      <div className="mb-4 flex gap-3">
        <button className="rounded-md border border-[var(--color-border)] px-4 py-1.5 text-[13px] text-[var(--color-text-tertiary)]">Light</button>
        <button className="rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-4 py-1.5 text-[13px] text-[var(--color-text-primary)]">Dark</button>
        <button className="rounded-md border border-[var(--color-border)] px-4 py-1.5 text-[13px] text-[var(--color-text-tertiary)]">System</button>
      </div>
      <div className="my-4 border-t border-[var(--color-border)]" />
      <h2 className="mb-3 text-[14px] font-medium text-[var(--color-text-primary)]">Dark theme</h2>
      <SettingRow label="Accent">
        <div className="h-7 w-20 rounded-md bg-[var(--blue-300)]" />
      </SettingRow>
      <SettingRow label="Background">
        <input type="text" value="#181818" readOnly className="w-20 rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-2 py-1 text-center text-[12px] text-[var(--color-text-primary)]" />
      </SettingRow>
      <SettingRow label="Foreground">
        <input type="text" value="#ffffff" readOnly className="w-20 rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-2 py-1 text-center text-[12px] text-[var(--color-text-primary)]" />
      </SettingRow>
      <SettingRow label="UI font">
        <span className="text-[13px] text-[var(--color-text-tertiary)]">-apple-system, BlinkM...</span>
      </SettingRow>
      <SettingRow label="Code font">
        <span className="text-[13px] text-[var(--color-text-tertiary)]">ui-monospace, "SFMo...</span>
      </SettingRow>
      <SettingRow label="Translucent sidebar">
        <Toggle checked={true} />
      </SettingRow>
      <SettingRow label="Contrast">
        <input type="range" min="30" max="80" defaultValue="48" className="w-32" />
      </SettingRow>
    </div>
  );
}

function ConfigurationSettings() {
  return (
    <div>
      <SectionTitle title="Configuration" subtitle="Configure approval policy and sandbox settings." />
      <div className="rounded-lg border border-[var(--color-border)] p-4">
        <SettingRow label="Approval policy" description="Choose when Codex asks for approval">
          <SelectInput value="on-request" options={[{ value: "on-request", label: "On request" }, { value: "auto", label: "Auto" }]} />
        </SettingRow>
        <SettingRow label="Sandbox settings" description="Choose how much Codex can do when running commands.">
          <SelectInput value="read-only" options={[{ value: "read-only", label: "Read only" }, { value: "full", label: "Full access" }]} />
        </SettingRow>
      </div>
    </div>
  );
}

function PersonalizationSettings() {
  return (
    <div>
      <SectionTitle title="Personalization" subtitle="Tailor Codex's personality and instructions." />
      <div className="rounded-lg border border-[var(--color-border)] p-4">
        <SettingRow label="Personality" description="Choose the default tone for Codex responses.">
          <SelectInput value="pragmatic" options={[{ value: "pragmatic", label: "Pragmatic" }, { value: "friendly", label: "Friendly" }, { value: "formal", label: "Formal" }]} />
        </SettingRow>
      </div>
      <div className="mt-6">
        <h2 className="mb-2 text-[14px] font-medium text-[var(--color-text-primary)]">Custom instructions</h2>
        <textarea
          placeholder="Add your own instructions..."
          className="h-32 w-full rounded-lg border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] p-3 text-[13px] text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-border-focus)]"
        />
        <div className="mt-2 flex justify-end">
          <button className="rounded-md bg-[var(--color-bg-elevated)] px-4 py-1.5 text-[13px] text-[var(--color-text-primary)] transition-colors duration-150 hover:bg-[var(--color-bg-elevated-secondary)]">
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

function UsageSettings() {
  return (
    <div>
      <SectionTitle title="Usage" />
      <h2 className="mb-3 text-[14px] font-medium text-[var(--color-text-primary)]">General usage limits</h2>
      <div className="space-y-4">
        <div className="rounded-lg border border-[var(--color-border)] p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[13px] text-[var(--color-text-primary)]">5 hour usage limit</div>
              <div className="mt-0.5 text-[12px] text-[var(--color-text-tertiary)]">Resets 06:10</div>
            </div>
            <div className="text-right">
              <div className="text-[13px] text-[var(--color-text-primary)]">Remaining</div>
              <div className="text-[13px] text-[var(--color-text-primary)]">68%</div>
            </div>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-elevated)]">
            <div className="h-full w-[68%] rounded-full bg-[var(--blue-300)]" />
          </div>
        </div>
        <div className="rounded-lg border border-[var(--color-border)] p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[13px] text-[var(--color-text-primary)]">Weekly usage limit</div>
              <div className="mt-0.5 text-[12px] text-[var(--color-text-tertiary)]">Resets Apr 13</div>
            </div>
            <div className="text-right">
              <div className="text-[13px] text-[var(--color-text-primary)]">Remaining</div>
              <div className="text-[13px] text-[var(--color-text-primary)]">90%</div>
            </div>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-elevated)]">
            <div className="h-full w-[90%] rounded-full bg-[var(--blue-300)]" />
          </div>
        </div>
      </div>
    </div>
  );
}

function MCPSettings() {
  const servers = [
    { name: "figma", enabled: true },
    { name: "search-server", enabled: true },
    { name: "magic21st", enabled: true },
    { name: "configured-tools", enabled: true },
    { name: "chrome-devtools", enabled: true },
  ];

  return (
    <div>
      <SectionTitle title="MCP Servers" subtitle="Connect external tools and data sources." />
      <div className="mb-3 flex justify-end">
        <button className="flex items-center gap-1.5 text-[13px] text-[var(--color-text-accent)]">
          <span>+</span> Add server
        </button>
      </div>
      <h2 className="mb-2 text-[14px] font-medium text-[var(--color-text-primary)]">Custom servers</h2>
      <div className="rounded-lg border border-[var(--color-border)]">
        {servers.map((server, i) => (
          <div
            key={server.name}
            className={`flex items-center justify-between px-4 py-3 ${i > 0 ? "border-t border-[var(--color-border)]" : ""}`}
          >
            <span className="text-[13px] text-[var(--color-text-primary)]">{server.name}</span>
            <div className="flex items-center gap-3">
              <button className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M8 1v2M8 13v2M1 8h2M13 8h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
              </button>
              <Toggle checked={server.enabled} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GitSettings() {
  return (
    <div>
      <SectionTitle title="Git" />
      <SettingRow label="Branch prefix" description="Prefix used when Codex creates new branches.">
        <input type="text" value="codex/" className="w-24 rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-2 py-1 text-[13px] text-[var(--color-text-primary)] outline-none" />
      </SettingRow>
      <SettingRow label="Pull request merge method" description="Choose how Codex merges pull requests">
        <div className="flex gap-2">
          <button className="rounded-md border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] px-3 py-1 text-[12px] text-[var(--color-text-primary)]">Merge</button>
          <button className="rounded-md border border-[var(--color-border)] px-3 py-1 text-[12px] text-[var(--color-text-tertiary)]">Squash</button>
        </div>
      </SettingRow>
      <SettingRow label="Show PR icons in sidebar" description="Display PR status icons on thread items in the sidebar">
        <Toggle checked={true} />
      </SettingRow>
      <SettingRow label="Always force-push changes" description="Use --force-with-lease when Codex pushes changes.">
        <Toggle checked={true} />
      </SettingRow>
      <SettingRow label="Create draft pull requests" description="Use draft pull requests by default when creating PRs from Codex">
        <Toggle checked={true} />
      </SettingRow>
      <div className="my-6 border-t border-[var(--color-border)]" />
      <h2 className="mb-2 text-[14px] font-medium text-[var(--color-text-primary)]">Commit message instructions</h2>
      <textarea
        placeholder="Add guidance for writing commit messages..."
        className="h-24 w-full rounded-lg border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] p-3 text-[13px] text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-border-focus)]"
      />
      <div className="mt-6">
        <h2 className="mb-2 text-[14px] font-medium text-[var(--color-text-primary)]">Pull request instructions</h2>
        <textarea
          placeholder="Add guidance for creating pull requests..."
          className="h-24 w-full rounded-lg border border-[var(--color-border-heavy)] bg-[var(--color-bg-elevated)] p-3 text-[13px] text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-border-focus)]"
        />
      </div>
    </div>
  );
}

function PlaceholderSection({ title }: { title: string }) {
  return (
    <div>
      <SectionTitle title={title} />
      <div className="rounded-lg border border-[var(--color-border)] p-8 text-center text-[13px] text-[var(--color-text-tertiary)]">
        This section will be available soon.
      </div>
    </div>
  );
}
