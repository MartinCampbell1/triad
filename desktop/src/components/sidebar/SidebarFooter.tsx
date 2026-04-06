export function SidebarFooter() {
  return (
    <footer className="border-t border-[rgba(255,255,255,0.06)] px-3 py-2">
      <button className="flex w-full items-center gap-3 rounded-lg px-3 py-[7px] text-left text-[13px] text-text-secondary transition-colors hover:bg-white/[0.04] hover:text-text-primary">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-text-tertiary">
          <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.2" />
          <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
        <span>Настройки</span>
      </button>
    </footer>
  );
}
