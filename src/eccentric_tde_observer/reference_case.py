"""阶段 2 使用的严格局域域 ZO 参考点。"""

from __future__ import annotations

from .zo_reference import (
    ZOConstantEParameters,
    ZOConstantEReferenceModel,
    build_zo_constant_e_reference_model,
    rescale_constant_e_circularization_efficiency,
)


STRICT_ECCENTRICITY = 0.6
STRICT_CIRCULARIZATION_EFFICIENCY = 0.01
STRICT_ANOMALY_CLUSTERING_POWER = 5.0


def strict_domain_parameters(
    eccentricity: float = STRICT_ECCENTRICITY,
) -> ZOConstantEParameters:
    """返回阶段 1H 筛选后采用的常偏心源参数。"""
    return ZOConstantEParameters(
        black_hole_mass_msun=1.0e6,
        stellar_mass_msun=1.0,
        stellar_radius_rsun=1.0,
        circularization_efficiency=1.0,
        outer_to_inner_semimajor_axis=2.0,
        eccentricity=eccentricity,
        opacity_cm2_g=0.34,
    )


def build_strict_domain_reference_model(
    radial_points: int = 65,
    anomaly_points: int = 1024,
    *,
    eccentricity: float = STRICT_ECCENTRICITY,
) -> ZOConstantEReferenceModel:
    """构造严格域参考源；低 V 是已记录的条件选择，不代表典型 TDE。"""
    base = build_zo_constant_e_reference_model(
        strict_domain_parameters(eccentricity),
        radial_points=radial_points,
        anomaly_points=anomaly_points,
        anomaly_sampling="pericentre_clustered",
        pericentre_clustering_power=STRICT_ANOMALY_CLUSTERING_POWER,
    )
    return rescale_constant_e_circularization_efficiency(
        base, STRICT_CIRCULARIZATION_EFFICIENCY
    )
