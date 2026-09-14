"""下载、校验并构建 Phase 7A 使用的官方 TLUSTY 208 H/He 可执行文件。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.error import URLError
from urllib.request import Request, urlopen


PACKAGE_URL = "https://www.as.arizona.edu/~hubeny/tlusty208-package/tl208-s54.tar.gz"
PACKAGE_SHA256 = "ec9febdc1795f2c1bbe948ea1736bed663aac9238b290483b517201132f85e4a"

BASIC_DIMENSIONS = {
    "MION": 20,
    "MLEVEL": 150,
    "MLVEXP": 150,
    "MTRANS": 2500,
    "MDEPTH": 70,
    "MFREQ": 15000,
    "MFREQP": 20000,
    "MFREQC": 1500,
    "MFREX": 125,
    "MFREQL": 1800,
    "MVOIGT": 200,
    "MFRTAB": 3,
    "MTABT": 3,
    "MTABR": 3,
}

ODF_DIMENSIONS = {"MKULEV": 2, "MLINE": 2, "MCFE": 2}


def _download_verified_archive(destination: Path, attempts: int = 3) -> str:
    """下载官方包并逐次核对固定哈希；错误内容绝不进入构建目录。"""
    if attempts < 1:
        raise ValueError("attempts must be positive")
    observed_hashes: list[str] = []
    download_errors: list[str] = []
    for attempt in range(1, attempts + 1):
        request = Request(
            PACKAGE_URL,
            headers={
                "User-Agent": "eccentric-tde-observer-phase7a/1.0",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urlopen(request, timeout=120) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output)
        except (URLError, TimeoutError, ConnectionError) as error:
            if destination.exists():
                destination.unlink()
            download_errors.append(f"attempt {attempt}: {error}")
            continue
        actual_hash = _sha256(destination)
        if actual_hash == PACKAGE_SHA256:
            return actual_hash
        observed_hashes.append(actual_hash)
        destination.unlink()
    joined_hashes = ", ".join(observed_hashes) or "none"
    joined_errors = "; ".join(download_errors) or "none"
    raise RuntimeError(
        f"TLUSTY archive hash mismatch after {attempts} attempts: "
        f"expected {PACKAGE_SHA256}; observed hashes {joined_hashes}; "
        f"download errors {joined_errors}"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_extract(archive: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle.getmembers():
            member_path = (destination / member.name).resolve()
            if destination_resolved not in member_path.parents and member_path != destination_resolved:
                raise RuntimeError(f"archive member escapes destination: {member.name}")
        # 已先验证固定哈希及成员路径；保留官方包中的符号链接元数据。
        handle.extractall(destination, filter="fully_trusted")


def _replace_integer_parameter(text: str, name: str, value: int) -> str:
    # 固定格式 Fortran 的注释行从第 1 列以 C/c 开始；只改活动参数行。
    pattern = rf"(?m)^([ \t]+[^\n]*\b{re.escape(name)}\s*=\s*)\d+"
    updated, count = re.subn(pattern, rf"\g<1>{value}", text)
    if count != 1:
        raise RuntimeError(f"expected one {name} parameter, found {count}")
    return updated


def _patch_dimensions(path: Path, replacements: dict[str, int]) -> None:
    text = path.read_text()
    for name, value in replacements.items():
        text = _replace_integer_parameter(text, name, value)
    path.write_text(text)


def build(
    destination: Path,
    fortran_compiler: str,
    archive_path: Path | None = None,
) -> dict[str, object]:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which(fortran_compiler)
    if compiler is None:
        raise FileNotFoundError(f"Fortran compiler not found: {fortran_compiler}")

    with tempfile.TemporaryDirectory(prefix="tlusty208-download-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "tl208-s54.tar.gz"
        if archive_path is None:
            actual_hash = _download_verified_archive(archive)
            archive_source = PACKAGE_URL
        else:
            archive_path = archive_path.resolve()
            if not archive_path.is_file():
                raise FileNotFoundError(archive_path)
            actual_hash = _sha256(archive_path)
            if actual_hash != PACKAGE_SHA256:
                raise RuntimeError(
                    f"TLUSTY archive hash mismatch: expected {PACKAGE_SHA256}, "
                    f"got {actual_hash}"
                )
            shutil.copyfile(archive_path, archive)
            archive_source = str(archive_path)
        extracted = temporary_path / "extracted"
        extracted.mkdir()
        _safe_extract(archive, extracted)
        roots = [path for path in extracted.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("TLUSTY archive must contain exactly one top-level directory")
        source_root = destination / "source"
        # 官方包含指向可选大分子线表的断链；H/He 构建不使用它们。
        shutil.copytree(roots[0], source_root, symlinks=True)

    # 中文：只缩小静态数组上限以适配 H/He 连续谱；不改 TLUSTY 物理方程。
    _patch_dimensions(source_root / "tlusty" / "BASICS.FOR", BASIC_DIMENSIONS)
    _patch_dimensions(source_root / "tlusty" / "ODFPAR.FOR", ODF_DIMENSIONS)
    binary_directory = destination / "bin"
    binary_directory.mkdir()
    executable = binary_directory / "tlusty208_hhe"
    command = [
        compiler,
        "-O2",
        "-fno-automatic",
        "-std=legacy",
        "-fallow-argument-mismatch",
        "-w",
        "-o",
        str(executable),
        "tlusty208.f",
    ]
    completed = subprocess.run(
        command,
        cwd=source_root / "tlusty",
        text=True,
        capture_output=True,
        check=False,
    )
    (destination / "compile.stdout.txt").write_text(completed.stdout)
    (destination / "compile.stderr.txt").write_text(completed.stderr)
    if completed.returncode != 0 or not executable.is_file():
        raise RuntimeError(f"TLUSTY compilation failed; retained {destination}")

    manifest = {
        "package_url": PACKAGE_URL,
        "package_sha256": actual_hash,
        "archive_source": archive_source,
        "compiler": compiler,
        "compiler_flags": command[1:-3],
        "basic_dimensions": BASIC_DIMENSIONS,
        "odf_dimensions": ODF_DIMENSIONS,
        "executable": str(executable),
        "atomic_data_directory": str(source_root / "data"),
        "source_physics_modified": False,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--fortran-compiler", default="gfortran")
    parser.add_argument(
        "--archive",
        type=Path,
        help="可选的官方包本地副本；仍会强制核对固定 SHA-256",
    )
    arguments = parser.parse_args()
    print(
        json.dumps(
            build(
                arguments.destination,
                arguments.fortran_compiler,
                arguments.archive,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
