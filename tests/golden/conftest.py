"""Shared fixtures and helpers for the golden codebase test suite."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from axon.core.ingestion.pipeline import run_pipeline
from axon.core.storage.kuzu_backend import KuzuBackend

GOLDEN_CODEBASE = Path(__file__).parent / "codebase"
EXPECTED_DIR = Path(__file__).parent / "expected"

# Tables to search when looking up a symbol by file+name
_SYMBOL_TABLES = ["Function", "Method", "Class", "Interface", "TypeAlias", "Enum"]


# ---------------------------------------------------------------------------
# Pipeline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def golden_codebase_path() -> Path:
    return GOLDEN_CODEBASE


@pytest.fixture(scope="session")
def golden_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # mktemp creates the dir; KuzuDB needs a non-existent path to initialize into
    return tmp_path_factory.mktemp("golden") / "kuzu_db"


@pytest.fixture(scope="session")
def golden_storage(
    golden_codebase_path: Path, golden_db_path: Path
) -> KuzuBackend:
    """Index the golden codebase once per test session."""
    backend = KuzuBackend()
    backend.initialize(golden_db_path)
    run_pipeline(golden_codebase_path, backend)
    yield backend
    backend.close()


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------


def load_expected(filename: str) -> dict[str, Any]:
    path = EXPECTED_DIR / filename
    with path.open() as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Graph query helpers
# ---------------------------------------------------------------------------


def get_symbol_node_id(storage: KuzuBackend, file_path: str, name: str) -> str | None:
    """Return the node ID for a symbol given file path and symbol name.

    Handles two naming conventions:
    - Plain functions/classes: name='validate_token' -> queries n.name
    - Methods: name='AuthService.authenticate' -> queries n.class_name + n.name
      (Axon stores methods as name='authenticate', class_name='AuthService')
    """
    if "." in name:
        # Method: split into class_name + plain method name
        class_name, _, method_name = name.rpartition(".")
        rows = storage.execute_raw(
            f"MATCH (n:Method) "
            f"WHERE n.file_path = '{file_path}' "
            f"AND n.class_name = '{class_name}' "
            f"AND n.name = '{method_name}' "
            f"RETURN n.id LIMIT 1"
        )
        if rows:
            return rows[0][0]
        return None

    for table in _SYMBOL_TABLES:
        rows = storage.execute_raw(
            f"MATCH (n:{table}) "
            f"WHERE n.file_path = '{file_path}' AND n.name = '{name}' "
            f"RETURN n.id LIMIT 1"
        )
        if rows:
            return rows[0][0]
    return None


def symbol_exists(storage: KuzuBackend, file_path: str, name: str) -> bool:
    return get_symbol_node_id(storage, file_path, name) is not None


def call_edge_exists(
    storage: KuzuBackend, source_file: str, source_name: str, target_file: str, target_name: str
) -> bool:
    """Return True if a CALLS edge exists from source to target."""
    source_id = get_symbol_node_id(storage, source_file, source_name)
    target_id = get_symbol_node_id(storage, target_file, target_name)
    if source_id is None or target_id is None:
        return False
    callees = storage.get_callees(source_id)
    return any(n.id == target_id for n in callees)


def parse_edge_ref(ref: str) -> tuple[str, str]:
    """Parse 'python/auth/service.py::validate_token' into (file_path, name)."""
    file_part, _, name_part = ref.partition("::")
    return file_part, name_part
