from __future__ import annotations

import base64
import binascii
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any


def materialize_attachments(
    raw_attachments: Any,
    *,
    project_path: str,
    artifacts_dir: Path,
    session_id: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw_attachments, list):
        return []

    attachments: list[dict[str, Any]] = []
    target_dir = (artifacts_dir / "desktop-attachments" / session_id).resolve()
    for index, item in enumerate(raw_attachments, start=1):
        if not isinstance(item, dict):
            continue

        attachment_id = str(item.get("id") or f"att_{uuid.uuid4().hex[:10]}")
        source = str(item.get("source") or "picker")
        name = str(item.get("name") or "").strip()
        mime_type = str(item.get("mime_type") or item.get("mimeType") or "").strip() or None
        kind = str(item.get("kind") or "").strip() or None
        size_bytes = _coerce_int(item.get("size_bytes") or item.get("sizeBytes"))

        raw_path = str(item.get("path") or "").strip()
        if raw_path:
            path = _resolve_attachment_path(raw_path, project_path)
            if not path.is_file():
                raise ValueError(f"Attachment does not exist: {raw_path}")
            resolved_name = name or path.name or f"attachment-{index}"
            resolved_mime = mime_type or mimetypes.guess_type(str(path))[0]
            resolved_kind = kind or _infer_attachment_kind(resolved_name, resolved_mime)
            attachments.append(
                {
                    "id": attachment_id,
                    "name": resolved_name,
                    "path": str(path),
                    "kind": resolved_kind,
                    "mime_type": resolved_mime,
                    "size_bytes": size_bytes or path.stat().st_size,
                    "source": source,
                }
            )
            continue

        content_base64 = str(item.get("content_base64") or item.get("contentBase64") or "").strip()
        if not content_base64:
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        resolved_name = name or f"attachment-{index}{_guess_extension(mime_type)}"
        target_path = target_dir / f"{index:02d}-{_slugify_name(resolved_name)}"
        try:
            payload = base64.b64decode(content_base64, validate=False)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"Invalid attachment payload for {resolved_name}") from exc
        target_path.write_bytes(payload)
        attachments.append(
            {
                "id": attachment_id,
                "name": resolved_name,
                "path": str(target_path.resolve()),
                "kind": kind or _infer_attachment_kind(resolved_name, mime_type),
                "mime_type": mime_type,
                "size_bytes": size_bytes or len(payload),
                "source": source,
            }
        )

    return attachments


def format_attachments_for_prompt(attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return ""

    lines = ["Attached context:"]
    for attachment in attachments:
        name = str(attachment.get("name") or "attachment")
        path = str(attachment.get("path") or "").strip()
        kind = str(attachment.get("kind") or "file")
        mime_type = str(attachment.get("mime_type") or "").strip()
        suffix = f" [{mime_type}]" if mime_type else ""
        if path:
            lines.append(f"- {name} ({kind}) at {path}{suffix}")
        else:
            lines.append(f"- {name} ({kind}){suffix}")
    lines.append("Use these files as supporting context and inspect them from disk as needed.")
    return "\n".join(lines)


def summarize_attachment_names(attachments: list[dict[str, Any]]) -> str:
    names = [str(attachment.get("name") or "").strip() for attachment in attachments]
    names = [name for name in names if name]
    if not names:
        return "attachments"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]}, {names[1]}, and {len(names) - 2} more"


def _resolve_attachment_path(raw_path: str, project_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    return Path(project_path).joinpath(path).resolve()


def _infer_attachment_kind(name: str, mime_type: str | None) -> str:
    if (mime_type or "").startswith("image/"):
        return "image"
    suffix = Path(name).suffix.lower()
    return "image" if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"} else "file"


def _guess_extension(mime_type: str | None) -> str:
    if not mime_type:
        return ""
    return mimetypes.guess_extension(mime_type) or ""


def _slugify_name(name: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-")
    return stem or "attachment"


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
