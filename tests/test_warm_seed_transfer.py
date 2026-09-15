"""Small byte fixtures test the same integrity and commit path as the 9.4 GiB seed."""
import hashlib
import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[1] / "handoff/fetch_warm_seed.py"
spec = importlib.util.spec_from_file_location("fetch_warm_seed", path)
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


def fixture(tmp_path):
    parts = tmp_path / "parts"
    parts.mkdir()
    chunks = [b"first-block\0\xff", b"second-block\x01"]
    rows = []
    offset = 0
    for i, chunk in enumerate(chunks):
        name = f"seed.part-{i:03d}"
        (parts / name).write_bytes(chunk)
        rows.append({"name": name, "offset_bytes": offset, "size_bytes": len(chunk),
                     "sha256": hashlib.sha256(chunk).hexdigest()})
        offset += len(chunk)
    data = b"".join(chunks)
    manifest = {"checkpoint": {"path": "outputs/checkpoints/seed.dat", "size_bytes": len(data),
                 "sha256": hashlib.sha256(data).hexdigest()}, "parts": rows}
    return parts, manifest, data


def test_assembly_verifies_bytes_and_is_idempotent(tmp_path):
    parts, manifest, data = fixture(tmp_path)
    final = transfer.assemble(tmp_path, manifest, parts)
    assert final.read_bytes() == data
    assert not final.with_name(final.name + ".github-assembling").exists()
    assert transfer.assemble(tmp_path, manifest, parts) == final


def test_corrupted_part_never_publishes_final(tmp_path):
    parts, manifest, data = fixture(tmp_path)
    part = parts / manifest["parts"][1]["name"]
    part.write_bytes(b"x" * part.stat().st_size)
    with pytest.raises(RuntimeError, match="corrupted"):
        transfer.assemble(tmp_path, manifest, parts)
    assert not (tmp_path / manifest["checkpoint"]["path"]).exists()
    # Repairing the part permits a retry after an interrupted/failed assembly.
    part.write_bytes(data[manifest["parts"][1]["offset_bytes"]:])
    assert transfer.assemble(tmp_path, manifest, parts).read_bytes() == data


def test_different_existing_checkpoint_is_not_overwritten(tmp_path):
    parts, manifest, _ = fixture(tmp_path)
    final = tmp_path / manifest["checkpoint"]["path"]
    final.parent.mkdir(parents=True)
    final.write_bytes(b"existing research data")
    with pytest.raises(RuntimeError, match="mismatch"):
        transfer.assemble(tmp_path, manifest, parts)
    assert final.read_bytes() == b"existing research data"


@pytest.mark.parametrize("mutation", ["gap", "duplicate", "traversal", "wrong_full_hash"])
def test_invalid_manifest_never_publishes_checkpoint(tmp_path, mutation):
    parts, manifest, _ = fixture(tmp_path)
    if mutation == "gap": manifest["parts"][1]["offset_bytes"] += 1
    if mutation == "duplicate": manifest["parts"][1]["name"] = manifest["parts"][0]["name"]
    if mutation == "traversal": manifest["checkpoint"]["path"] = "outputs/checkpoints/../../escape.dat"
    if mutation == "wrong_full_hash": manifest["checkpoint"]["sha256"] = "0" * 64
    with pytest.raises((ValueError, RuntimeError)):
        transfer.assemble(tmp_path, manifest, parts)
    assert not (tmp_path / "outputs/checkpoints/seed.dat").exists()
