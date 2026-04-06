import { useEffect } from "react";
import { useUiStore } from "../stores/ui-store";

interface ShortcutHandlers {
  openCommandPalette: () => void;
  stopCurrentRun?: () => void;
}

export function useKeyboardShortcuts({ openCommandPalette, stopCurrentRun }: ShortcutHandlers) {
  const toggleDrawer = useUiStore((state) => state.toggleDrawer);
  const toggleDiffPanel = useUiStore((state) => state.toggleDiffPanel);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const meta = event.metaKey || event.ctrlKey;
      if (!meta) {
        return;
      }

      const target = event.target as HTMLElement | null;
      const editable =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable === true;

      if (event.key.toLowerCase() === "k") {
        event.preventDefault();
        openCommandPalette();
        return;
      }

      if (event.key === "`") {
        event.preventDefault();
        toggleDrawer();
        return;
      }

      if (event.shiftKey && event.key.toLowerCase() === "d") {
        event.preventDefault();
        toggleDiffPanel();
        return;
      }

      if (event.key.toLowerCase() === "b" && !editable) {
        event.preventDefault();
        toggleSidebar();
        return;
      }

      if (event.key === "." && stopCurrentRun) {
        event.preventDefault();
        stopCurrentRun();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openCommandPalette, stopCurrentRun, toggleDiffPanel, toggleDrawer, toggleSidebar]);
}
