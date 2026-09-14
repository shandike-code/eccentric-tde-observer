"""Phase 7B9dj：用稀疏内存 sink 独立重算 block 34 两次。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Callable

import numpy as np

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9dj_memory_only_block_rerun.py"
BLOCK_INDEX = 34
SOURCE_ITERATION = 20


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if path.suffix == ".dat":
        raise RuntimeError("7B9dj source pinning refuses full-state .dat")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class MemoryOnlyBlockSink:
    """只接收目标 core slice；绝不分配或落盘整个 10 GiB 输出。"""

    expected_slice: slice
    mapped: np.ndarray | None = None
    flush_count: int = 0

    def __setitem__(self, key: object, value: object) -> None:
        if not isinstance(key, slice) or (
            key.start,
            key.stop,
            key.step,
        ) != (
            self.expected_slice.start,
            self.expected_slice.stop,
            self.expected_slice.step,
        ):
            raise RuntimeError("7B9dj memory sink received an unexpected block slice")
        if self.mapped is not None:
            raise RuntimeError("7B9dj memory sink received more than one write")
        array = np.asarray(value)
        if not np.all(np.isfinite(array)) or np.any(array < 0.0):
            raise ArithmeticError("7B9dj memory-only mapped block is invalid")
        self.mapped = np.array(array, copy=True)

    def flush(self) -> None:
        self.flush_count += 1


AttemptExecutor = Callable[
    [Path, str, Path, int, int, int], dict[str, object]
]


def _shape(protocol: dict[str, object]) -> tuple[int, int, int]:
    cfg = protocol["configuration"]
    return (
        int(cfg["physical_frequency_groups"]),
        int(cfg["angular_direction_count"]),
        int(cfg["radiation_depth_cell_count"]),
    )


def _block_sha256(
    path: Path, shape: tuple[int, int, int], start: int, stop: int
) -> str:
    array = np.memmap(path, mode="r", dtype=np.float64, shape=shape)
    digest = hashlib.sha256(np.asarray(array[start:stop]).tobytes()).hexdigest()
    del array
    return digest


def _load_di_evidence(
    root: Path,
    protocol_path: Path,
    expected_protocol_sha256: str,
    manifest_path: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if _sha256(protocol_path) != expected_protocol_sha256:
        raise RuntimeError("7B9dj frozen 7B9di protocol changed")
    protocol = _read_json(protocol_path)
    for source in protocol["sources"].values():
        path = root / source["path"]
        if (
            path.stat().st_size != int(source["size_bytes"])
            or _sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"7B9dj 7B9di source changed: {source['path']}")
    manifest = _read_json(manifest_path)
    records = manifest.get("iterations", [])
    if (
        manifest.get("protocol_sha256") != expected_protocol_sha256
        or manifest.get("status") != "gate_failed"
        or manifest.get("active_iteration") is not None
        or len(records) != 21
        or records[-1].get("iteration") != SOURCE_ITERATION
    ):
        raise RuntimeError("7B9dj iteration-20 manifest lineage changed")
    return protocol, manifest, records[-1]


def _default_attempt_executor(
    root: Path,
    protocol_path: Path,
    expected_protocol_sha256: str,
    protocol: dict[str, object],
) -> AttemptExecutor:
    generic = engine.generic

    def execute(
        input_path: Path,
        input_sha256: str,
        virtual_output_path: Path,
        block_index: int,
        core_start: int,
        core_stop: int,
    ) -> dict[str, object]:
        if virtual_output_path.exists():
            raise RuntimeError("7B9dj virtual output unexpectedly exists")
        sink = MemoryOnlyBlockSink(slice(core_start, core_stop))
        original_memmap = generic.np.memmap

        def memory_map(path: object, *args: object, **kwargs: object) -> object:
            candidate = Path(path).resolve()
            if candidate == virtual_output_path.resolve():
                return sink
            return original_memmap(path, *args, **kwargs)

        fixed = _read_json(
            root / protocol["sources"]["finite_trial_protocol"]["path"]
        )
        if (
            fixed["sources"]["current_material_state"]
            != protocol["sources"]["finite_trial_material"]
        ):
            raise RuntimeError("7B9dj fixed material source changed")
        original_loader = generic.base.phase7b9i._load_protocol
        with tempfile.TemporaryDirectory(prefix="phase7b9dj_") as temporary:
            report_path = Path(temporary) / "worker_report.json"
            try:
                generic.base.phase7b9i._load_protocol = (
                    lambda _path, validate_sources=False: fixed
                )
                generic.np.memmap = memory_map
                engine.EXPECTED_PROTOCOL_SHA256 = expected_protocol_sha256
                generic.EXPECTED_PROTOCOL_SHA256 = expected_protocol_sha256
                engine._run_worker(
                    protocol_path,
                    SOURCE_ITERATION,
                    block_index,
                    input_path,
                    input_sha256,
                    virtual_output_path,
                    report_path,
                )
                report = _read_json(report_path)
            finally:
                generic.np.memmap = original_memmap
                generic.base.phase7b9i._load_protocol = original_loader
        if virtual_output_path.exists():
            raise RuntimeError("7B9dj memory sink persisted the virtual output")
        if sink.mapped is None or sink.flush_count < 1:
            raise RuntimeError("7B9dj memory sink did not receive a complete mapped block")
        report["in_memory_rerun_block_sha256"] = hashlib.sha256(
            np.ascontiguousarray(sink.mapped).tobytes()
        ).hexdigest()
        report["output_persisted"] = False
        report["input_modified"] = False
        return report

    return execute


def run_two_memory_only_reruns(
    root: Path,
    di_protocol_path: Path,
    expected_di_protocol_sha256: str,
    di_manifest_path: Path,
    output_path: Path,
    *,
    runner_relative_path: str = RUNNER_RELATIVE_PATH,
    natural_frequency_block_width: int = 128,
    attempt_executor: AttemptExecutor | None = None,
) -> dict[str, object]:
    protocol, _, failed = _load_di_evidence(
        root,
        di_protocol_path,
        expected_di_protocol_sha256,
        di_manifest_path,
    )
    shape = _shape(protocol)
    start = BLOCK_INDEX * natural_frequency_block_width
    stop = min(start + natural_frequency_block_width, shape[0])
    if stop <= start:
        raise RuntimeError("7B9dj block 34 is outside the frequency grid")
    input_path = root / failed["input_state_path"]
    failed_output_path = root / failed["mapped_state_path"]
    if (
        _sha256(input_path) != failed["input_state_sha256"]
        or _sha256(failed_output_path) != failed["mapped_state_sha256"]
    ):
        raise RuntimeError("7B9dj A/B full-state bytes changed")
    input_before = str(failed["input_state_sha256"])
    failed_block_sha = _block_sha256(failed_output_path, shape, start, stop)
    execute = attempt_executor or _default_attempt_executor(
        root, di_protocol_path, expected_di_protocol_sha256, protocol
    )
    rows = []
    for attempt in (1, 2):
        # 中文：虚拟 output 仅作为路径标识；映射结果由稀疏内存 sink 接收。
        virtual = output_path.parent / f".virtual_block34_attempt{attempt}.dat"
        if virtual.exists():
            raise RuntimeError("7B9dj virtual output path is not clean")
        row = execute(
            input_path,
            input_before,
            virtual,
            BLOCK_INDEX,
            start,
            stop,
        )
        if virtual.exists():
            raise RuntimeError("7B9dj virtual output was persisted")
        rows.append(
            {
                "attempt": attempt,
                "block_relative_radiation_change": float(
                    row["block_relative_radiation_change"]
                ),
                "maximum_absolute_radiation_change": float(
                    row["maximum_absolute_radiation_change"]
                ),
                "maximum_radiation_scale": float(row["maximum_radiation_scale"]),
                "in_memory_rerun_block_sha256": row[
                    "in_memory_rerun_block_sha256"
                ],
                "output_persisted": False,
                "input_modified": False,
            }
        )
    mapped_hashes = [str(row["in_memory_rerun_block_sha256"]) for row in rows]
    input_after = _sha256(input_path)
    if (
        mapped_hashes[0] != mapped_hashes[1]
        or mapped_hashes[0] == failed_block_sha
        or input_after != input_before
    ):
        raise RuntimeError("7B9dj two memory-only reruns did not isolate the anomaly")
    di_runner = protocol["sources"].get("progression_continuation_runner")
    if not isinstance(di_runner, dict):
        raise RuntimeError("7B9dj 7B9di runner source pin is missing")
    summary = {
        "phase": "7B9dj iteration20 block34 memory-only reruns",
        "classification": "[V-memory-only]+[O]",
        "sources": {
            "di_protocol": _source(
                root, str(di_protocol_path.resolve().relative_to(root.resolve()))
            ),
            "di_manifest": _source(
                root, str(di_manifest_path.resolve().relative_to(root.resolve()))
            ),
            "di_progression_runner": dict(di_runner),
            "memory_only_runner": _source(root, runner_relative_path),
        },
        "source_iteration": SOURCE_ITERATION,
        "block_index": BLOCK_INDEX,
        "core_group_start": start,
        "core_group_stop": stop,
        "input_state_path": failed["input_state_path"],
        "input_state_sha256": input_before,
        "failed_output_state_path": failed["mapped_state_path"],
        "failed_output_state_sha256": failed["mapped_state_sha256"],
        "failed_persisted_block_sha256": failed_block_sha,
        "independent_memory_only_reruns": rows,
        "output_persisted": False,
        "input_modified": False,
        "decision": {
            "two_memory_only_reruns_byte_identical": True,
            "both_reruns_differ_from_failed_persisted_block": True,
            "single_block_repair_authorized": False,
            "fresh_full_76_block_reproduction_required": True,
        },
    }
    _write_json_atomic(output_path, summary)
    return summary


def main(argv: list[str] | None = None, *, root: Path | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--di-protocol", required=True)
    parser.add_argument("--expected-di-protocol-sha256", required=True)
    parser.add_argument("--di-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--natural-frequency-block-width", type=int, default=128)
    args = parser.parse_args(argv)
    base = ROOT if root is None else root
    summary = run_two_memory_only_reruns(
        base,
        base / args.di_protocol,
        args.expected_di_protocol_sha256,
        base / args.di_manifest,
        base / args.output,
        natural_frequency_block_width=args.natural_frequency_block_width,
    )
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
