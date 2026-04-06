import type { Message, StreamingRun } from "../../lib/types";

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
  return normalized.length > max ? `${normalized.slice(0, max - 1).trimEnd()}...` : normalized;
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
  const toolEvents = messages.filter((message) => message.content.startsWith("!tool:")).length;
  const findings = messages.filter((message) => message.content.startsWith("!finding:")).length;
  const systemMessages = messages.filter(
    (message) =>
      message.role === "system" &&
      !message.content.startsWith("!tool:") &&
      !message.content.startsWith("!finding:")
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

export function TranscriptOverview({ overview, onJump }: Props) {
  return (
    <div className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] px-3 py-2">
      <div className="flex items-center gap-3 text-[12px] text-text-tertiary">
        <span>{overview.totalMessages} msgs</span>
        <span>{overview.userTurns} turns</span>
        {overview.toolEvents > 0 ? <span>{overview.toolEvents} tools</span> : null}
        {overview.liveRuns > 0 ? <span className="text-[#339cff]">{overview.liveRuns} live</span> : null}
      </div>

      {overview.anchors.length > 1 ? (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {overview.anchors.map((anchor) => (
            <button
              key={anchor.messageId}
              type="button"
              onClick={() => onJump(anchor.messageId)}
              className="rounded-md px-2 py-0.5 text-[11px] text-text-tertiary transition-colors hover:bg-white/[0.04] hover:text-text-secondary"
              title={anchor.label}
            >
              {`#${anchor.turn} ${anchor.label}`}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
