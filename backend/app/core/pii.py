from __future__ import annotations

import logging
import re

_EMAIL_RE = re.compile(
    r"(?i)\b([A-Z0-9._%+-])([A-Z0-9._%+-]*)@([A-Z0-9.-]+\.[A-Z]{2,})\b"
)
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6})(\d{8})(\d{3}[\dXx])(?!\d)")
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{4})(\d{8,11})(\d{4})(?!\d)")
_LANDLINE_RE = re.compile(r"(?<!\d)(0\d{2,3})-?(\d{4})(\d{4})(?!\d)")
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
_ORDER_NO_RE = re.compile(r"\b(QH)(\d{4})\d+(\d{3})\b", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+")
_API_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b")


def _mask_email(match: re.Match[str]) -> str:
    return f"{match.group(1)}***@{match.group(3)}"


def _mask_id_card(match: re.Match[str]) -> str:
    return f"{match.group(1)}********{match.group(3)}"


def _mask_bank_card(match: re.Match[str]) -> str:
    return f"{match.group(1)}{'*' * len(match.group(2))}{match.group(3)}"


def _mask_landline(match: re.Match[str]) -> str:
    return f"{match.group(1)}-****{match.group(3)}"


def _mask_phone(match: re.Match[str]) -> str:
    return f"{match.group(1)}****{match.group(3)}"


def redact_pii(text: str) -> str:
    """Mask common personal identifiers while preserving enough context."""
    if not text:
        return text
    redacted = _EMAIL_RE.sub(_mask_email, text)
    redacted = _ID_CARD_RE.sub(_mask_id_card, redacted)
    redacted = _BANK_CARD_RE.sub(_mask_bank_card, redacted)
    redacted = _LANDLINE_RE.sub(_mask_landline, redacted)
    redacted = _PHONE_RE.sub(_mask_phone, redacted)
    return redacted


def redact_log_text(text: str) -> str:
    redacted = redact_pii(text)
    redacted = _ORDER_NO_RE.sub(r"\1\2****\3", redacted)
    redacted = _BEARER_RE.sub(r"\1 ***", redacted)
    redacted = _API_KEY_RE.sub("sk-***", redacted)
    return redacted


class PIIRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted = redact_log_text(message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        except Exception:
            # Logging must never break request handling because of redaction.
            pass
        return True
