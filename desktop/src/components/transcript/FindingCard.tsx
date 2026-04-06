import type { ReviewFinding } from "../../lib/types";

interface Props {
  finding: ReviewFinding;
}

const severityTone: Record<ReviewFinding["severity"], string> = {
  P0: "border-red-400/40 text-red-300",
  P1: "border-orange-400/40 text-orange-300",
  P2: "border-yellow-300/40 text-yellow-300",
  P3: "border-white/15 text-text-secondary",
};

export function FindingCard({ finding }: Props) {
  return (
    <div className="rounded-[18px] border border-border-default bg-[rgba(255,255,255,0.025)] px-4 py-3">
      <div className="mb-2 flex items-center gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-[11px] ${severityTone[finding.severity]}`}>
          {finding.severity}
        </span>
        <span className="text-[11px] uppercase tracking-[0.12em] text-text-tertiary">{finding.file}</span>
      </div>
      <div className="text-[13px] font-medium text-text-primary">{finding.title}</div>
      <div className="mt-1 text-[12px] leading-[1.6] text-text-secondary">{finding.explanation}</div>
      {finding.line_range ? <div className="mt-2 text-[11px] text-text-tertiary">{finding.line_range}</div> : null}
    </div>
  );
}
