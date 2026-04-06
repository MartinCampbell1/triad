import { useUiStore } from "../../stores/ui-store";

export function SidebarFooter() {
  const setSettingsOpen = useUiStore((state) => state.setSettingsOpen);

  return (
    <footer className="border-t border-[var(--color-border)] px-2 py-1.5">
      <button
        onClick={() => setSettingsOpen(true)}
        className="flex w-full items-center gap-3 rounded-lg px-3 py-[6px] text-left text-[12px] text-[var(--color-text-secondary)] transition-colors duration-150 hover:bg-[rgba(255,255,255,0.03)] hover:text-[var(--color-text-primary)]"
      >
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" className="text-[var(--color-text-tertiary)]">
          <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
          <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        <span>Settings</span>
      </button>
    </footer>
  );
}
