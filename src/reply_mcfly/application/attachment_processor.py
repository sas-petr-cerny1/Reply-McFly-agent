from __future__ import annotations

import io
import wave
from dataclasses import dataclass

from reply_mcfly.domain.email import EmailAttachment, WorkflowError

MAX_ATTACHMENT_COUNT = 5
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024

_SUPPORTED_DECLARED = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
    }
)
_WAV_DECLARED = frozenset({"audio/wav", "audio/x-wav"})


@dataclass(frozen=True)
class ValidatedAttachment:
    source_id: str
    filename: str
    mime_type: str
    data: bytes


def _detect_mime(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    return None


def _canonical_declared(mime: str) -> str:
    if mime in _WAV_DECLARED:
        return "audio/wav"
    return mime


def _validate_pdf(data: bytes) -> None:
    if len(data) < 8 or not data.startswith(b"%PDF-"):
        raise WorkflowError("ATTACHMENT_INVALID")


def _validate_png(data: bytes) -> None:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise WorkflowError("ATTACHMENT_INVALID")


def _validate_jpeg(data: bytes) -> None:
    if len(data) < 4:
        raise WorkflowError("ATTACHMENT_INVALID")


def _validate_wav(data: bytes) -> None:
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            if handle.getnframes() <= 0:
                raise WorkflowError("ATTACHMENT_INVALID")
    except (EOFError, wave.Error):
        raise WorkflowError("ATTACHMENT_INVALID") from None


def _validate_mp3(data: bytes) -> None:
    if len(data) < 4:
        raise WorkflowError("ATTACHMENT_INVALID")


def validate_attachments(
    attachments: tuple[EmailAttachment, ...],
) -> tuple[ValidatedAttachment, ...]:
    if len(attachments) > MAX_ATTACHMENT_COUNT:
        raise WorkflowError("ATTACHMENT_LIMIT_EXCEEDED")
    total = sum(len(item.data) for item in attachments)
    if total > MAX_TOTAL_BYTES:
        raise WorkflowError("ATTACHMENT_LIMIT_EXCEEDED")
    validated: list[ValidatedAttachment] = []
    for item in attachments:
        if not item.data:
            raise WorkflowError("ATTACHMENT_INVALID")
        declared = _canonical_declared(item.declared_mime.casefold())
        if declared not in _SUPPORTED_DECLARED:
            raise WorkflowError("UNSUPPORTED_ATTACHMENT")
        detected = _detect_mime(item.data)
        if detected is None:
            raise WorkflowError("ATTACHMENT_INVALID")
        if declared != detected:
            raise WorkflowError("ATTACHMENT_INVALID")
        limit = {
            "application/pdf": MAX_PDF_BYTES,
            "image/jpeg": MAX_IMAGE_BYTES,
            "image/png": MAX_IMAGE_BYTES,
            "audio/wav": MAX_AUDIO_BYTES,
            "audio/mpeg": MAX_AUDIO_BYTES,
        }[detected]
        if len(item.data) > limit:
            raise WorkflowError("ATTACHMENT_LIMIT_EXCEEDED")
        if detected == "application/pdf":
            _validate_pdf(item.data)
        elif detected == "image/png":
            _validate_png(item.data)
        elif detected == "image/jpeg":
            _validate_jpeg(item.data)
        elif detected == "audio/wav":
            _validate_wav(item.data)
        else:
            _validate_mp3(item.data)
        validated.append(
            ValidatedAttachment(item.source_id, item.filename, detected, item.data),
        )
    return tuple(validated)
