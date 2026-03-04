"""Layout-aware PDF to Markdown extraction using Docling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from docshield.config import DEFAULT_OCR_LANGUAGES

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger("docshield.engine.extractor")


def _build_converter(
    ocr_languages: Sequence[str] = DEFAULT_OCR_LANGUAGES,
):
    """Build a ``DocumentConverter`` with optimised pipeline options."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        PdfPipelineOptions,
        TableStructureOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True,
    )
    pipeline_options.ocr_options = EasyOcrOptions(lang=list(ocr_languages))
    pipeline_options.images_scale = 2.0
    pipeline_options.generate_picture_images = False

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
        },
    )


class DocumentExtractor:
    """Convert PDFs to layout-preserving Markdown via Docling."""

    def __init__(
        self,
        ocr_languages: Sequence[str] = DEFAULT_OCR_LANGUAGES,
    ) -> None:
        try:
            self._converter = _build_converter(ocr_languages)
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Run: pip install -r requirements.txt"
            ) from exc

        logger.debug(
            "DocumentExtractor initialised (OCR langs=%s)", list(ocr_languages),
        )

    def pdf_to_markdown(self, file_path: Path) -> str:
        logger.info("Extracting %s", file_path.name)
        result = self._converter.convert(file_path)
        md = result.document.export_to_markdown()
        logger.debug("Extracted %d chars from %s", len(md), file_path.name)
        return md
