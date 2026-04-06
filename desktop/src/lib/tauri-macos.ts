import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";

const NOTIFICATION_PROMPT_KEY = "triad.desktop.notifications.prompted.v1";

function isTruthyWindow() {
  return typeof window !== "undefined";
}

export async function ensureMacOSNotificationPermissionPromptOnce() {
  if (!isTruthyWindow()) {
    return;
  }

  try {
    if (window.localStorage.getItem(NOTIFICATION_PROMPT_KEY) === "1") {
      return;
    }

    let shouldPersistPromptState = false;
    const granted = await isPermissionGranted();
    shouldPersistPromptState = true;
    if (!granted) {
      await requestPermission();
      shouldPersistPromptState = true;
    }

    if (shouldPersistPromptState) {
      try {
        window.localStorage.setItem(NOTIFICATION_PROMPT_KEY, "1");
      } catch {
        // Ignore localStorage failures.
      }
    }
  } catch {
    // Permission prompting is best-effort on desktop.
  }
}

export async function notifyMacOSRunOutcome(params: {
  title: string;
  outcome: "completed" | "failed";
  provider?: string;
  error?: string;
}) {
  if (!isTruthyWindow()) {
    return;
  }

  try {
    let granted = await isPermissionGranted();
    if (!granted) {
      const permission = await requestPermission();
      granted = permission === "granted";
    }

    if (!granted) {
      return;
    }

    sendNotification({
      title: params.outcome === "failed" ? `Triad: ${params.title}` : `Triad: ${params.title}`,
      body:
        params.outcome === "failed"
          ? params.error || "The current run failed."
          : params.provider
            ? `${params.provider} finished the current run.`
            : "The current run finished successfully.",
    });
  } catch {
    // Notifications are best-effort on desktop.
  }
}

export async function setMacOSDockBadgeLabel(label?: string) {
  if (!isTruthyWindow()) {
    return;
  }

  try {
    await getCurrentWindow().setBadgeLabel(label);
  } catch {
    // Dock badging is best-effort and macOS-only.
  }
}
