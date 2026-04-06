import type { ReviewFinding } from "../../lib/types";

interface Props {
  finding: ReviewFinding;
}

const severityColor: Record<ReviewFinding["severity"], string> = {
  P0: "text-red-300",
  P1: "text-orange-300",
  P2: "text-yellow-300",
  P3: "text-text-tertiary",
};

export function FindingCard({ finding }: Props) {
  return (
    <div className="py-1.5">
      <div className="flex items-center gap-2 text-[12px]">
        <span className={severityColor[finding.severity]}>{finding.severity}</span>
        <span className="text-text-tertiary">{finding.file}</span>
      </div>
      <div className="mt-1 text-[13px] text-text-primary">{finding.title}</div>
      <div className="mt-0.5 text-[12px] leading-[1.5] text-text-secondary">{finding.explanation}</div>
      {finding.line_range ? <div className="mt-1 text-[11px] text-text-tertiary">{finding.line_range}</div> : null}
    </div>
  );
}
