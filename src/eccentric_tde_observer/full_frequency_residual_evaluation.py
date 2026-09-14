"""可恢复全频物质残差评估的状态机、哈希账本与准入门。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError


_SCHEMA_VERSION = 1
_REQUIRED_INPUT_NAMES = frozenset(
    {
        "frozen_protocol",
        "encoded_material_state",
        "decoded_material_state",
        "physical_old_time_level",
        "initial_radiation_checkpoint",
    }
)


class FullFrequencyResidualFidelity(StrEnum):
    """全频评估是否足以定义消去辐射后的 Newton 物质残差。"""

    ONE_MAP_DIAGNOSTIC = "one_map_diagnostic"
    INNER_CONVERGED_RADIATION = "inner_converged_radiation"


class FullFrequencyResidualStatus(StrEnum):
    """可恢复评估的不可逆阶段。"""

    PLANNED = "planned"
    RADIATION_RUNNING = "radiation_running"
    RADIATION_COMPLETE = "radiation_complete"
    FEEDBACK_COMPLETE = "feedback_complete"
    DIAGNOSTIC_COMPLETE = "diagnostic_complete"
    COMPLETE = "complete"
    FAILED_PHYSICAL_DOMAIN = "failed_physical_domain"
    FAILED_NUMERICAL = "failed_numerical"


_TERMINAL_STATUSES = frozenset(
    {
        FullFrequencyResidualStatus.DIAGNOSTIC_COMPLETE,
        FullFrequencyResidualStatus.COMPLETE,
        FullFrequencyResidualStatus.FAILED_PHYSICAL_DOMAIN,
        FullFrequencyResidualStatus.FAILED_NUMERICAL,
    }
)

_ALLOWED_STATUS_TRANSITIONS = frozenset(
    {
        (FullFrequencyResidualStatus.PLANNED, FullFrequencyResidualStatus.RADIATION_RUNNING),
        (
            FullFrequencyResidualStatus.RADIATION_RUNNING,
            FullFrequencyResidualStatus.RADIATION_COMPLETE,
        ),
        (
            FullFrequencyResidualStatus.RADIATION_COMPLETE,
            FullFrequencyResidualStatus.FEEDBACK_COMPLETE,
        ),
        (
            FullFrequencyResidualStatus.FEEDBACK_COMPLETE,
            FullFrequencyResidualStatus.DIAGNOSTIC_COMPLETE,
        ),
        (
            FullFrequencyResidualStatus.FEEDBACK_COMPLETE,
            FullFrequencyResidualStatus.COMPLETE,
        ),
    }
)


def sha256_file(path: Path) -> str:
    """流式计算文件 SHA-256，不把大型辐射检查点读入内存。"""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _relative_workspace_path(workspace_root: Path, path: Path) -> str:
    root = workspace_root.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return str(candidate.resolve().relative_to(root))
    except ValueError as error:
        raise PhysicalDomainError("residual artifact leaves the workspace root") from error


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


@dataclass(frozen=True)
class ArtifactDigest:
    """工作区内一个不可变输入或阶段产物的内容指纹。"""

    path: str
    size_bytes: int
    sha256: str

    @classmethod
    def from_path(cls, workspace_root: Path, path: Path) -> ArtifactDigest:
        relative = _relative_workspace_path(workspace_root, path)
        absolute = workspace_root.resolve() / relative
        if not absolute.is_file():
            raise FileNotFoundError(absolute)
        size = absolute.stat().st_size
        if size < 1:
            raise PhysicalDomainError("residual artifact is empty")
        return cls(relative, int(size), sha256_file(absolute))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ArtifactDigest:
        artifact = cls(
            path=str(payload["path"]),
            size_bytes=int(payload["size_bytes"]),
            sha256=str(payload["sha256"]),
        )
        if artifact.size_bytes < 1 or len(artifact.sha256) != 64:
            raise PhysicalDomainError("stored artifact digest is invalid")
        return artifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }

    def verify(self, workspace_root: Path) -> None:
        current = ArtifactDigest.from_path(workspace_root, Path(self.path))
        if current != self:
            raise RuntimeError(f"residual artifact changed: {self.path}")


@dataclass(frozen=True)
class NamedArtifactDigest:
    """带物理角色名称的输入文件指纹。"""

    name: str
    artifact: ArtifactDigest

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "artifact": self.artifact.to_dict()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> NamedArtifactDigest:
        return cls(
            name=str(payload["name"]),
            artifact=ArtifactDigest.from_dict(payload["artifact"]),
        )


@dataclass(frozen=True)
class FullFrequencyResidualRequest:
    """一次全频残差评估不可在运行中改变的请求。"""

    evaluation_id: str
    fidelity: FullFrequencyResidualFidelity
    encoded_unknown_count: int
    frequency_group_count: int
    direction_count: int
    depth_count: int
    frequency_block_ranges: tuple[tuple[int, int], ...]
    radiation_output_path: str
    radiation_inner_residual_tolerance: float
    input_artifacts: tuple[NamedArtifactDigest, ...]

    def __post_init__(self) -> None:
        if not self.evaluation_id or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for character in self.evaluation_id
        ):
            raise PhysicalDomainError("full-frequency evaluation id is invalid")
        if not isinstance(self.fidelity, FullFrequencyResidualFidelity):
            raise TypeError("full-frequency residual fidelity is invalid")
        integers = (
            self.encoded_unknown_count,
            self.frequency_group_count,
            self.direction_count,
            self.depth_count,
        )
        if any(not isinstance(value, int) or value < 1 for value in integers):
            raise PhysicalDomainError("full-frequency residual dimensions are invalid")
        tolerance = float(self.radiation_inner_residual_tolerance)
        if not np.isfinite(tolerance) or tolerance <= 0.0:
            raise PhysicalDomainError("radiation inner residual tolerance is invalid")
        expected_start = 0
        for group_start, group_stop in self.frequency_block_ranges:
            if group_start != expected_start or group_stop <= group_start:
                raise PhysicalDomainError(
                    "frequency blocks must be positive, ordered and contiguous"
                )
            expected_start = group_stop
        if expected_start != self.frequency_group_count:
            raise PhysicalDomainError("frequency blocks do not cover the full grid")
        names = [entry.name for entry in self.input_artifacts]
        if len(names) != len(set(names)) or not _REQUIRED_INPUT_NAMES.issubset(names):
            raise PhysicalDomainError("full-frequency residual inputs are incomplete")
        if not self.radiation_output_path:
            raise PhysicalDomainError("radiation output path is empty")
        if self.radiation_output_path in {
            entry.artifact.path for entry in self.input_artifacts
        }:
            raise PhysicalDomainError("radiation output would overwrite a frozen input")

    @property
    def expected_radiation_size_bytes(self) -> int:
        return (
            self.frequency_group_count
            * self.direction_count
            * self.depth_count
            * np.dtype(np.float64).itemsize
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "fidelity": self.fidelity.value,
            "encoded_unknown_count": self.encoded_unknown_count,
            "frequency_group_count": self.frequency_group_count,
            "direction_count": self.direction_count,
            "depth_count": self.depth_count,
            "frequency_block_ranges": [list(value) for value in self.frequency_block_ranges],
            "radiation_output_path": self.radiation_output_path,
            "radiation_inner_residual_tolerance": self.radiation_inner_residual_tolerance,
            "input_artifacts": [entry.to_dict() for entry in self.input_artifacts],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FullFrequencyResidualRequest:
        return cls(
            evaluation_id=str(payload["evaluation_id"]),
            fidelity=FullFrequencyResidualFidelity(payload["fidelity"]),
            encoded_unknown_count=int(payload["encoded_unknown_count"]),
            frequency_group_count=int(payload["frequency_group_count"]),
            direction_count=int(payload["direction_count"]),
            depth_count=int(payload["depth_count"]),
            frequency_block_ranges=tuple(
                (int(value[0]), int(value[1]))
                for value in payload["frequency_block_ranges"]
            ),
            radiation_output_path=str(payload["radiation_output_path"]),
            radiation_inner_residual_tolerance=float(
                payload["radiation_inner_residual_tolerance"]
            ),
            input_artifacts=tuple(
                NamedArtifactDigest.from_dict(value)
                for value in payload["input_artifacts"]
            ),
        )


def build_full_frequency_residual_request(
    workspace_root: Path,
    *,
    evaluation_id: str,
    fidelity: FullFrequencyResidualFidelity,
    encoded_unknown_count: int,
    radiation_shape: tuple[int, int, int],
    frequency_block_ranges: tuple[tuple[int, int], ...],
    radiation_output_path: Path,
    radiation_inner_residual_tolerance: float,
    input_artifact_paths: dict[str, Path],
) -> FullFrequencyResidualRequest:
    """从当前文件内容冻结请求；后续恢复会逐项复核这些哈希。"""
    output_path = _relative_workspace_path(workspace_root, radiation_output_path)
    inputs = tuple(
        NamedArtifactDigest(
            name=name,
            artifact=ArtifactDigest.from_path(workspace_root, path),
        )
        for name, path in sorted(input_artifact_paths.items())
    )
    return FullFrequencyResidualRequest(
        evaluation_id=evaluation_id,
        fidelity=fidelity,
        encoded_unknown_count=int(encoded_unknown_count),
        frequency_group_count=int(radiation_shape[0]),
        direction_count=int(radiation_shape[1]),
        depth_count=int(radiation_shape[2]),
        frequency_block_ranges=frequency_block_ranges,
        radiation_output_path=output_path,
        radiation_inner_residual_tolerance=float(radiation_inner_residual_tolerance),
        input_artifacts=inputs,
    )


def _block_sha256(
    path: Path,
    request: FullFrequencyResidualRequest,
    block_index: int,
) -> str:
    start, stop = request.frequency_block_ranges[block_index]
    plane_bytes = (
        request.direction_count * request.depth_count * np.dtype(np.float64).itemsize
    )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(start * plane_bytes)
        remaining = (stop - start) * plane_bytes
        while remaining:
            block = stream.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("radiation checkpoint ended inside a completed block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


class RecoverableFullFrequencyResidualEvaluation:
    """以原子 JSON 清单管理大型全频残差评估，不接受部分检查点。"""

    def __init__(
        self,
        workspace_root: Path,
        manifest_path: Path,
        payload: dict[str, Any],
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        relative = _relative_workspace_path(self.workspace_root, manifest_path)
        self.manifest_path = self.workspace_root / relative
        self._payload = payload

    @classmethod
    def create(
        cls,
        workspace_root: Path,
        manifest_path: Path,
        request: FullFrequencyResidualRequest,
    ) -> RecoverableFullFrequencyResidualEvaluation:
        root = Path(workspace_root).resolve()
        _relative_workspace_path(root, Path(request.radiation_output_path))
        for entry in request.input_artifacts:
            entry.artifact.verify(root)
        request_payload = request.to_dict()
        payload: dict[str, Any] = {
            "schema_version": _SCHEMA_VERSION,
            "request": request_payload,
            "request_sha256": _canonical_sha256(request_payload),
            "status": FullFrequencyResidualStatus.PLANNED.value,
            "completed_frequency_blocks": [],
            "radiation": None,
            "feedback": None,
            "material_residual": None,
            "failure": None,
            "transitions": [FullFrequencyResidualStatus.PLANNED.value],
        }
        evaluation = cls(root, manifest_path, payload)
        if evaluation.manifest_path.exists():
            raise FileExistsError(evaluation.manifest_path)
        evaluation._save()
        return evaluation

    @classmethod
    def resume(
        cls,
        workspace_root: Path,
        manifest_path: Path,
        *,
        verify_artifacts: bool = True,
    ) -> RecoverableFullFrequencyResidualEvaluation:
        root = Path(workspace_root).resolve()
        relative = _relative_workspace_path(root, manifest_path)
        absolute = root / relative
        payload = json.loads(absolute.read_text(encoding="utf-8"))
        evaluation = cls(root, absolute, payload)
        evaluation._validate_manifest(verify_artifacts=verify_artifacts)
        return evaluation

    @property
    def request(self) -> FullFrequencyResidualRequest:
        return FullFrequencyResidualRequest.from_dict(self._payload["request"])

    @property
    def status(self) -> FullFrequencyResidualStatus:
        return FullFrequencyResidualStatus(self._payload["status"])

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._payload))

    def _save(self) -> None:
        state_payload = {
            key: value for key, value in self._payload.items() if key != "state_sha256"
        }
        self._payload["state_sha256"] = _canonical_sha256(state_payload)
        _write_json_atomic(self.manifest_path, self._payload)

    def _transition(self, status: FullFrequencyResidualStatus) -> None:
        if self.status in _TERMINAL_STATUSES:
            raise RuntimeError("full-frequency residual evaluation is terminal")
        self._payload["status"] = status.value
        self._payload["transitions"].append(status.value)
        self._save()

    def _radiation_path(self) -> Path:
        return self.workspace_root / self.request.radiation_output_path

    def _verify_radiation_shape(self) -> None:
        path = self._radiation_path()
        if not path.is_file() or path.stat().st_size != self.request.expected_radiation_size_bytes:
            raise RuntimeError("radiation checkpoint size does not match the frozen request")

    def _validate_manifest(self, *, verify_artifacts: bool) -> None:
        if self._payload.get("schema_version") != _SCHEMA_VERSION:
            raise RuntimeError("full-frequency residual manifest schema changed")
        state_payload = {
            key: value for key, value in self._payload.items() if key != "state_sha256"
        }
        if self._payload.get("state_sha256") != _canonical_sha256(state_payload):
            raise RuntimeError("full-frequency residual manifest state hash changed")
        request_payload = self._payload.get("request")
        if self._payload.get("request_sha256") != _canonical_sha256(request_payload):
            raise RuntimeError("full-frequency residual request hash changed")
        request = self.request
        status = self.status
        transitions = self._payload.get("transitions")
        if not isinstance(transitions, list) or not transitions or transitions[-1] != status.value:
            raise RuntimeError("full-frequency residual transition ledger is invalid")
        parsed_transitions = [FullFrequencyResidualStatus(value) for value in transitions]
        if parsed_transitions[0] is not FullFrequencyResidualStatus.PLANNED:
            raise RuntimeError("full-frequency residual transition ledger is invalid")
        for previous, current in zip(parsed_transitions[:-1], parsed_transitions[1:]):
            failure_transition = (
                previous not in _TERMINAL_STATUSES
                and current
                in {
                    FullFrequencyResidualStatus.FAILED_PHYSICAL_DOMAIN,
                    FullFrequencyResidualStatus.FAILED_NUMERICAL,
                }
            )
            if (previous, current) not in _ALLOWED_STATUS_TRANSITIONS and not failure_transition:
                raise RuntimeError("full-frequency residual transition ledger is invalid")
        block_records = self._payload.get("completed_frequency_blocks")
        if not isinstance(block_records, list):
            raise RuntimeError("full-frequency residual block ledger is invalid")
        indices = [int(record["block_index"]) for record in block_records]
        if len(indices) != len(set(indices)) or any(
            index < 0 or index >= len(request.frequency_block_ranges)
            for index in indices
        ):
            raise RuntimeError("full-frequency residual block indices are invalid")
        if verify_artifacts:
            for entry in request.input_artifacts:
                entry.artifact.verify(self.workspace_root)
            if block_records:
                self._verify_radiation_shape()
                for record in block_records:
                    index = int(record["block_index"])
                    if _block_sha256(self._radiation_path(), request, index) != record["sha256"]:
                        raise RuntimeError(f"completed radiation block changed: {index}")
            for stage_name in ("radiation", "feedback", "material_residual"):
                stage = self._payload.get(stage_name)
                if stage is not None:
                    ArtifactDigest.from_dict(stage["artifact"]).verify(self.workspace_root)

    def start_radiation(self) -> None:
        if self.status in _TERMINAL_STATUSES:
            raise RuntimeError("full-frequency residual evaluation is terminal")
        if self.status is not FullFrequencyResidualStatus.PLANNED:
            raise RuntimeError("radiation evaluation can only start from planned")
        self._transition(FullFrequencyResidualStatus.RADIATION_RUNNING)

    def mark_frequency_block_complete(self, block_index: int) -> None:
        if self.status is not FullFrequencyResidualStatus.RADIATION_RUNNING:
            raise RuntimeError("radiation block is outside the running stage")
        if not isinstance(block_index, int) or not 0 <= block_index < len(
            self.request.frequency_block_ranges
        ):
            raise PhysicalDomainError("radiation block index is invalid")
        self._verify_radiation_shape()
        digest = _block_sha256(self._radiation_path(), self.request, block_index)
        records = self._payload["completed_frequency_blocks"]
        for record in records:
            if int(record["block_index"]) == block_index:
                if record["sha256"] != digest:
                    raise RuntimeError(f"completed radiation block changed: {block_index}")
                return
        start, stop = self.request.frequency_block_ranges[block_index]
        records.append(
            {
                "block_index": block_index,
                "group_start": start,
                "group_stop": stop,
                "sha256": digest,
            }
        )
        records.sort(key=lambda value: int(value["block_index"]))
        self._save()

    def complete_radiation(
        self,
        *,
        inner_iteration_count: int,
        inner_residual_norm: float,
        inner_converged: bool,
        science_functionals_passed: bool,
        wall_runtime_s: float,
    ) -> None:
        if self.status is not FullFrequencyResidualStatus.RADIATION_RUNNING:
            raise RuntimeError("radiation completion is outside the running stage")
        request = self.request
        expected = set(range(len(request.frequency_block_ranges)))
        present = {
            int(value["block_index"])
            for value in self._payload["completed_frequency_blocks"]
        }
        if present != expected:
            raise RuntimeError("partial radiation checkpoint cannot be completed")
        residual = float(inner_residual_norm)
        runtime = float(wall_runtime_s)
        if (
            not isinstance(inner_iteration_count, int)
            or inner_iteration_count < 1
            or not np.isfinite(residual)
            or residual < 0.0
            or not np.isfinite(runtime)
            or runtime <= 0.0
        ):
            raise PhysicalDomainError("radiation completion diagnostics are invalid")
        if request.fidelity is FullFrequencyResidualFidelity.ONE_MAP_DIAGNOSTIC:
            if inner_iteration_count != 1 or inner_converged:
                raise PhysicalDomainError("one-map fidelity cannot claim inner convergence")
        elif (
            not inner_converged
            or residual > request.radiation_inner_residual_tolerance
            or not science_functionals_passed
        ):
            raise RuntimeError("inner-converged radiation gate did not pass")
        self._verify_radiation_shape()
        for record in self._payload["completed_frequency_blocks"]:
            index = int(record["block_index"])
            if _block_sha256(self._radiation_path(), request, index) != record["sha256"]:
                raise RuntimeError(f"completed radiation block changed: {index}")
        artifact = ArtifactDigest.from_path(
            self.workspace_root, Path(request.radiation_output_path)
        )
        self._payload["radiation"] = {
            "artifact": artifact.to_dict(),
            "inner_iteration_count": inner_iteration_count,
            "inner_residual_norm": residual,
            "inner_converged": bool(inner_converged),
            "science_functionals_passed": bool(science_functionals_passed),
            "wall_runtime_s": runtime,
        }
        self._transition(FullFrequencyResidualStatus.RADIATION_COMPLETE)

    def radiation_checkpoint_for_feedback(self) -> Path:
        if self.status not in {
            FullFrequencyResidualStatus.RADIATION_COMPLETE,
            FullFrequencyResidualStatus.FEEDBACK_COMPLETE,
            FullFrequencyResidualStatus.DIAGNOSTIC_COMPLETE,
            FullFrequencyResidualStatus.COMPLETE,
        }:
            raise RuntimeError("partial radiation checkpoint is not a physical feedback input")
        artifact = ArtifactDigest.from_dict(self._payload["radiation"]["artifact"])
        artifact.verify(self.workspace_root)
        return self.workspace_root / artifact.path

    def complete_feedback(
        self,
        feedback_artifact_path: Path,
        *,
        source_consistency_passed: bool,
        conservation_passed: bool,
        wall_runtime_s: float,
    ) -> None:
        if self.status is not FullFrequencyResidualStatus.RADIATION_COMPLETE:
            raise RuntimeError("feedback can only follow a complete radiation state")
        runtime = float(wall_runtime_s)
        if not np.isfinite(runtime) or runtime <= 0.0:
            raise PhysicalDomainError("feedback runtime is invalid")
        artifact = ArtifactDigest.from_path(self.workspace_root, feedback_artifact_path)
        self._payload["feedback"] = {
            "artifact": artifact.to_dict(),
            "source_consistency_passed": bool(source_consistency_passed),
            "conservation_passed": bool(conservation_passed),
            "wall_runtime_s": runtime,
        }
        self._transition(FullFrequencyResidualStatus.FEEDBACK_COMPLETE)

    def complete_material_residual(self, residual_artifact_path: Path) -> None:
        if self.status is not FullFrequencyResidualStatus.FEEDBACK_COMPLETE:
            raise RuntimeError("material residual can only follow complete feedback")
        feedback = self._payload["feedback"]
        if not feedback["source_consistency_passed"] or not feedback["conservation_passed"]:
            raise RuntimeError("invalid feedback cannot define a material residual")
        path = Path(residual_artifact_path)
        if not path.is_absolute():
            path = self.workspace_root / path
        vector = np.load(path, allow_pickle=False)
        if (
            not isinstance(vector, np.ndarray)
            or vector.shape != (self.request.encoded_unknown_count,)
            or vector.dtype.kind != "f"
            or not np.all(np.isfinite(vector))
        ):
            raise PhysicalDomainError("encoded full-frequency material residual is invalid")
        artifact = ArtifactDigest.from_path(self.workspace_root, path)
        self._payload["material_residual"] = {
            "artifact": artifact.to_dict(),
            "l2_norm": float(np.linalg.norm(vector)),
            "maximum_absolute_component": float(np.max(np.abs(vector))),
        }
        if self.request.fidelity is FullFrequencyResidualFidelity.ONE_MAP_DIAGNOSTIC:
            self._transition(FullFrequencyResidualStatus.DIAGNOSTIC_COMPLETE)
        else:
            radiation = self._payload["radiation"]
            if (
                not radiation["inner_converged"]
                or radiation["inner_residual_norm"]
                > self.request.radiation_inner_residual_tolerance
                or not radiation["science_functionals_passed"]
            ):
                raise RuntimeError("radiation state cannot define a Newton residual")
            self._transition(FullFrequencyResidualStatus.COMPLETE)

    def load_newton_residual(self) -> NDArray[np.float64]:
        if (
            self.status is not FullFrequencyResidualStatus.COMPLETE
            or self.request.fidelity
            is not FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
        ):
            raise RuntimeError("evaluation is not an inner-converged Newton residual")
        artifact = ArtifactDigest.from_dict(
            self._payload["material_residual"]["artifact"]
        )
        artifact.verify(self.workspace_root)
        vector = np.asarray(
            np.load(self.workspace_root / artifact.path, allow_pickle=False),
            dtype=np.float64,
        )
        vector.setflags(write=False)
        return vector

    def record_failure(
        self,
        *,
        physical_domain: bool,
        stage: str,
        exception_type: str,
        message: str,
    ) -> None:
        if self.status in _TERMINAL_STATUSES:
            raise RuntimeError("full-frequency residual evaluation is terminal")
        if not stage or not exception_type or not message:
            raise PhysicalDomainError("failure record is incomplete")
        self._payload["failure"] = {
            "stage": stage,
            "exception_type": exception_type,
            "message": message,
            "physical_domain": bool(physical_domain),
        }
        status = (
            FullFrequencyResidualStatus.FAILED_PHYSICAL_DOMAIN
            if physical_domain
            else FullFrequencyResidualStatus.FAILED_NUMERICAL
        )
        self._transition(status)


def write_encoded_residual_atomic(path: Path, residual: ArrayLike) -> None:
    """原子写入一维残差；非有限值直接拒绝，不做替换或裁剪。"""
    vector = np.asarray(residual, dtype=np.float64)
    if vector.ndim != 1 or vector.size < 1 or not np.all(np.isfinite(vector)):
        raise PhysicalDomainError("encoded material residual is invalid")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp.npy")
    np.save(temporary, vector)
    os.replace(temporary, path)
