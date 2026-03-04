"""Configuration defaults and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL_ID = "urchade/gliner_multi-v2.1"

DEFAULT_OCR_LANGUAGES: list[str] = ["de", "en"]
DEFAULT_MIN_CONFIDENCE: float = 0.4

DEFAULT_LABELS: list[str] = [
    "person name",
    "company name",
    "bank name",
    "email address",
    "physical address",
    "internal project code",
    "custom ID number",
    "insurance number",
    "financial value",
    "phone number",
    "date of birth",
]


DEFAULT_CUSTOM_TERMS_FILE = "data/custom_terms.txt"


@dataclass(frozen=True)
class PipelineConfig:
    input_dir: Path = field(default_factory=lambda: Path("input"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    mapping_dir: Path = field(default_factory=lambda: Path("mapping"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    llm_responses_dir: Path = field(default_factory=lambda: Path("llm_responses"))
    model_id: str = DEFAULT_MODEL_ID
    labels: list[str] = field(default_factory=lambda: list(DEFAULT_LABELS))
    ocr_languages: list[str] = field(
        default_factory=lambda: list(DEFAULT_OCR_LANGUAGES),
    )
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    custom_terms_file: Path | None = field(
        default_factory=lambda: Path(DEFAULT_CUSTOM_TERMS_FILE),
    )
    verbose: bool = False
