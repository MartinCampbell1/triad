export type DiffLineKind = "context" | "add" | "remove";
export type DiffFileStatus = "added" | "modified" | "deleted" | "renamed";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
  oldLineNumber?: number;
  newLineNumber?: number;
}

export interface DiffHunk {
  id: string;
  header: string;
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

export interface StructuredDiffFile {
  path: string;
  status: DiffFileStatus;
  oldPath?: string;
  oldContent: string;
  newContent: string;
  additions: number;
  deletions: number;
  hunks: DiffHunk[];
  patch: string;
}

export interface StructuredDiffSelectionSummary {
  totalFiles: number;
  totalHunks: number;
  selectedFiles: number;
  selectedHunks: number;
  partialFiles: number;
}

export interface RawDiffFile {
  path: string;
  oldContent: string;
  newContent: string;
  oldPath?: string;
}

interface ParsedDiffFile {
  path: string;
  oldPath?: string;
  status: DiffFileStatus;
  hunks: DiffHunk[];
  additions: number;
  deletions: number;
  patchLines: string[];
}

interface InternalDiffLine extends DiffLine {
  oldConsumed: number;
  newConsumed: number;
}

function splitLines(value: string) {
  if (!value) {
    return [] as string[];
  }
  return value.split("\n");
}

function buildLcsTable(oldLines: string[], newLines: string[]) {
  const rows = oldLines.length + 1;
  const cols = newLines.length + 1;
  const table = Array.from({ length: rows }, () => Array<number>(cols).fill(0));

  for (let oldIndex = oldLines.length - 1; oldIndex >= 0; oldIndex -= 1) {
    for (let newIndex = newLines.length - 1; newIndex >= 0; newIndex -= 1) {
      if (oldLines[oldIndex] === newLines[newIndex]) {
        table[oldIndex][newIndex] = table[oldIndex + 1][newIndex + 1] + 1;
      } else {
        table[oldIndex][newIndex] = Math.max(
          table[oldIndex + 1][newIndex],
          table[oldIndex][newIndex + 1]
        );
      }
    }
  }

  return table;
}

function buildDiffLines(oldContent: string, newContent: string) {
  const oldLines = splitLines(oldContent);
  const newLines = splitLines(newContent);
  const table = buildLcsTable(oldLines, newLines);
  const lines: InternalDiffLine[] = [];

  let oldIndex = 0;
  let newIndex = 0;
  let oldLineNumber = 1;
  let newLineNumber = 1;
  let additions = 0;
  let deletions = 0;

  while (oldIndex < oldLines.length || newIndex < newLines.length) {
    if (
      oldIndex < oldLines.length &&
      newIndex < newLines.length &&
      oldLines[oldIndex] === newLines[newIndex]
    ) {
      lines.push({
        kind: "context",
        text: oldLines[oldIndex],
        oldLineNumber,
        newLineNumber,
        oldConsumed: 1,
        newConsumed: 1,
      });
      oldIndex += 1;
      newIndex += 1;
      oldLineNumber += 1;
      newLineNumber += 1;
      continue;
    }

    const consumeAdd =
      newIndex < newLines.length &&
      (oldIndex === oldLines.length ||
        table[oldIndex][newIndex + 1] >= table[oldIndex + 1][newIndex]);

    if (consumeAdd) {
      lines.push({
        kind: "add",
        text: newLines[newIndex],
        newLineNumber,
        oldConsumed: 0,
        newConsumed: 1,
      });
      additions += 1;
      newIndex += 1;
      newLineNumber += 1;
      continue;
    }

    lines.push({
      kind: "remove",
      text: oldLines[oldIndex],
      oldLineNumber,
      oldConsumed: 1,
      newConsumed: 0,
    });
    deletions += 1;
    oldIndex += 1;
    oldLineNumber += 1;
  }

  return { lines, additions, deletions };
}

function buildHunks(lines: InternalDiffLine[], status: DiffFileStatus, context = 3): DiffHunk[] {
  const changeIndexes = lines.flatMap((line, index) => (line.kind === "context" ? [] : [index]));
  if (changeIndexes.length === 0) {
    return [];
  }

  const prefixOld = Array<number>(lines.length + 1).fill(0);
  const prefixNew = Array<number>(lines.length + 1).fill(0);
  for (let index = 0; index < lines.length; index += 1) {
    prefixOld[index + 1] = prefixOld[index] + lines[index].oldConsumed;
    prefixNew[index + 1] = prefixNew[index] + lines[index].newConsumed;
  }

  const ranges: Array<{ start: number; end: number }> = [];
  for (const changeIndex of changeIndexes) {
    const start = Math.max(0, changeIndex - context);
    const end = Math.min(lines.length, changeIndex + context + 1);
    const current = ranges.at(-1);
    if (!current || start > current.end) {
      ranges.push({ start, end });
      continue;
    }
    current.end = Math.max(current.end, end);
  }

  return ranges.map((range, index) => {
    const hunkLines = lines.slice(range.start, range.end).map(({ oldConsumed, newConsumed, ...line }) => line);
    const oldLines = hunkLines.filter((line) => line.kind !== "add").length;
    const newLines = hunkLines.filter((line) => line.kind !== "remove").length;
    const oldStart = oldLines === 0 ? prefixOld[range.start] : prefixOld[range.start] + 1;
    const newStart = newLines === 0 ? prefixNew[range.start] : prefixNew[range.start] + 1;
    const normalizedOldStart = status === "added" && oldLines === 0 ? 0 : oldStart;
    const normalizedNewStart = status === "deleted" && newLines === 0 ? 0 : newStart;
    return {
      id: `hunk-${index + 1}`,
      header: `@@ -${normalizedOldStart},${oldLines} +${normalizedNewStart},${newLines} @@`,
      oldStart: normalizedOldStart,
      oldLines,
      newStart: normalizedNewStart,
      newLines,
      lines: hunkLines,
    };
  });
}

function buildPatchPreamble(
  path: string,
  status: DiffFileStatus,
  oldPath: string | undefined,
  sourcePatch?: string
) {
  if (sourcePatch?.trim()) {
    const sourceLines = sourcePatch.split("\n");
    const hunkIndex = sourceLines.findIndex((line) => line.startsWith("@@ "));
    if (hunkIndex > 0) {
      return sourceLines.slice(0, hunkIndex);
    }
  }

  const previousPath = oldPath ?? path;
  const diffHeader = `diff --git a/${previousPath} b/${path}`;
  const fromPath = status === "added" ? "/dev/null" : `a/${previousPath}`;
  const toPath = status === "deleted" ? "/dev/null" : `b/${path}`;

  if (status === "added") {
    return [diffHeader, "new file mode 100644", `--- ${fromPath}`, `+++ ${toPath}`];
  }

  if (status === "deleted") {
    return [diffHeader, "deleted file mode 100644", `--- ${fromPath}`, `+++ ${toPath}`];
  }

  if (status === "renamed" && oldPath && oldPath !== path) {
    return [diffHeader, `rename from ${oldPath}`, `rename to ${path}`, `--- ${fromPath}`, `+++ ${toPath}`];
  }

  return [diffHeader, `--- ${fromPath}`, `+++ ${toPath}`];
}

function buildPatch(path: string, status: DiffFileStatus, oldPath: string | undefined, hunks: DiffHunk[]) {
  const lines = buildPatchPreamble(path, status, oldPath);

  for (const hunk of hunks) {
    lines.push(hunk.header);
    for (const line of hunk.lines) {
      const prefix = line.kind === "add" ? "+" : line.kind === "remove" ? "-" : " ";
      lines.push(`${prefix}${line.text}`);
    }
  }

  return lines.join("\n");
}

function buildPatchForSelectedHunks(file: StructuredDiffFile, hunks: DiffHunk[]) {
  const lines = buildPatchPreamble(file.path, file.status, file.oldPath, file.patch);

  for (const hunk of hunks) {
    lines.push(hunk.header);
    for (const line of hunk.lines) {
      const prefix = line.kind === "add" ? "+" : line.kind === "remove" ? "-" : " ";
      lines.push(`${prefix}${line.text}`);
    }
  }

  return lines.join("\n");
}

function resolveStatus(oldContent: string, newContent: string): DiffFileStatus {
  if (!oldContent && newContent) {
    return "added";
  }
  if (oldContent && !newContent) {
    return "deleted";
  }
  return "modified";
}

export function buildStructuredDiffFile(file: RawDiffFile): StructuredDiffFile {
  const status = resolveStatus(file.oldContent, file.newContent);
  const { lines, additions, deletions } = buildDiffLines(file.oldContent, file.newContent);
  const hunks = buildHunks(lines, status);
  return {
    path: file.path,
    oldPath: file.oldPath,
    status,
    oldContent: file.oldContent,
    newContent: file.newContent,
    additions,
    deletions,
    hunks,
    patch: buildPatch(file.path, status, file.oldPath, hunks),
  };
}

export function diffHunkSelectionKey(filePath: string, hunkId: string) {
  return `${filePath}::${hunkId}`;
}

export function summarizeStructuredDiffSelection(
  files: StructuredDiffFile[],
  selectedHunkKeys: readonly string[] = []
): StructuredDiffSelectionSummary {
  const selectedSet = new Set(selectedHunkKeys);
  let totalHunks = 0;
  let selectedHunks = 0;
  let selectedFiles = 0;
  let partialFiles = 0;

  for (const file of files) {
    if (file.hunks.length === 0) {
      continue;
    }

    totalHunks += file.hunks.length;
    const fileSelectedCount = file.hunks.filter((hunk) => selectedSet.has(diffHunkSelectionKey(file.path, hunk.id))).length;
    selectedHunks += fileSelectedCount;
    if (fileSelectedCount === 0) {
      continue;
    }

    if (fileSelectedCount === file.hunks.length) {
      selectedFiles += 1;
    } else {
      partialFiles += 1;
    }
  }

  return {
    totalFiles: files.length,
    totalHunks,
    selectedFiles,
    selectedHunks,
    partialFiles,
  };
}

export function composeStructuredDiffPatch(
  files: StructuredDiffFile[],
  selectedHunkKeys: readonly string[] = []
): string {
  const selectedSet = new Set(selectedHunkKeys);
  if (selectedSet.size === 0) {
    return files.map((file) => file.patch).filter(Boolean).join("\n\n");
  }

  const patches: string[] = [];
  for (const file of files) {
    if (file.hunks.length === 0) {
      continue;
    }

    const selectedHunks = file.hunks.filter((hunk) => selectedSet.has(diffHunkSelectionKey(file.path, hunk.id)));
    if (selectedHunks.length === 0) {
      continue;
    }

    if (selectedHunks.length === file.hunks.length) {
      patches.push(file.patch);
      continue;
    }

    patches.push(buildPatchForSelectedHunks(file, selectedHunks));
  }

  return patches.join("\n\n");
}

function parseDiffPath(line: string) {
  if (line === "/dev/null") {
    return undefined;
  }
  return line.replace(/^[ab]\//, "");
}

function parseHunkHeader(header: string) {
  const match = header.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/);
  if (!match) {
    return null;
  }
  return {
    oldStart: Number(match[1]),
    oldLines: Number(match[2] ?? "1"),
    newStart: Number(match[3]),
    newLines: Number(match[4] ?? "1"),
  };
}

function finalizeParsedFile(file: ParsedDiffFile | null) {
  if (!file || !file.path) {
    return null;
  }

  return {
    path: file.path,
    oldPath: file.oldPath,
    status: file.status,
    oldContent: "",
    newContent: "",
    additions: file.additions,
    deletions: file.deletions,
    hunks: file.hunks,
    patch: file.patchLines.join("\n"),
  } satisfies StructuredDiffFile;
}

export function parseStructuredDiffPatch(patch: string): StructuredDiffFile[] {
  if (!patch.trim()) {
    return [];
  }

  const results: StructuredDiffFile[] = [];
  const lines = patch.split("\n");
  let current: ParsedDiffFile | null = null;
  let currentHunk: DiffHunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  const pushCurrent = () => {
    const finalized = finalizeParsedFile(current);
    if (finalized) {
      results.push(finalized);
    }
    current = null;
    currentHunk = null;
    oldLine = 0;
    newLine = 0;
  };

  for (const line of lines) {
    if (line.startsWith("diff --git ")) {
      pushCurrent();
      const match = line.match(/^diff --git a\/(.+?) b\/(.+)$/);
      current = {
        path: match?.[2] ?? "",
        oldPath: match?.[1],
        status: "modified",
        hunks: [],
        additions: 0,
        deletions: 0,
        patchLines: [],
      };
    }

    if (!current && line.startsWith("--- ")) {
      current = {
        path: "",
        oldPath: parseDiffPath(line.slice(4)),
        status: "modified",
        hunks: [],
        additions: 0,
        deletions: 0,
        patchLines: [],
      };
    }

    if (current) {
      current.patchLines.push(line);
    }

    if (!current) {
      continue;
    }

    if (line.startsWith("new file mode ")) {
      current.status = "added";
      continue;
    }

    if (line.startsWith("deleted file mode ")) {
      current.status = "deleted";
      continue;
    }

    if (line.startsWith("rename from ")) {
      current.status = "renamed";
      current.oldPath = line.slice("rename from ".length);
      continue;
    }

    if (line.startsWith("rename to ")) {
      current.status = "renamed";
      current.path = line.slice("rename to ".length);
      continue;
    }

    if (line.startsWith("--- ")) {
      current.oldPath = parseDiffPath(line.slice(4)) ?? current.oldPath;
      continue;
    }

    if (line.startsWith("+++ ")) {
      current.path = parseDiffPath(line.slice(4)) ?? current.path;
      continue;
    }

    if (line.startsWith("@@ ")) {
      const parsed = parseHunkHeader(line);
      if (!parsed) {
        currentHunk = null;
        continue;
      }
      currentHunk = {
        id: `hunk-${current.hunks.length + 1}`,
        header: line,
        oldStart: parsed.oldStart,
        oldLines: parsed.oldLines,
        newStart: parsed.newStart,
        newLines: parsed.newLines,
        lines: [],
      };
      current.hunks.push(currentHunk);
      oldLine = parsed.oldStart;
      newLine = parsed.newStart;
      continue;
    }

    if (!currentHunk) {
      continue;
    }

    if (line.startsWith("\\ No newline at end of file")) {
      continue;
    }

    const marker = line[0];
    const text = line.slice(1);
    if (marker === " ") {
      currentHunk.lines.push({
        kind: "context",
        text,
        oldLineNumber: oldLine,
        newLineNumber: newLine,
      });
      oldLine += 1;
      newLine += 1;
      continue;
    }

    if (marker === "+") {
      currentHunk.lines.push({
        kind: "add",
        text,
        newLineNumber: newLine,
      });
      current.additions += 1;
      newLine += 1;
      continue;
    }

    if (marker === "-") {
      currentHunk.lines.push({
        kind: "remove",
        text,
        oldLineNumber: oldLine,
      });
      current.deletions += 1;
      oldLine += 1;
    }
  }

  pushCurrent();
  return results;
}
