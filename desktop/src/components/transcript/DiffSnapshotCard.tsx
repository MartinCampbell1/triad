import { useMemo } from "react";
import { parseStructuredDiffPatch } from "../../lib/diff";
import { FileChangeSummary } from "./FileChangeSummary";

interface Props {
  patch: string;
}

export function DiffSnapshotCard({ patch }: Props) {
  const files = useMemo(
    () =>
      parseStructuredDiffPatch(patch).map((file) => ({
        path: file.path,
        additions: file.additions,
        deletions: file.deletions,
      })),
    [patch]
  );

  return <FileChangeSummary files={files} />;
}
