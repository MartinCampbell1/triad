import { useState } from "react";
import { DiagnosticsPanel } from "../shared/DiagnosticsPanel";

export function SidebarFooter() {
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);

  return (
    <footer className="mt-auto border-t border-border-light bg-[rgba(0,0,0,0.12)] px-3 py-3">
      <DiagnosticsPanel open={diagnosticsOpen} />
      <button
        type="button"
        onClick={() => setDiagnosticsOpen((open) => !open)}
        className="mb-1.5 flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-[13px] text-text-secondary transition-colors hover:bg-elevated-secondary hover:text-text-primary"
      >
        <span className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-full border border-border-light bg-elevated text-[11px] text-text-secondary">
            i
          </span>
          <span>
            <span className="block text-[13px]">System diagnostics</span>
            <span className="block text-[11px] text-text-tertiary">
              {diagnosticsOpen ? "Скрыть runtime state" : "Показать runtime state"}
            </span>
          </span>
        </span>
        <span className="text-text-tertiary">{diagnosticsOpen ? "−" : "+"}</span>
      </button>
      <button className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left text-[13px] text-text-secondary transition-colors hover:bg-elevated-secondary hover:text-text-primary">
        <span className="flex items-center gap-2">
          <span className="h-7 w-7 rounded-full bg-elevated text-center text-[11px] leading-7 text-text-primary">
            M
          </span>
          <span>
            <span className="block text-[13px]">martin</span>
            <span className="block text-[11px] text-text-tertiary">Настройки</span>
          </span>
        </span>
        <span className="text-text-tertiary">⚙</span>
      </button>
    </footer>
  );
}
