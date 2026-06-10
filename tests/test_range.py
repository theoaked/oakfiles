"""Testes do parser de HTTP Range em /api/download."""

import sys
from pathlib import Path

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from app.api.fs_routes import parse_range_header  # noqa: E402

SIZE = 1000


def test_no_header_serves_full_file():
    assert parse_range_header(None, SIZE) is None
    assert parse_range_header("", SIZE) is None


def test_invalid_headers_fall_back_to_full_file():
    assert parse_range_header("bytes=abc", SIZE) is None
    assert parse_range_header("items=0-99", SIZE) is None
    assert parse_range_header("bytes=-", SIZE) is None
    # Multi-range não suportado: serve o arquivo inteiro
    assert parse_range_header("bytes=0-99,200-299", SIZE) is None


def test_open_ended_range():
    assert parse_range_header("bytes=0-", SIZE) == (0, SIZE - 1)
    assert parse_range_header("bytes=500-", SIZE) == (500, SIZE - 1)


def test_bounded_range():
    assert parse_range_header("bytes=0-99", SIZE) == (0, 99)
    assert parse_range_header("bytes=200-299", SIZE) == (200, 299)


def test_end_clamped_to_file_size():
    assert parse_range_header("bytes=900-5000", SIZE) == (900, SIZE - 1)


def test_suffix_range():
    assert parse_range_header("bytes=-100", SIZE) == (SIZE - 100, SIZE - 1)
    # Sufixo maior que o arquivo devolve o arquivo todo
    assert parse_range_header("bytes=-5000", SIZE) == (0, SIZE - 1)


def test_unsatisfiable_ranges():
    assert parse_range_header("bytes=1000-", SIZE) == "unsatisfiable"
    assert parse_range_header("bytes=2000-2100", SIZE) == "unsatisfiable"
    assert parse_range_header("bytes=-0", SIZE) == "unsatisfiable"
    assert parse_range_header("bytes=0-", 0) == "unsatisfiable"
