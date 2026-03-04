"""Zero-shot contextual PII sanitizer powered by GLiNER + regex patterns."""

from __future__ import annotations

import logging
import os
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from docshield.config import DEFAULT_LABELS, DEFAULT_MIN_CONFIDENCE, DEFAULT_MODEL_ID
from docshield.engine.blocklist import NOT_A_PROPER_NAME, is_blocked
from docshield.engine.patterns import detect_patterns

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger("docshield.engine.sanitizer")

_FLAG_RE = re.compile(r"\[[A-Z_]+_FLAG_\d+\]")

# Consistency-scan constraints: only propagate tokens that genuinely
# look like personal/family names, not common words.
_MIN_NAME_TOKEN_LEN = 4
_MAX_SOURCE_ENTITY_WORDS = 4

# Generic abbreviations that appear inside company names but should NOT
# be propagated as standalone entity tokens (legal forms, technical terms).
_GENERIC_ABBREVIATIONS: frozenset[str] = frozenset({
    "AG", "SE", "KG", "OHG", "EV",
    "GMBH", "CO", "INC", "LTD", "LLC", "PLC", "LP",
    "CERT", "SOC", "NOC", "BSI", "TUV", "ISO",
    "IT", "HR", "QA", "QM", "EU", "US", "UK", "DE",
})

# Vault validation: reject entries that look like garbled OCR output.
_VOWELS = set("aeiouAEIOUäöüÄÖÜ")
_MIN_VOWEL_RATIO = 0.15


class IntelligentSanitizer:
    """Three-pass PII sanitizer with confidence filtering and vault validation.

    Pass 1 -- GLiNER predicts entities per chunk (names, companies, ...).
              Results are filtered by confidence threshold + blocklists.
    Pass 2 -- Deterministic regex patterns catch structured data that the
              model typically misses (IBANs, BICs, emails, amounts, ...).
    Pass 3 -- Consistency scan: finds remaining plain-text occurrences of
              tokens from already-detected *person names only*, using
              strict proper-name heuristics to avoid false propagation.
    """

    def __init__(
        self,
        labels: Iterable[str] | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        chunk_separator: str = "\n\n",
        custom_terms: list[tuple[str, str]] | None = None,
    ) -> None:
        try:
            from gliner import GLiNER
        except ImportError as exc:
            raise RuntimeError(
                "GLiNER is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self._suppress_library_warnings()

        local_path = self._resolve_cached_model(model_id)
        self._model = GLiNER.from_pretrained(local_path)
        self._chunk_separator = chunk_separator
        self._min_confidence = min_confidence
        self._custom_terms = custom_terms or []
        self.labels = list(labels or DEFAULT_LABELS)
        logger.debug(
            "Loaded GLiNER model %s (confidence >= %.2f, labels=%s, custom_terms=%d)",
            model_id, min_confidence, self.labels, len(self._custom_terms),
        )

    @staticmethod
    def _resolve_cached_model(model_id: str) -> str:
        """Return local snapshot path if model is already cached, else *model_id*.

        When GLiNER receives a local directory path it skips
        ``huggingface_hub.snapshot_download`` entirely -- no network calls,
        no tqdm/multiprocessing locks, and instant startup.
        """
        if Path(model_id).exists():
            return model_id

        try:
            from huggingface_hub import scan_cache_dir
            for repo in scan_cache_dir().repos:
                if repo.repo_id == model_id:
                    revisions = sorted(
                        repo.revisions,
                        key=lambda r: r.last_modified,
                        reverse=True,
                    )
                    if revisions:
                        snap = str(revisions[0].snapshot_path)
                        logger.info("Using cached model: %s", snap)
                        return snap
        except Exception:  # noqa: BLE001
            pass

        return model_id

    @staticmethod
    def _suppress_library_warnings() -> None:
        """Suppress known non-actionable warnings from third-party ML libraries.

        Also disables HuggingFace progress bars and tokenizer parallelism to
        prevent multiprocessing lock issues when running inside threads
        (e.g. Textual worker threads on Python 3.14+).
        """
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

        warnings.filterwarnings(
            "ignore", message=r".*resume_download.*deprecated.*", category=FutureWarning,
        )
        warnings.filterwarnings(
            "ignore", message=r".*sentencepiece.*byte fallback.*", category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore", message=r".*Sentence of length \d+ has been truncated.*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore", message=r".*Asking to truncate to max_length.*",
        )
        warnings.filterwarnings(
            "ignore", message=r".*pin_memory.*no accelerator.*", category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore", message=r".*Cannot close object.*pdfium.*",
        )
        logging.getLogger("transformers").setLevel(logging.ERROR)

    def _apply_custom_terms(
        self,
        text: str,
        entity_key_to_flag: dict[tuple[str, str], str],
        flag_to_entity: dict[str, str],
        label_counters: dict[str, int],
    ) -> str:
        """Pass 0: replace user-defined custom terms (longest-first, literal)."""
        result = text
        for term, label in self._custom_terms:
            if term not in result:
                continue
            dedup_key = (term, label)
            if dedup_key not in entity_key_to_flag:
                label_counters[label] = label_counters.get(label, 0) + 1
                flag = f"[{label}_FLAG_{label_counters[label]}]"
                entity_key_to_flag[dedup_key] = flag
                flag_to_entity[flag] = term
            else:
                flag = entity_key_to_flag[dedup_key]
            result = result.replace(term, flag)
        return result

    @staticmethod
    def _normalize_label(label: str) -> str:
        safe = label.upper().replace(" ", "_")
        return "".join(ch for ch in safe if ch.isalnum() or ch == "_")

    def _apply_replacements(
        self,
        text: str,
        entities: list[dict[str, object]],
        entity_key_to_flag: dict[tuple[str, str], str],
        flag_to_entity: dict[str, str],
        label_counters: dict[str, int],
    ) -> str:
        """Replace entity spans from right to left, updating lookup dicts."""
        clean = text
        for entity in entities:
            original = str(entity["text"])
            label = self._normalize_label(str(entity["label"]))
            dedup_key = (original, label)

            if dedup_key not in entity_key_to_flag:
                label_counters[label] = label_counters.get(label, 0) + 1
                flag = f"[{label}_FLAG_{label_counters[label]}]"
                entity_key_to_flag[dedup_key] = flag
                flag_to_entity[flag] = original
            else:
                flag = entity_key_to_flag[dedup_key]

            start = int(entity["start"])
            end = int(entity["end"])
            clean = clean[:start] + flag + clean[end:]
        return clean

    def _filter_by_confidence(
        self,
        entities: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Remove entities below the confidence threshold."""
        kept: list[dict[str, object]] = []
        for ent in entities:
            score = float(ent.get("score", 1.0))
            if score < self._min_confidence:
                logger.debug(
                    "Below confidence (%.2f): '%s' as %s",
                    score, ent.get("text"), ent.get("label"),
                )
                continue
            kept.append(ent)
        return kept

    @staticmethod
    def _filter_blocked(
        entities: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Remove entities that match entity-type blocklists."""
        kept: list[dict[str, object]] = []
        for ent in entities:
            label = IntelligentSanitizer._normalize_label(str(ent["label"]))
            if is_blocked(str(ent["text"]), label):
                logger.debug(
                    "Blocked false positive: '%s' as %s", ent["text"], label,
                )
                continue
            kept.append(ent)
        return kept

    def sanitize(self, text: str) -> tuple[str, dict[str, str]]:
        """Replace detected entities with flag tokens.

        Returns ``(sanitized_text, flag_to_entity)`` for vault storage.
        """
        chunks = text.split(self._chunk_separator)
        clean_chunks: list[str] = []
        entity_key_to_flag: dict[tuple[str, str], str] = {}
        flag_to_entity: dict[str, str] = {}
        label_counters: dict[str, int] = {}

        for chunk in chunks:
            if not chunk.strip():
                clean_chunks.append(chunk)
                continue

            # -- Pass 0: user-defined custom terms (literal, longest-first) --
            if self._custom_terms:
                chunk = self._apply_custom_terms(
                    chunk, entity_key_to_flag, flag_to_entity, label_counters,
                )

            # -- Pass 1: GLiNER + confidence filter + blocklist filter --
            gliner_entities = self._model.predict_entities(chunk, self.labels)
            after_confidence = self._filter_by_confidence(gliner_entities)
            filtered = self._filter_blocked(after_confidence)
            gliner_sorted = sorted(
                filtered, key=lambda e: e["start"], reverse=True,
            )

            clean_chunk = self._apply_replacements(
                chunk, gliner_sorted,
                entity_key_to_flag, flag_to_entity, label_counters,
            )

            # -- Pass 2: regex patterns on the *already-cleaned* chunk --
            regex_matches = detect_patterns(clean_chunk)
            regex_entities = [
                {
                    "text": m.text, "label": m.label,
                    "start": m.start, "end": m.end,
                }
                for m in regex_matches
                if not self._inside_flag(clean_chunk, m.start, m.end)
            ]
            if regex_entities:
                clean_chunk = self._apply_replacements(
                    clean_chunk, regex_entities,
                    entity_key_to_flag, flag_to_entity, label_counters,
                )

            clean_chunks.append(clean_chunk)

        joined = self._chunk_separator.join(clean_chunks)

        # -- Pass 3: consistency scan for genuine name tokens only --
        joined = self._consistency_scan(
            joined, entity_key_to_flag, flag_to_entity, label_counters,
        )

        # -- Post-pass: vault validation --
        flag_to_entity = self._validate_vault(
            flag_to_entity, entity_key_to_flag,
        )

        total = len(flag_to_entity)
        logger.info("Sanitized text: %d unique entities masked", total)
        return joined, flag_to_entity

    # ------------------------------------------------------------------
    # Pass 3 helpers -- Consistency scan (restricted)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_likely_proper_name(token: str) -> bool:
        """Strict heuristic: a token looks like a proper *personal* name.

        Must be: capitalized, alphabetic, >= 4 chars, and NOT in the
        comprehensive ``NOT_A_PROPER_NAME`` dictionary.
        """
        if len(token) < _MIN_NAME_TOKEN_LEN:
            return False
        if not token[0].isupper():
            return False
        if not token.isalpha():
            return False
        return token not in NOT_A_PROPER_NAME

    @staticmethod
    def _collect_propagation_tokens(
        flag_to_entity: dict[str, str],
    ) -> dict[str, str]:
        """Extract tokens from detected entities to propagate across the document.

        Person names: extract individual surname tokens from multi-word
        entities, skipping tokens that are also COMPANY_NAME values.

        Company names: extract distinctive tokens.  For all-uppercase
        abbreviations (e.g. "VW", "PAG") the length and blocklist
        restrictions are relaxed because these are *confirmed* entity
        components, not speculative detections.
        """
        company_values: set[str] = set()
        for flag, value in flag_to_entity.items():
            if "COMPANY_NAME" in flag or "BANK_NAME" in flag:
                for word in re.split(r"[\s\-]+", value):
                    company_values.add(word)

        tokens: dict[str, str] = {}

        for flag, value in flag_to_entity.items():
            if "PERSON_NAME" in flag:
                words = value.split()
                if len(words) < 2 or len(words) > _MAX_SOURCE_ENTITY_WORDS:
                    continue
                for tok in words:
                    if tok in company_values:
                        continue
                    if (
                        tok not in tokens
                        and IntelligentSanitizer._is_likely_proper_name(tok)
                    ):
                        tokens[tok] = "PERSON_NAME"

            elif "COMPANY_NAME" in flag:
                for tok in re.split(r"[\s\-]+", value):
                    if tok in tokens or not tok:
                        continue
                    is_abbreviation = (
                        tok.isupper()
                        and len(tok) >= 2
                        and tok.upper() not in _GENERIC_ABBREVIATIONS
                    )
                    is_proper = (
                        len(tok) >= _MIN_NAME_TOKEN_LEN
                        and tok[0].isupper()
                        and tok.isalpha()
                        and tok not in NOT_A_PROPER_NAME
                    )
                    if is_abbreviation or is_proper:
                        tokens[tok] = "COMPANY_NAME"

        return tokens

    def _consistency_scan(
        self,
        text: str,
        entity_key_to_flag: dict[tuple[str, str], str],
        flag_to_entity: dict[str, str],
        label_counters: dict[str, int],
    ) -> str:
        """Find remaining plain-text occurrences of detected entity tokens.

        Phase 1 -- propagate *all* confirmed vault entity values (full text,
                   regardless of length or blocklist status).  Longest first
                   to avoid partial overlap.  Also matches entities as
                   prefixes of German compound words.

        Phase 2 -- token-level propagation for individual surname tokens
                   extracted from multi-word PERSON_NAME entities (existing
                   strict heuristic).
        """
        # ---- Phase 1: confirmed entity propagation ----
        text = self._propagate_confirmed_entities(
            text, entity_key_to_flag, flag_to_entity,
        )

        # ---- Phase 2: token-level name propagation ----
        tokens = self._collect_propagation_tokens(flag_to_entity)
        if not tokens:
            return text

        parts = _FLAG_RE.split(text)
        flags = _FLAG_RE.findall(text)

        for token in sorted(tokens, key=len, reverse=True):
            label = tokens[token]
            dedup_key = (token, label)

            if dedup_key not in entity_key_to_flag:
                label_counters[label] = label_counters.get(label, 0) + 1
                flag = f"[{label}_FLAG_{label_counters[label]}]"
                entity_key_to_flag[dedup_key] = flag
                flag_to_entity[flag] = token
            else:
                flag = entity_key_to_flag[dedup_key]

            pattern = re.compile(r"(?<!\w)" + re.escape(token) + r"(?!\w)")
            parts = [pattern.sub(flag, part) for part in parts]

        result: list[str] = []
        for idx, part in enumerate(parts):
            result.append(part)
            if idx < len(flags):
                result.append(flags[idx])
        return "".join(result)

    @staticmethod
    def _propagate_confirmed_entities(
        text: str,
        entity_key_to_flag: dict[tuple[str, str], str],
        flag_to_entity: dict[str, str],
    ) -> str:
        """Replace remaining occurrences of confirmed vault entities.

        Unlike token-level propagation this has NO length or blocklist
        restrictions -- the entities were already confirmed by GLiNER or
        custom terms.  For COMPANY_NAME/PERSON_NAME entities this also
        matches as a prefix of German compound words (e.g. "Porsche" inside
        "Porschespezifisch").
        """
        compound_labels = {"COMPANY_NAME", "PERSON_NAME", "BANK_NAME"}
        entries = sorted(
            entity_key_to_flag.items(), key=lambda x: len(x[0][0]), reverse=True,
        )

        parts = _FLAG_RE.split(text)
        flags = _FLAG_RE.findall(text)

        for (value, label), flag in entries:
            if len(value) < 2 or _FLAG_RE.match(value):
                continue

            is_single_word = " " not in value.strip()
            if is_single_word and label in compound_labels:
                pattern = re.compile(
                    r"(?<!\w)" + re.escape(value) + r"(?:\w+)?",
                )
            else:
                pattern = re.compile(
                    r"(?<!\w)" + re.escape(value) + r"(?!\w)",
                )

            parts = [pattern.sub(flag, part) for part in parts]

        result: list[str] = []
        for idx, part in enumerate(parts):
            result.append(part)
            if idx < len(flags):
                result.append(flags[idx])
        return "".join(result)

    # ------------------------------------------------------------------
    # Vault validation
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_garbled(text: str) -> bool:
        """Heuristic: text is likely garbled OCR output."""
        stripped = text.strip()
        if len(stripped) < 3:
            return False
        alpha_chars = [c for c in stripped if c.isalpha()]
        if not alpha_chars:
            return False
        vowel_count = sum(1 for c in alpha_chars if c in _VOWELS)
        vowel_ratio = vowel_count / len(alpha_chars)
        return vowel_ratio < _MIN_VOWEL_RATIO

    @staticmethod
    def _validate_vault(
        flag_to_entity: dict[str, str],
        entity_key_to_flag: dict[tuple[str, str], str],
    ) -> dict[str, str]:
        """Remove vault entries that are garbled OCR or trivial."""
        cleaned: dict[str, str] = {}
        for flag, value in flag_to_entity.items():
            if IntelligentSanitizer._looks_garbled(value):
                logger.debug("Vault reject (garbled): %s -> '%s'", flag, value)
                continue
            cleaned[flag] = value
        return cleaned

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _inside_flag(text: str, start: int, end: int) -> bool:
        """Return True if [start:end] is inside an existing [*_FLAG_*] token."""
        bracket_open = text.rfind("[", 0, start + 1)
        if bracket_open == -1:
            return False
        bracket_close = text.find("]", bracket_open)
        if bracket_close == -1:
            return False
        flag_candidate = text[bracket_open : bracket_close + 1]
        return "_FLAG_" in flag_candidate and bracket_close >= end


DataSanitizer = IntelligentSanitizer
