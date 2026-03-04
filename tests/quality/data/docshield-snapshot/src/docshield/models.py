"""Data models for DocShield pipeline results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunResult:
    document_name: str
    output_file: str
    pii_count: int
    status: str
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "success"
