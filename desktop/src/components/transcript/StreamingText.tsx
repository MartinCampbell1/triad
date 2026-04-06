import { Badge } from "../shared/Badge";

interface Props {
  text: string;
  provider?: string | null;
  role?: string | null;
}

function providerGlyph(provider?: string | null) {
  if (provider === "codex") return "C";
  if (provider === "gemini") return "G";
  return "◆";
}

function providerLabel(provider?: string | null) {
  if (provider === "codex") return "Codex";
  if (provider === "gemini") return "Gemini";
  if (provider === "claude") return "Claude";
  return provider ?? "Claude";
}

function providerTone(provider?: string | null): "neutral" | "subtle" | "accent" {
  if (provider === "codex") return "accent";
  return "neutral";
}

export function StreamingText({ text, provider, role }: Props) {
  if (!text.trim()) {
    return null;
  }

  return (
    <div className="codex-message-enter rounded-[18px] border border-border-default bg-[rgba(255,255,255,0.03)] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-[transform,box-shadow,border-color,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-border-heavy hover:bg-[rgba(255,255,255,0.04)]">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <Badge tone={providerTone(provider)} leading={providerGlyph(provider)}>
          {providerLabel(provider)}
        </Badge>
        {role ? (
          <Badge tone="subtle" className="capitalize">
            {role}
          </Badge>
        ) : null}
      </div>
      <div className="whitespace-pre-wrap text-[13px] leading-[1.6] text-text-primary">
        {text}
        <span className="codex-streaming-caret ml-0.5 inline-block h-4 w-0.5 rounded-full bg-accent align-text-bottom" />
      </div>
    </div>
  );
}
