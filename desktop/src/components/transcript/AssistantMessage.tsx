import { lazy, Suspense } from "react";
import type { Message } from "../../lib/types";
import { Badge } from "../shared/Badge";

interface Props {
  message: Message;
}

const Markdown = lazy(async () => {
  const module = await import("./Markdown");
  return { default: module.Markdown };
});

function providerGlyph(provider?: string) {
  if (provider === "codex") return "C";
  if (provider === "gemini") return "G";
  return "◆";
}

function providerLabel(provider?: string) {
  if (provider === "codex") return "Codex";
  if (provider === "gemini") return "Gemini";
  if (provider === "claude") return "Claude";
  return provider ?? "Claude";
}

function providerTone(provider?: string): "neutral" | "subtle" | "accent" {
  if (provider === "codex") return "accent";
  return "neutral";
}

export function AssistantMessage({ message }: Props) {
  return (
    <div className="codex-message-enter-subtle rounded-[18px] border border-border-light bg-[linear-gradient(180deg,rgba(255,255,255,0.03),transparent),rgba(255,255,255,0.015)] px-4 py-3 shadow-glow transition-[transform,box-shadow,border-color,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-border-default hover:shadow-[0_0_0_1px_rgba(255,255,255,0.05),0_24px_48px_rgba(0,0,0,0.24)]">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <Badge tone={providerTone(message.provider)} leading={providerGlyph(message.provider)}>
          {providerLabel(message.provider)}
        </Badge>
        {message.agent_role ? (
          <Badge tone="subtle" className="capitalize">
            {message.agent_role}
          </Badge>
        ) : null}
      </div>
      <div className="text-[13px] leading-[1.65] text-text-primary motion-safe:[&_pre]:transition-[background-color,border-color]">
        <Suspense fallback={<div className="whitespace-pre-wrap leading-[1.65] text-text-primary">{message.content}</div>}>
          <Markdown content={message.content} />
        </Suspense>
      </div>
    </div>
  );
}
