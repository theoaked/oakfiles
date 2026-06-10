"""Testes do streaming de ZIP."""

import io
import sys
import zipfile
from pathlib import Path

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from app.core.zip_stream import zip_folder_stream, total_size  # noqa: E402


def _build_tree(base: Path) -> dict:
    """Cria uma árvore com vários arquivos, incluindo um maior que o chunk."""
    files = {
        "a.txt": b"hello oakfiles",
        "sub/b.bin": bytes(range(256)) * 64,
        "sub/deep/c.dat": b"x" * (3 * 1024 * 1024),  # > _CHUNK_SIZE (1 MB)
        "empty.txt": b"",
    }
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return files


def test_zip_stream_produces_valid_archive(tmp_path):
    files = _build_tree(tmp_path)

    data = b"".join(zip_folder_stream(tmp_path))
    zf = zipfile.ZipFile(io.BytesIO(data))

    # ZIP íntegro: CRCs e diretório central corretos
    assert zf.testzip() is None

    names = set(zf.namelist())
    expected = {rel.replace("\\", "/") for rel in files}
    assert {n.replace("\\", "/") for n in names} == expected

    for rel, content in files.items():
        member = rel.replace("/", "\\") if rel.replace("/", "\\") in names else rel
        assert zf.read(member) == content


def test_zip_stream_yields_incrementally(tmp_path):
    _build_tree(tmp_path)
    chunks = list(zip_folder_stream(tmp_path))
    # Vários chunks (não um blob único no final) e nenhum chunk gigante:
    # garante que arquivos grandes não são bufferizados inteiros em memória
    assert len(chunks) > 3
    assert max(len(c) for c in chunks) <= 2 * 1024 * 1024


def test_total_size(tmp_path):
    files = _build_tree(tmp_path)
    assert total_size(tmp_path) == sum(len(c) for c in files.values())
