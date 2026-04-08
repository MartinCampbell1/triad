import type { Message, StreamingRun } from "../../lib/types";
import { Badge } from "../shared/Badge";

interface TranscriptAnchor {
  messageId: string;
  label: string;
  turn: number;
}

export interface TranscriptOverviewData {
  totalMessages: number;
  userTurns: number;
  assistantMessages: number;
  toolEvents: number;
  findings: number;
  systemMessages: number;
  liveRuns: number;
  firstTopic: string | null;
  latestTopic: string | null;
  anchors: TranscriptAnchor[];
}

interface Props {
  overview: TranscriptOverviewData;
  onJump: (messageId: string) => void;
}

function compactLabel(value: string, max = 48) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "Untitled turn";
  }
  return normalized.length > max ? `${normalized.slice(0, max - 1).trimEnd()}…` : normalized;
}

function selectAnchorIndexes(total: number, maxAnchors = 6) {
  if (total <= maxAnchors) {
    return Array.from({ length: total }, (_, index) => index);
  }

  const indexes = new Set<number>([0, total - 1]);
  for (let slot = 1; slot < maxAnchors - 1; slot += 1) {
    indexes.add(Math.round((slot * (total - 1)) / (maxAnchors - 1)));
  }
  return [...indexes].sort((left, right) => left - right);
}

export function buildTranscriptOverview(
  messages: Message[],
  streamingRuns: StreamingRun[]
): TranscriptOverviewData | null {
  const userMessages = messages.filter((message) => message.role === "user");
  const assistantMessages = messages.filter((message) => message.role === "assistant");
  const toolEvents = messages.filter((message) => Boolean(message.tool_event)).length;
  const findings = messages.filter((message) => Boolean(message.review_finding)).length;
  const systemMessages = messages.filter(
    (message) =>
      message.role === "system" &&
      !message.tool_event &&
      !message.review_finding
  ).length;

  if (messages.length < 4 && userMessages.length < 2 && streamingRuns.length === 0) {
    return null;
  }

  const anchorIndexes = selectAnchorIndexes(userMessages.length);
  const anchors = anchorIndexes.map((index) => {
    const message = userMessages[index];
    return {
      messageId: message.id,
      label: compactLabel(message.content),
      turn: index + 1,
    };
  });

  return {
    totalMessages: messages.length,
    userTurns: userMessages.length,
    assistantMessages: assistantMessages.length,
    toolEvents,
    findings,
    systemMessages,
    liveRuns: streamingRuns.length,
    firstTopic: userMessages[0] ? compactLabel(userMessages[0].content, 72) : null,
    latestTopic: userMessages.at(-1) ? compactLabel(userMessages.at(-1)!.content, 72) : null,
    anchors,
  };
}

function summaryLine(overview: TranscriptOverviewData) {
  if (overview.firstTopic && overview.latestTopic && overview.firstTopic !== overview.latestTopic) {
    return `Started with "${overview.firstTopic}" and is now focused on "${overview.latestTopic}".`;
  }
  if (overview.latestTopic) {
    return `Current focus: "${overview.latestTopic}".`;
  }
  return `Session has ${overview.totalMessages} visible messages.`;
}

export function TranscriptOverview({ overview, onJump }: Props) {
  return (
    <div className="codex-message-enter-subtle rounded-[20px] border border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.02))] px-4 py-3 shadow-[0_18px_40px_rgba(0,0,0,0.18)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Session map</div>
          <div className="mt-1 text-[13px] leading-[1.6] text-text-secondary">{summaryLine(overview)}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="subtle">{`${overview.totalMessages} msgs`}</Badge>
          <Badge tone="neutral">{`${overview.userTurns} turns`}</Badge>
          <Badge tone="neutral">{`${overview.assistantMessages} replies`}</Badge>
          {overview.toolEvents > 0 ? <Badge tone="subtle">{`${overview.toolEvents} tools`}</Badge> : null}
          {overview.findings > 0 ? <Badge tone="subtle">{`${overview.findings} findings`}</Badge> : null}
          {overview.liveRuns > 0 ? <Badge tone="accent">{`${overview.liveRuns} live`}</Badge> : null}
        </div>
      </div>

      {overview.anchors.length > 1 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {overview.anchors.map((anchor) => (
            <button
              key={anchor.messageId}
              type="button"
              onClick={() => onJump(anchor.messageId)}
              className="rounded-full border border-border-light bg-black/15 px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:border-border-default hover:bg-white/5 hover:text-text-primary"
              title={anchor.label}
            >
              {`Turn ${anchor.turn}: ${anchor.label}`}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
