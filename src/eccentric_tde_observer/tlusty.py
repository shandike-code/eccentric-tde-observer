"""TLUSTY 208 静态环带运行器；只处理 Phase 7A 的局域连续谱。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from numpy.typing import NDArray

from .radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4
from .source import PhysicalDomainError


def _readonly(array: NDArray) -> NDArray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class TlustyNumericalControls:
    """会写入 ``annulus.nst`` 的、可追踪的 TLUSTY 数值控制量。"""

    maximum_iterations: int = 30
    convergence_threshold: float = 1.0e-3
    radiative_equilibrium_division_tau: float | None = None
    general_change_limit: float | None = None
    electron_density_change_limit: float | None = None
    temperature_change_limit: float | None = None
    relaxation_coefficient: float | None = None
    surface_column_mass_g_cm2: float | None = None
    mean_intensity_zero_fraction: float | None = None
    maximum_frequency_hz: float | None = None
    grey_iterations: int | None = None
    ng_acceleration_start: int | None = None
    kantorovich_start: int | None = None
    lambda_iterations: int | None = None
    fix_structure: bool = False
    hold_temperature_fixed: bool = False
    include_hminus: bool = False
    surface_viscosity_exponent: float | None = None
    inner_dissipation_fraction: float | None = None
    surface_radiation_acceleration_control: float | None = None
    hydrostatic_surface_boundary_mode: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.maximum_iterations, (int, np.integer))
            or isinstance(self.maximum_iterations, (bool, np.bool_))
            or int(self.maximum_iterations) < 0
        ):
            raise PhysicalDomainError("maximum_iterations must be a non-negative integer")
        object.__setattr__(self, "maximum_iterations", int(self.maximum_iterations))
        for name in (
            "convergence_threshold",
            "radiative_equilibrium_division_tau",
            "general_change_limit",
            "electron_density_change_limit",
            "temperature_change_limit",
            "relaxation_coefficient",
            "surface_column_mass_g_cm2",
            "mean_intensity_zero_fraction",
            "maximum_frequency_hz",
        ):
            raw_value = getattr(self, name)
            if raw_value is None:
                continue
            value = float(raw_value)
            if not np.isfinite(value) or value <= 0.0:
                raise PhysicalDomainError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if self.surface_viscosity_exponent is not None:
            exponent = float(self.surface_viscosity_exponent)
            if not np.isfinite(exponent) or exponent < 0.0:
                raise PhysicalDomainError(
                    "surface_viscosity_exponent must be finite and non-negative"
                )
            object.__setattr__(self, "surface_viscosity_exponent", exponent)
        if self.inner_dissipation_fraction is not None:
            fraction = float(self.inner_dissipation_fraction)
            if not np.isfinite(fraction) or not (
                fraction == -1.0 or 0.0 < fraction <= 1.0
            ):
                raise PhysicalDomainError(
                    "inner_dissipation_fraction must be -1 or lie in (0, 1]"
                )
            object.__setattr__(self, "inner_dissipation_fraction", fraction)
        if self.surface_radiation_acceleration_control is not None:
            control = float(self.surface_radiation_acceleration_control)
            if not np.isfinite(control) or control == 0.0 or control < -2.0:
                raise PhysicalDomainError(
                    "surface_radiation_acceleration_control must be -2, -1, or positive"
                )
            object.__setattr__(
                self, "surface_radiation_acceleration_control", control
            )
        for name in (
            "ng_acceleration_start",
            "kantorovich_start",
            "lambda_iterations",
            "grey_iterations",
        ):
            raw_value = getattr(self, name)
            if raw_value is None:
                continue
            if (
                not isinstance(raw_value, (int, np.integer))
                or isinstance(raw_value, (bool, np.bool_))
                or int(raw_value) < 0
            ):
                raise PhysicalDomainError(f"{name} must be a non-negative integer")
            object.__setattr__(self, name, int(raw_value))
        if self.hydrostatic_surface_boundary_mode is not None:
            mode = self.hydrostatic_surface_boundary_mode
            if (
                not isinstance(mode, (int, np.integer))
                or isinstance(mode, (bool, np.bool_))
                or int(mode) not in (0, 1, 2)
            ):
                raise PhysicalDomainError(
                    "hydrostatic_surface_boundary_mode must be 0, 1, or 2"
                )
            object.__setattr__(self, "hydrostatic_surface_boundary_mode", int(mode))

    def render(self) -> str:
        entries: list[tuple[str, int | float]] = [
            ("NITER", self.maximum_iterations),
            ("CHMAX", self.convergence_threshold),
        ]
        optional = (
            ("TAUDIV", self.radiative_equilibrium_division_tau),
            ("DPSILG", self.general_change_limit),
            ("DPSILN", self.electron_density_change_limit),
            ("DPSILT", self.temperature_change_limit),
            ("ORELAX", self.relaxation_coefficient),
            ("DM1", self.surface_column_mass_g_cm2),
            ("RADZER", self.mean_intensity_zero_fraction),
            ("FRCMAX", self.maximum_frequency_hz),
            ("IACC", self.ng_acceleration_start),
            ("ITEK", self.kantorovich_start),
            ("NLAMBD", self.lambda_iterations),
            ("ITGMAX", self.grey_iterations),
            ("ZETA1", self.surface_viscosity_exponent),
            ("FRACTV", self.inner_dissipation_fraction),
            ("XGRAD", self.surface_radiation_acceleration_control),
            ("IBCHE", self.hydrostatic_surface_boundary_mode),
        )
        entries.extend((name, value) for name, value in optional if value is not None)
        if self.fix_structure:
            entries.append(("IFIXMO", 1))
        elif self.hold_temperature_fixed:
            entries.append(("INRE", 0))
        if self.include_hminus:
            entries.extend((("IHM", 1), ("IOPADD", 1), ("IOPHMI", 1)))
        return "\n".join(f"{name}={value:.5g}" for name, value in entries) + "\n"


@dataclass(frozen=True)
class TlustyAnnulusInput:
    """直接指定 ``(T_eff,Q,m0)`` 的 TLUSTY 静态环带输入。"""

    effective_temperature_k: float
    gravity_coefficient_s2: float
    midplane_column_mass_g_cm2: float
    lte: bool = True
    grey_start: bool = True
    continuum_frequency_points: int = 50
    hydrogen_neutral_levels: int = 9
    helium_neutral_levels: int = 14
    helium_singly_ionized_levels: int = 14
    include_bound_bound_lines: bool = False
    numerical_controls: TlustyNumericalControls = field(
        default_factory=TlustyNumericalControls
    )

    def __post_init__(self) -> None:
        for name in (
            "effective_temperature_k",
            "gravity_coefficient_s2",
            "midplane_column_mass_g_cm2",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise PhysicalDomainError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if (
            not isinstance(self.continuum_frequency_points, (int, np.integer))
            or isinstance(self.continuum_frequency_points, (bool, np.bool_))
            or int(self.continuum_frequency_points) < 10
        ):
            raise PhysicalDomainError("continuum_frequency_points must be an integer >= 10")
        object.__setattr__(
            self, "continuum_frequency_points", int(self.continuum_frequency_points)
        )
        for name, maximum in (
            ("hydrogen_neutral_levels", 9),
            ("helium_neutral_levels", 14),
            ("helium_singly_ionized_levels", 14),
        ):
            raw_value = getattr(self, name)
            if (
                not isinstance(raw_value, (int, np.integer))
                or isinstance(raw_value, (bool, np.bool_))
                or not 1 <= int(raw_value) <= maximum
            ):
                raise PhysicalDomainError(f"{name} must lie in [1, {maximum}]")
            object.__setattr__(self, name, int(raw_value))
        if not isinstance(self.include_bound_bound_lines, (bool, np.bool_)):
            raise TypeError("include_bound_bound_lines must be boolean")
        object.__setattr__(
            self, "include_bound_bound_lines", bool(self.include_bound_bound_lines)
        )
        if not isinstance(self.numerical_controls, TlustyNumericalControls):
            raise TypeError("numerical_controls must be TlustyNumericalControls")


@dataclass(frozen=True)
class TlustyEmergentFlux:
    """TLUSTY unit 13 的表面 Eddington flux 及能量闭合。"""

    frequency_hz: NDArray[np.float64]
    eddington_flux_hnu_cgs: NDArray[np.float64]
    eddington_factor_h_over_j: NDArray[np.float64]
    effective_temperature_k: float

    @property
    def surface_flux_fnu_cgs(self) -> NDArray[np.float64]:
        # 中文：TLUSTY 输出 H_nu；物理单面通量为 F_nu=4*pi*H_nu。
        return _readonly(4.0 * np.pi * self.eddington_flux_hnu_cgs.copy())

    @property
    def integrated_surface_flux_cgs(self) -> float:
        return float(np.trapezoid(self.surface_flux_fnu_cgs, self.frequency_hz))

    @property
    def target_surface_flux_cgs(self) -> float:
        return float(
            STEFAN_BOLTZMANN_ERG_S_CM2_K4 * self.effective_temperature_k**4
        )

    @property
    def fractional_energy_residual(self) -> float:
        return self.integrated_surface_flux_cgs / self.target_surface_flux_cgs - 1.0


@dataclass(frozen=True)
class TlustyRunResult:
    run_directory: Path
    spectrum: TlustyEmergentFlux
    final_iteration: int
    final_maximum_relative_change: float
    return_code: int

    @property
    def converged_at_1e3(self) -> bool:
        return self.return_code == 0 and self.final_maximum_relative_change < 1.0e-3

    @property
    def diagnostic_only(self) -> bool:
        return self.final_iteration == 0


@dataclass(frozen=True)
class TlustyDiskScaleHeights:
    """TLUSTY 灰初值报告的气体压与辐射压特征高度。"""

    gas_pressure_scale_height_cm: float
    radiation_pressure_scale_height_cm: float
    radiation_to_gas_ratio: float


@dataclass(frozen=True)
class TlustyDirectAnnulusParameters:
    """从 ``XMSTAR=0`` 输入恢复的静态环带三个直接参数。"""

    effective_temperature_k: float
    gravity_coefficient_s2: float
    midplane_column_mass_g_cm2: float


def render_h_he_annulus_input(configuration: TlustyAnnulusInput) -> str:
    """生成官方 H/He benchmark 原子设置的 disk-annulus unit 5 输入。"""
    lte_flag = "T" if configuration.lte else "F"
    grey_flag = "T" if configuration.grey_start else "F"
    # 中文：Phase 7A 只求连续谱；ILVLIN=100 关闭束缚-束缚线，避免把线谱混入比较。
    linearization = 0 if configuration.include_bound_bound_lines else 100
    return f""" 0.0 {configuration.effective_temperature_k:.12e} {configuration.gravity_coefficient_s2:.12e} {configuration.midplane_column_mass_g_cm2:.12e}  ! XMSTAR=0: TEFF, QGRAV, DMTOT
 {lte_flag}  {grey_flag}              ! LTE, LTGRAY
 'annulus.nst'     ! auditable numerical controls
*
* frequencies
*
 {configuration.continuum_frequency_points:d}
*
* H/He-only feasibility composition; not a metal-complete atmosphere
*
 8                 ! NATOMS
* mode abn modpf
    2   0   0
    2   0   0
    0   0   0
    0   0   0
    0   0   0
    1   0   0
    1   0   0
    1   0   0
*
*iat    iz   nlevs  ilast ilvlin  nonstd typion  filei
*
   1     0    {configuration.hydrogen_neutral_levels:2d}      0    {linearization:3d}      0    ' H 1' './data/h1.dat'
   1     1     1      1      0      0    ' H 2' ' '
   2     0    {configuration.helium_neutral_levels:2d}      0    {linearization:3d}      0    'He 1' './data/he1.dat'
   2     1    {configuration.helium_singly_ionized_levels:2d}      0    {linearization:3d}      0    'He 2' './data/he2.dat'
   2     2     1      1      0      0    'He 3' ' '
   0     0     0     -1      0      0    '    ' ' '
*
* end
"""


def parse_direct_annulus_input(path: Path) -> TlustyDirectAnnulusParameters:
    """严格读取首行的 ``XMSTAR=0, T_eff, Q, m0`` 参数。"""
    lines = path.read_text().splitlines()
    if not lines:
        raise ValueError(f"{path}: empty TLUSTY input")
    fields = lines[0].split("!", maxsplit=1)[0].split()
    if len(fields) != 4:
        raise ValueError(f"{path}: expected four direct-annulus parameters")
    values = np.asarray([_parse_fortran_float(field) for field in fields])
    if not np.all(np.isfinite(values)):
        raise ArithmeticError(f"{path}: direct-annulus parameters are non-finite")
    if values[0] != 0.0:
        raise PhysicalDomainError(f"{path}: XMSTAR must be zero for direct annulus input")
    if np.any(values[1:] <= 0.0):
        raise PhysicalDomainError(f"{path}: T_eff, Q and m0 must be positive")
    return TlustyDirectAnnulusParameters(
        effective_temperature_k=float(values[1]),
        gravity_coefficient_s2=float(values[2]),
        midplane_column_mass_g_cm2=float(values[3]),
    )


def _parse_fortran_float(token: str) -> float:
    return float(token.replace("D", "E").replace("d", "e"))


def parse_unit13(path: Path, effective_temperature_k: float) -> TlustyEmergentFlux:
    """严格解析 unit 13，并按频率升序返回 ``H_nu``。"""
    rows: list[tuple[float, float, float]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 3:
            raise ValueError(f"{path}:{line_number}: expected three columns")
        rows.append(tuple(_parse_fortran_float(field) for field in fields))
    if len(rows) < 2:
        raise ValueError(f"{path}: unit 13 contains fewer than two frequency rows")
    values = np.asarray(rows, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ArithmeticError(f"{path}: unit 13 contains non-finite values")
    order = np.argsort(values[:, 0], kind="stable")
    frequency = values[order, 0]
    eddington_flux = values[order, 1]
    eddington_factor = values[order, 2]
    if np.any(frequency <= 0.0) or np.any(np.diff(frequency) <= 0.0):
        raise PhysicalDomainError("TLUSTY unit 13 frequencies must be positive and unique")
    if np.any(eddington_flux < 0.0):
        raise PhysicalDomainError("TLUSTY unit 13 H_nu must be non-negative")
    if np.any(eddington_factor <= 0.0):
        raise PhysicalDomainError("TLUSTY unit 13 H/J must be positive")
    return TlustyEmergentFlux(
        frequency_hz=_readonly(frequency.copy()),
        eddington_flux_hnu_cgs=_readonly(eddington_flux.copy()),
        eddington_factor_h_over_j=_readonly(eddington_factor.copy()),
        effective_temperature_k=float(effective_temperature_k),
    )


def parse_final_relative_change(path: Path) -> tuple[int, float]:
    """从 unit 9 取得最后一次迭代所有深度中的最大相对改变量。"""
    by_iteration: dict[int, list[float]] = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) != 9:
            continue
        try:
            iteration = int(fields[0])
            int(fields[1])
            maximum = abs(_parse_fortran_float(fields[6]))
            int(fields[7])
            int(fields[8])
        except ValueError:
            continue
        by_iteration.setdefault(iteration, []).append(maximum)
    if not by_iteration:
        raise ValueError(f"{path}: no TLUSTY relative-change rows found")
    final_iteration = max(by_iteration)
    return final_iteration, float(max(by_iteration[final_iteration]))


def parse_disk_scale_heights(path: Path) -> TlustyDiskScaleHeights:
    """解析 TLUSTY disk 灰初值的两个尺度高度及其比值。"""
    text = path.read_text()
    patterns = (
        r"GAS PRESSURE SCALE HEIGHT\s*=\s*([+\-0-9.DEde]+)",
        r"RAD\.PRESSURE SCALE HEIGHT\s*=\s*([+\-0-9.DEde]+)",
        r"RATIO\s*=\s*([+\-0-9.DEde]+)",
    )
    values: list[float] = []
    for pattern in patterns:
        match = re.search(pattern, text)
        if match is None:
            raise ValueError(f"{path}: missing TLUSTY disk scale-height diagnostic")
        values.append(_parse_fortran_float(match.group(1)))
    gas, radiation, ratio = values
    if not np.all(np.isfinite(values)) or gas <= 0.0 or radiation <= 0.0 or ratio <= 0.0:
        raise PhysicalDomainError("TLUSTY disk scale heights must be finite and positive")
    independently_computed_ratio = radiation / gas
    if not np.isclose(ratio, independently_computed_ratio, rtol=1.0e-3, atol=0.0):
        raise ArithmeticError("TLUSTY disk scale-height ratio is internally inconsistent")
    return TlustyDiskScaleHeights(gas, radiation, ratio)


def run_h_he_annulus(
    executable: Path,
    atomic_data_directory: Path,
    run_directory: Path,
    configuration: TlustyAnnulusInput,
    *,
    initial_model_path: Path | None = None,
    timeout_seconds: float = 600.0,
) -> TlustyRunResult:
    """运行一个隔离的 TLUSTY 环带；所有失败文件均保留在运行目录。"""
    executable = executable.resolve()
    atomic_data_directory = atomic_data_directory.resolve()
    run_directory = run_directory.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    for filename in ("h1.dat", "he1.dat", "he2.dat"):
        source = atomic_data_directory / filename
        if not source.is_file():
            raise FileNotFoundError(source)
    if run_directory.exists() and any(run_directory.iterdir()):
        raise FileExistsError(f"run directory is not empty: {run_directory}")
    run_directory.mkdir(parents=True, exist_ok=True)
    (run_directory / "fort.1").write_text("1\n")
    input_text = render_h_he_annulus_input(configuration)
    (run_directory / "annulus.5").write_text(input_text)
    (run_directory / "annulus.nst").write_text(
        configuration.numerical_controls.render()
    )
    # 中文：TLUSTY 208 的连续不透明度会从固定的 ``./data`` 路径读取表文件。
    # 保留到已校验原子数据库的只读目录链接，避免悄悄关闭 H- 等默认过程。
    (run_directory / "data").symlink_to(atomic_data_directory, target_is_directory=True)
    if initial_model_path is not None:
        initial_model = initial_model_path.resolve()
        if not initial_model.is_file():
            raise FileNotFoundError(initial_model)
        shutil.copy2(initial_model, run_directory / "fort.8")

    with (run_directory / "annulus.5").open("rb") as stdin_file, (
        run_directory / "annulus.6"
    ).open("wb") as stdout_file, (run_directory / "annulus.stderr").open(
        "wb"
    ) as stderr_file:
        completed = subprocess.run(
            [str(executable)],
            cwd=run_directory,
            stdin=stdin_file,
            stdout=stdout_file,
            stderr=stderr_file,
            timeout=float(timeout_seconds),
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"TLUSTY failed with return code {completed.returncode}; retained {run_directory}"
        )
    required_outputs = ["fort.7", "fort.13"]
    if configuration.numerical_controls.maximum_iterations > 0:
        required_outputs.append("fort.9")
    for required in required_outputs:
        if not (run_directory / required).is_file():
            raise RuntimeError(f"TLUSTY did not create {required}; retained {run_directory}")
    if configuration.numerical_controls.maximum_iterations == 0:
        iteration, maximum_change = 0, float("inf")
    else:
        iteration, maximum_change = parse_final_relative_change(run_directory / "fort.9")
    spectrum = parse_unit13(run_directory / "fort.13", configuration.effective_temperature_k)
    return TlustyRunResult(
        run_directory=run_directory,
        spectrum=spectrum,
        final_iteration=iteration,
        final_maximum_relative_change=maximum_change,
        return_code=completed.returncode,
    )
