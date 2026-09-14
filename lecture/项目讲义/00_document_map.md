# Markdown 文档地图

本页覆盖本理论项目、项目使用的本地论文和直接相关的研究报告。论文原文保持只读；从本页
产生的入链足以让 Obsidian 显示 backlinks。

## 项目总览与规范

- [[eccentric_tde_observer/README|代码项目总览]]
- [[eccentric_tde_observer/docs/code_conventions|代码规范]]
- [[eccentric_tde_observer/docs/chat_output_standard|项目聊天输出规范]]
- [[eccentric_tde_observer/docs/obsidian_linking_standard|Obsidian 双链与讲义文档规范]]
- [[eccentric_tde_observer/lecture/项目讲义/README|讲义入口]]
- [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]
- [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]
- [[eccentric_tde_observer/docs/project_closeout_2026-09-02|2026-09-02 项目阶段性收尾]]
- [[eccentric_tde_observer/lecture/AI任务简报/claude_lecture_brief|Claude 初稿任务书]]：只记录讲义生成要求，
  不作为科学证据；

## 第一阶段：把解析源变成几何和基础观察者积分

- [[eccentric_tde_observer/docs/erratum_2022_correction|ZO 2022 Erratum corrected 面积专项修正]]
- [[eccentric_tde_observer/docs/phase1_baseline|1A face-on 辐射基线]]
- [[eccentric_tde_observer/docs/phase1b_geometry|1B 偏心几何与投影]]
- [[eccentric_tde_observer/docs/phase1c_vertical|1C 垂向密度与灰光球]]
- [[eccentric_tde_observer/docs/phase1d_raytrace|1D Newtonian 射线与第一张频谱]]
- [[eccentric_tde_observer/docs/phase1e_zo_reference|1E ZO 参考源与积分审计]]
- [[eccentric_tde_observer/docs/phase1f_adaptive_surface|1F 自适应表面积分]]
- [[eccentric_tde_observer/docs/phase1g_vertical_closure|1G 垂向闭合敏感性]]
- [[eccentric_tde_observer/docs/phase1h_validity_domain|1H 局域垂向适用域]]
- [[eccentric_tde_observer/docs/phase1i_strict_domain_spectra|1I 严格域方向与相位光谱]]

## 第二阶段：频移、热化和能量守恒局域谱

- [[eccentric_tde_observer/docs/phase2a_weakfield_frequency_shift|2A 弱场频移]]
- [[eccentric_tde_observer/docs/phase2b_atmosphere_audit|2B opacity 与热化审计]]
- [[eccentric_tde_observer/docs/phase2c_modified_blackbody|2C modified-blackbody]]
- [[eccentric_tde_observer/docs/phase2_complete|第二阶段完成报告]]

## 第三阶段：非灰失效门、角分布、偏振、GR 和再处理约束

- [[eccentric_tde_observer/docs/phase3a_non_gray|3A 低温 H/He LTE 非灰失效门]]
- [[eccentric_tde_observer/docs/phase3b_angle_polarization|3B 角分辨强度与偏振]]
- [[eccentric_tde_observer/docs/phase3c_gr_transfer|3C Cunningham 式弱场直接像]]
- [[eccentric_tde_observer/docs/phase3d_reprocessing_constraints|3D 最小再处理层约束]]
- [[eccentric_tde_observer/docs/phase3_complete|第三阶段完成说明]]

## 第四阶段：动态大气接口与观测图谱

- [[eccentric_tde_observer/docs/phase4a_annulus_bridge|4A 动态柱到 annulus atmosphere]]
- [[eccentric_tde_observer/docs/phase4b_observer_atlas|4B 倾角—进动相位图谱]]
- [[eccentric_tde_observer/docs/phase4_complete|第四阶段完成报告]]

## 第五阶段：观察者系光谱与后续观测接口

- [[eccentric_tde_observer/docs/phase5a_observer_frame_flambda|5A 观察者系 F-lambda 光谱]]
- [[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|5B1 线性拱点本征模与物理时标门槛]]
- `outputs/phase5b1_linear_apsidal_report.json`：强--弱形式、自由边界、GR 和物理归一化审计；
- `outputs/phase5b1_linear_eigenfunctions.png`：四种径向范围的无节点线性本征函数；
- `outputs/phase5b1_linear_convergence.png`：64--512 点径向收敛与独立强形式对照；
- `outputs/phase5b1_precession_scale_audit.png`：ZO Eq. (48) 十倍归一化差异与局域 GR 梯度；
- [[eccentric_tde_observer/docs/phase5b2_nonlinear_hamiltonian_gate|5B2 三维非线性局域 Hamiltonian 与导数门槛]]
- `outputs/phase5b2_hamiltonian_surface.csv`：130 个 $(e,q)$ 非交叉局域状态；
- `outputs/phase5b2_hamiltonian_surface.png`：完整呼吸解后的 $F(e,f)$ 验证面；
- `outputs/phase5b2_vertical_breathing_profiles.png`：高偏心呼吸与 Jacobian 对照；
- `outputs/phase5b2_local_hamiltonian_controls.png`：线性四阶余项和五点偏导稳定性；
- [[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|5B3 全局非线性拱点模与 ZO Fig. 6/7 基准门]]
- outputs/phase5b3_nonlinear_apsidal_report.json：方程内部门、文献基准门和时间轴授权；
- outputs/phase5b3_fig6_profile_audit.png：published 矢量路径、三维解和二维控制；
- outputs/phase5b3_frequency_benchmark.png：低振幅本征频率四路线比较；
- outputs/zo2020_original_fig7_reference.png：原始 Fig. 7 圆盘端与窄环端分支行为；
- [[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|5B3a 已发表分支反演审计]]
- outputs/phase5b3a_published_branch_inverse_audit_report.json：连续追踪、偏差形状与时间轴授权；
- outputs/phase5b3a_published_frequency_continuation.csv：18 个 published 与三维无节点状态；
- outputs/phase5b3a_frequency_guess_robustness.csv：成功和表域拒绝的全部初始频率猜测；
- outputs/phase5b3a_published_branch_inverse_audit.png：Fig. 7 对照与 $1/e_{\rm in}$ 偏差诊断；
- outputs/phase5b3a_linear_branch_topology.png：无节点有限支与高节点发散支；
- [[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|5B3b 完整二维非线性分支诊断]]
- outputs/phase5b3b_full_2d_nonlinear_report.json：二维公式内部门、published 门和时间轴授权；
- outputs/phase5b3b_quadratic_limit.csv：OL Eq. (40) 二阶 Hessian 回收；
- outputs/phase5b3b_2d_table_convergence.csv：两档二维 Hamiltonian 表与四个全局 BVP；
- outputs/phase5b3b_2d_derivative_holdout.csv：六个直接五点偏导留出状态；
- outputs/phase5b3b_published_comparison.csv：published、二维线性和完整二维非线性频率；
- outputs/phase5b3b_full_2d_nonlinear_diagnostic.png：频率、模形和非线性修正总图；
- [[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|5B3c 印刷方程路径与边界切线审计]]
- outputs/phase5b3c_printed_equation_path_report.json：印刷路径门、边界切线门和时间轴授权；
- outputs/phase5b3c_printed_equation_ledger.csv：主文/附录符号、caption 与归一化账本；
- outputs/phase5b3c_equation_variant_convergence.csv：两档表上的主文和附录字面 BVP；
- outputs/phase5b3c_published_boundary_tangents.csv：Fig. 6 矢量路径端点切线与自由根；
- outputs/phase5b3c_printed_equation_path_audit.png：方程路径、模形和边界切线总图；
- [[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|5B3d published 实现公开来源审计]]
- outputs/phase5b3d_public_source_availability_report.json：期刊、Crossref、arXiv、GitHub 与
  Zenodo 的响应哈希、源包成员和时间轴授权；
- [[eccentric_tde_observer/docs/zo2020_author_source_request_draft|ZO 2020 Fig. 6/7 作者请求及发送记录]]：
  只请求求解器、原始数组和实现约定；2026-08-30 已发送，当前等待回复；
- [[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|5B4 严格域候选时标与模形兼容门]]
- outputs/phase5b4_strict_domain_candidate_timescale_report.json：高偏心方程门、候选周期和 atlas 授权；
- outputs/phase5b4_candidate_timescales.csv：直接 Eq. (39) 与印刷 Eq. (48) 候选周期账本；
- outputs/phase5b4_derivative_resolution_audit.csv：两档失败和最终通过的高偏心偏导门；
- outputs/phase5b4_mode_shape_compatibility.png：候选 $e(a)$ 与常偏心 atlas 的不兼容；
- outputs/phase5b4_candidate_timescale_ledger.png：无量纲频率与十倍物理归一化差异；
- [[eccentric_tde_observer/docs/phase5b5_mode_matched_time_axis|5B5 模形哈希绑定的候选相对时间轴]]
- outputs/phase5b5_mode_matched_time_axis_summary.json：时间钟、指纹门与旧 atlas 拒绝结论；
- outputs/phase5b5_mode_matched_phase_schedule.csv：模形匹配候选的 15 度相对时间模板；
- outputs/phase5b5_mode_matched_time_axis.png：径向模形门与直接/印刷相位时间轴英文图；
- [[eccentric_tde_observer/docs/phase5b6_equation_self_consistent_candidate_source|5B6 方程自洽候选源]]
- outputs/phase5b6_candidate_source_report.json：两级指纹、候选源场、corrected 光度与有效域接口；
- outputs/phase5b6_candidate_source_radial_diagnostics.csv：两条候选的径向动力学与热源诊断；
- outputs/phase5b6_candidate_source_diagnostics.png：$e(a)$、Jacobian、$H/r$ 与 $T_{\rm eff}$ 英文图；
- [[eccentric_tde_observer/docs/phase5b7_candidate_validity_convergence|5B7 候选有效域网格收敛]]
- outputs/phase5b7_candidate_validity_convergence_report.json：径向与 $E$/表面三角收敛门；
- outputs/phase5b7_candidate_validity_convergence.csv：两候选、两闭合的完整分辨率账本；
- outputs/phase5b7_candidate_validity_convergence.png：面积分数、表面几何、最小光深与斜率英文图；
- [[eccentric_tde_observer/docs/phase5b8_candidate_source_time_mapping|5B8 候选源拱点相位—相对时间映射]]
- outputs/phase5b8_candidate_source_time_mapping_report.json：候选周期、双指纹和时间轴授权；
- outputs/phase5b8_candidate_source_phase_schedule.csv：两条候选每 $15^{\circ}$ 的相对时间表；
- outputs/phase5b8_candidate_source_time_mapping.png：相位—时间与十年相位漂移英文图；
- [[eccentric_tde_observer/lecture/AI任务简报/phase5_literature_package|第五阶段预备文献包：来源、用途与验收]]
- [[eccentric_tde_observer/lecture/AI任务简报/phase5_mineru_conversion_brief|Claude–MinerU 转换任务书]]
- [[eccentric_tde_observer/lecture/AI任务简报/phase5_mineru_addendum_leloudas|Claude–MinerU Leloudas 补充任务书]]
- [[markdown_papers/phase5_conversion_report|Phase 5 MinerU 转换与 Codex 独立验收报告]]
- [[markdown_papers/astro-ph_9905116_Hogg_distance_measures|Hogg 1999：宇宙学距离与红移谱通量]]
- [[markdown_papers/0708.2259_Poole_Swift_UVOT_calibration|Poole et al. 2008：Swift/UVOT 标定]]
- [[markdown_papers/1102.4717_Breeveld_updated_UVOT_calibration|Breeveld et al. 2011：UVOT 标定更新]]
- [[markdown_papers/astro-ph_9809387_Fitzpatrick_extinction|Fitzpatrick 1998：星际消光]]
- [[markdown_papers/1012.4804_Schlafly_Finkbeiner_reddening|Schlafly 与 Finkbeiner 2011：尘埃图重标定]]
- [[markdown_papers/1703.09824_VanderPlas_Lomb_Scargle|VanderPlas 2017：Lomb–Scargle 周期图]]
- [[markdown_papers/1510.04879_Stone_Loeb_Lense_Thirring_TDE|Stone 与 Loeb 2016：TDE 节点进动]]
- [[markdown_papers/2402.09689_Pasham_Lense_Thirring_TDE|Pasham et al. 2024：AT2020ocn X-ray 变化]]
- [[markdown_papers/2303.06523_Yao_ZTF_TDE_demographics|Yao et al. 2023：ZTF TDE 人口统计]]
- [[markdown_papers/2308.13019_Guolo_Xray_selected_TDEs|Guolo et al. 2023：optical 选 TDE 的 X-ray 性质]]
- [[markdown_papers/2206.09039_Patra_AT2019qiz_spectropolarimetry|Patra et al. 2022：AT2019qiz 光谱偏振]]
- [[markdown_papers/2207.06855_Leloudas_asymmetric_electron_scattering_photosphere|Leloudas et al. 2022：非球对称电子散射光球]]
- [[markdown_papers/2208.14465_Liodakis_AT2020mot_polarization|Liodakis et al. 2022：AT2020mot 偏振]]
- [[markdown_papers/astro-ph_9804288_Hubeny_NLTE_vertical_structure|Hubeny 与 Hubeny 1998：NLTE 盘垂向结构]]

## 第六阶段：corrected 曲面上的条件性谱线响应

- [[eccentric_tde_observer/docs/phase6_line_response|Phase 6 条件性谱线响应报告]]
- `outputs/phase6_line_response_report.json`：线传递、三种权重、分类门和收敛；
- `outputs/phase6_line_diagnostics.csv`：完整倾角--相位连续诊断；
- `outputs/phase6_dynamic_spectrum.csv`：一个进动周期的归一化运动学线核。

本阶段只用 Halpha 的 $6562.8\ \mathrm{\mathring A}$ 作为展示轴；它不提供 Halpha、Hbeta
或 He II 的绝对光度，也没有加入自由盘风或任意径向发射率指数。`[A/V/O]`

## 第七阶段：局域大气闭合审计

- [[eccentric_tde_observer/docs/phase7a_static_annulus|Phase 7A 低温、极低 Q 静态环带审计]]；
- `outputs/phase7a_static_annulus_report.json`：求解器构建、官方控制、实际柱和阶段决策；
- `outputs/phase7a_representative_annuli.csv`：12 个真实代表柱、灰诊断和直接 LTE 失败；
- `outputs/phase7a_rep03_continuation.csv`：代表柱 03 的重力续接检查点；
- `outputs/phase7a_static_annulus_audit.png`：代表覆盖、辐射压尺度、直接失败和续接边界。
- [[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 规定背景周期柱与守恒布居控制]]；
- `outputs/phase7b_periodic_column_report.json`：轨道时间、背景范围、守恒与收敛；
- `outputs/phase7b_periodic_column_control.png`：规定背景、时标和两态解析控制；
- `outputs/phase7b_kinetics_sensitivity.csv`：四档响应时标的完整周期布居。
- [[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 频率--角度转移解析控制]]；
- `outputs/phase7b2_transfer_report.json`：解析门、ZO 高光深压力测试与开放物理；
- `outputs/phase7b2_convergence.csv`：角、深度、频率、时间和高光深散射收敛；
- `outputs/phase7b2_transfer_controls.png`：纯吸收、散射守恒和四条收敛轴。
- [[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 可追溯 H/He 原子率与静态耦合]]；
- `outputs/phase7b3_atomic_continuum_report.json`：原子数据来源、详细平衡、静态耦合与边界；
- `outputs/phase7b3_convergence.csv`：光致电离频率、转移角度和 ZO 垂向网格收敛；
- `outputs/phase7b3_atomic_continuum_controls.png`：原子率、稳态、ZO opacity 和收敛总图。
- [[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a H/He 碰撞动力学与固定背景松弛]]；
- `outputs/phase7b4a_collisional_kinetics_report.json`：碰撞率、详细平衡、固定松弛和中面时标；
- `outputs/phase7b4a_convergence.csv`：电荷求根与 ZO 源相位网格收敛；
- `outputs/phase7b4a_collisional_kinetics_controls.png`：六面板碰撞动力学控制；
- `outputs/phase7b4a_collisional_kinetics_convergence.png`：两条独立收敛轴。
- [[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 电荷自洽的轨道耦合 H/He 基态动力学]]；
- `outputs/phase7b4b_orbit_coupled_kinetics_report.json`：周期解、守恒、初值独立性和接受门；
- `outputs/phase7b4b_periodic_kinetics.csv`：动态、瞬时无辐射稳态和 LTE 的逐相位对照；
- `outputs/phase7b4b_convergence.csv`：非线性解析题、轨道时间步和源相位网格收敛；
- `outputs/phase7b4b_orbit_coupled_kinetics.png`：周期布居与缺失辐射诊断；
- `outputs/phase7b4b_orbit_coupled_kinetics_convergence.png`：三条独立收敛轴。
- [[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c 规定辐射场与 H/He 基态周期布居耦合]]；
- `outputs/phase7b4c_prescribed_radiation_report.json`：零场、热详细平衡、稀释敏感性和边界；
- `outputs/phase7b4c_prescribed_radiation_orbits.csv`：全部 $W$ 的逐相位光致率与布居；
- `outputs/phase7b4c_dilution_sensitivity.csv`：连续规定场敏感性诊断；
- `outputs/phase7b4c_convergence.csv`：频率、时间步和源相位网格收敛；
- `outputs/phase7b4c_prescribed_radiation_kinetics.png`：四面板规定场耦合主图；
- `outputs/phase7b4c_prescribed_radiation_convergence.png`：三条独立收敛轴。
- [[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d 固定温度板层辐射--布居--opacity 反馈]]；
- `outputs/phase7b4d_coupled_slab_report.json`：固定点、透明/LTE/能量门和阶段边界；
- `outputs/phase7b4d_coupled_slab_depth.csv`：逐深度基态布居、电子密度与光致率；
- `outputs/phase7b4d_coupled_slab_convergence.csv`：频率、深度、角度和欠松弛扫描；
- `outputs/phase7b4d_coupled_slab.png`：衰减、布居、光深与初态收敛主图；
- `outputs/phase7b4d_coupled_slab_convergence.png`：收敛和透明--不透明反馈控制图。
- [[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e 基态 Milne 连续发射与固定温度能量账本]]；
- `outputs/phase7b4e_continuum_emission_report.json`：Kirchhoff/LTE、光子率、能量账本和边界；
- `outputs/phase7b4e_emissive_slab_depth.csv`：逐深度布居、基态率和恒温项；
- `outputs/phase7b4e_emergent_continuum.csv`：有限能段入射与双边出射连续谱；
- `outputs/phase7b4e_continuum_convergence.csv`：频率、深度、半区间角度、欠松弛和直接加密；
- `outputs/phase7b4e_continuum_emission.png`：连续能流、布居、能量账本和初态控制；
- `outputs/phase7b4e_continuum_convergence.png`：详细平衡、收敛和能量分配控制。
- [[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f 规定加热下的逐深度温度平衡]]；
- `outputs/phase7b4f_temperature_balance_report.json`：稳定根、无根门、热稳定性和收敛边界；
- `outputs/phase7b4f_temperature_profile.csv`：逐深度温度、布居与局域能量残差；
- `outputs/phase7b4f_isothermal_scan.csv`：规定耗散沉积分数的等温根拓扑；
- `outputs/phase7b4f_temperature_convergence.csv`：频率、深度和角度直接加密；
- `outputs/phase7b4f_temperature_balance.png`：根拓扑、温度剖面、布居与连续谱对照；
- `outputs/phase7b4f_temperature_convergence.png`：离散化误差、稳定性步长和无根门。
- [[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 有限沉积柱静态门]]；
- `outputs/phase7b4g_finite_column_report.json`：根拓扑、稳定性、谱差和路线决策；
- `outputs/phase7b4g_column_topology.csv`：沉积柱质量与温度域根状态；
- `outputs/phase7b4g_validity_map.csv`：全部柱质量--温度采样及失败状态；
- `outputs/phase7b4g_process_controls.csv`：连续、Compton、线完全逃逸及联合控制；
- `outputs/phase7b4g_temperature_profile.csv`：参考柱逐深度温度、布居和能量账本；
- `outputs/phase7b4g_convergence.csv`：频率、深度、角度和初温直接加密；
- `outputs/phase7b4g_emergent_continuum.csv`：有限柱与局域 ZO 黑体连续谱；
- `outputs/phase7b4g_finite_column.png`：根拓扑、微物理控制、温度剖面和能量项；
- `outputs/phase7b4g_convergence.png`：加密、根带和归一化连续谱差异。
- [[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 有限静力大气表准入门]]；
- `outputs/phase7b4h_hydrostatic_gate_report.json`：静力厚度、压力剖面、收敛和路线决策；
- `outputs/phase7b4h_representative_hydrostatic_gate.csv`：12 个代表柱和两种耗散律的逐点门；
- `outputs/phase7b4h_reference_profiles.csv`：代表柱 03 的固定/压力匹配剖面；
- `outputs/phase7b4h_convergence.csv`：深度、频率和 opacity 迭代收敛；
- `outputs/phase7b4h_hydrostatic_gate.png`：静力厚度、压力根、剖面和扩散结构；
- `outputs/phase7b4h_hydrostatic_convergence.png`：厚度、剖面和密度反转诊断收敛。
- [[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 周期动态 H/He 基态能量柱]]；
- `outputs/phase7b4i_periodic_dynamic_report.json`：周期能量账本、人口、初态独立性和路线门；
- `outputs/phase7b4i_periodic_dynamic_phase.csv`：两种耗散律下逐相位热状态和能量项；
- `outputs/phase7b4i_periodic_dynamic_profile.csv`：主算例逐相位、逐质量深度状态；
- `outputs/phase7b4i_periodic_dynamic_convergence.csv`：时间、深度和频率三轴加密；
- `outputs/phase7b4i_periodic_dynamic_column.png`：呼吸背景、温度、通量和基态人口；
- `outputs/phase7b4i_energy_convergence.png`：周期账本、热记忆和收敛边界。
- [[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase 7B4j 自适应拉格朗日深度与高时间分辨率审计]]；
- `outputs/phase7b4j_adaptive_convergence_report.json`：网格构造、深度/时间误差和准入决策；
- `outputs/phase7b4j_adaptive_mass_edges.csv`：四档共享拉格朗日质量边界；
- `outputs/phase7b4j_adaptive_monitor.csv`：温度、Rosseland opacity 与 He III 轨道梯度监视函数；
- `outputs/phase7b4j_depth_convergence.csv`：固定/自适应逐点、柱平均和前沿误差；
- `outputs/phase7b4j_time_convergence.csv`：128--1024 相位的温度、能流和人口误差；
- `outputs/phase7b4j_adaptive_depth.png`：自适应网格与深度收敛四面板图；
- `outputs/phase7b4j_time_convergence.png`：高轨道时间分辨率四面板图。
- [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 双网格误差估计与 2048 相位审计]]；
- `outputs/phase7b4k_error_estimated_convergence_report.json`：深度、时间和联合准入决策；
- `outputs/phase7b4k_depth_report.json`：双网格误差分量、嵌套网格和深度失败门；
- `outputs/phase7b4k_time_report.json`：512--2048 相位时间误差与守恒残差；
- `outputs/phase7b4k_two_grid_monitor.csv`：四个误差分量和解析幂律基线；
- `outputs/phase7b4k_nested_mass_edges.csv`：严格嵌套质量边界及基线份额敏感性；
- `outputs/phase7b4k_depth_convergence.csv`：fixed、gradient 与 two-grid 空间误差；
- `outputs/phase7b4k_time_convergence.csv`：512、1024、2048 相位直接对照；
- `outputs/phase7b4k_two_grid_depth.png`：双网格监视函数和深度权衡四面板图；
- `outputs/phase7b4k_time_2048.png`：2048 相位时间审计四面板图。
- [[eccentric_tde_observer/docs/phase7b4l_conservative_subcell_reconstruction|Phase 7B4l 保守子单元重构与空间生产门]]；
- `outputs/phase7b4l_control_report.json`：制造前沿、父平均与能量反演控制；
- `outputs/phase7b4l_subcell_report.json`：保留子单元空间误差、守恒诊断和路线门；
- `outputs/phase7b4l_complete_report.json`：控制与正式空间判据的合并结果；
- `outputs/phase7b4l_manufactured_front.csv`：移动 He III 制造前沿对照；
- `outputs/phase7b4l_subcell_edges.csv`：父单元和严格嵌套子单元边界；
- `outputs/phase7b4l_subcell_profiles.csv`：16、32、64 有效深度的动态状态；
- `outputs/phase7b4l_subcell_convergence.csv`：局域、积分、前沿和守恒误差；
- `outputs/phase7b4l_subcell_controls.png`：制造前沿与解析守恒四面板图；
- `outputs/phase7b4l_subcell_convergence.png`：正式空间收敛四面板图。
- [[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 前沿感知可变子单元与空间准入门]]；
- `outputs/phase7b4m_control_report.json`：嵌入式误差和变量网格控制；
- `outputs/phase7b4m_complete_report.json`：空间、时间与联合参考准入判据；
- `outputs/phase7b4m_embedded_indicator.csv`：逐父单元四分量缺陷与稳定排序；
- `outputs/phase7b4m_convergence.csv`：56、60、62 层真实动态候选误差与成本；
- `outputs/phase7b4m_estimator_validation.csv`：未加密 pilot 对有限 64 层参考的独立排序验证；
- `outputs/phase7b4m_candidate_parent_residuals.csv`：加密后逐父单元残余误差；
- `outputs/phase7b4m_embedded_refinement.png`：嵌入式误差、网格和控制四面板图；
- `outputs/phase7b4m_variable_convergence.png`：正式变量深度收敛四面板图。
- [[eccentric_tde_observer/docs/phase7b4n_joint_depth_time_reference|Phase 7B4n 联合深度--时间周期动态参考]]；
- `outputs/phase7b4n_control_report.json`：dense--colored 数值等价与成本控制；
- `outputs/phase7b4n_complete_report.json`：64×1024 联合有限参考、耦合门和后续授权；
- `outputs/phase7b4n_joint_convergence.csv`：高深度时间误差与高时间空间误差；
- `outputs/phase7b4n_time_population_error_locations.csv`：H II/He III 时间误差位置；
- `outputs/phase7b4n_energy_ledger.csv`：三个正式算例的周期能量账本；
- `outputs/phase7b4n_colored_jacobian_control.png`：dense--colored 英文控制图；
- `outputs/phase7b4n_joint_convergence.png`：联合深度--时间英文收敛图；
- `outputs/phase7b4n_joint_reference_map.png`：64×1024 英文动态二维图。
- [[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o 高深度 2048 相位周期时间参考]]；
- `outputs/phase7b4o_complete_report.json`：64×2048 有限参考、时间门和后续授权；
- `outputs/phase7b4o_time_convergence.csv`：512--1024--2048 高深度时间误差；
- `outputs/phase7b4o_population_error_locations.csv`：H II/He III 最大误差位置；
- `outputs/phase7b4o_energy_ledger.csv`：三档周期闭合与能量账本；
- `outputs/phase7b4o_time_convergence.png`：英文高深度时间收敛图；
- `outputs/phase7b4o_reference_map.png`：64×2048 英文动态二维图。
- [[eccentric_tde_observer/docs/phase7b4p_frozen_nonlocal_transfer|Phase 7B4p 冻结非局域转移审计]]；
- `outputs/phase7b4p_complete_report.json`：形式解、局域闭合、四轴门和路线判据；
- `outputs/phase7b4p_controls.csv`：Kirchhoff、能量、镜像、散射与扩散控制；
- `outputs/phase7b4p_convergence.csv`：全轨道时间及代表相位角度、频率、深度误差；
- `outputs/phase7b4p_extended_convergence.csv`：71--519 频点和 4--24 方向扩展序列；
- `outputs/phase7b4p_frozen_nonlocal_orbit.png`：英文冻结通量、扩散时标与失衡图；
- `outputs/phase7b4p_nonlocal_spectra.png`：英文探索性谱、光深和光致率图；
- `outputs/phase7b4p_convergence.png`：英文四轴收敛图。
- [[eccentric_tde_observer/docs/phase7b4q_threshold_quadrature|Phase 7B4q 阈值求积与分离深度网格]]；
- `outputs/phase7b4q_summary.json`：正式冻结配置、失败门与开放项；
- `outputs/phase7b4q_depth128_phase1024.npz`：独立 N128×1024 动态物质参考；
- `outputs/phase7b4q_transfer_subgrid_convergence.csv`：8/16/32 辐射子网格直接收敛；
- `outputs/phase7b4q_production_frequency_angle.csv`：新正式深度上的频率与角向门；
- `outputs/phase7b4q_threshold_quadrature.png`：英文阈值求积与解析控制图；
- `outputs/phase7b4q_depth_and_transfer_convergence.png`：英文物质/辐射深度分离图；
- `outputs/phase7b4q_production_gates.png`：英文通过与失败门总图。
- [[eccentric_tde_observer/docs/phase7b4r_n128_time_reference|Phase 7B4r N128 时间参考]]；
- `outputs/phase7b4r_summary.json`：N128 有限时间门、授权项和开放动态辐射项；
- `outputs/phase7b4r_depth128_phase2048.npz`：独立 N128×2048 周期物质参考；
- `outputs/phase7b4r_time_convergence.csv`：1024 对 2048 联合时间指标；
- `outputs/phase7b4r_error_locations.csv`：各连续场最差相位和深度；
- `outputs/phase7b4r_time_convergence.png`：英文时间门图；
- `outputs/phase7b4r_reference_map.png`：英文温度、He III 和热记忆二维图。
- [[eccentric_tde_observer/docs/phase7b4s_implicit_ale_radiation|Phase 7B4s 隐式 ALE 辐射储能核]]；
- `outputs/phase7b4s_summary.json`：解析门、网格运动、双频 pilot 与下一阶段判定；
- `outputs/phase7b4s_two_frequency_pilot.npz`：N128×2048 的 10/60 eV 周期 $J_{\nu}$ 和出射诊断；
- `outputs/phase7b4s_controls.csv`：吸收、散射、ALE、真空平流和冻结回归；
- `outputs/phase7b4s_mesh_audit.csv`：逐相位厚度、速度、步长和网格位移；
- `outputs/phase7b4s_pilot_cycles.csv`、`outputs/phase7b4s_pilot_phase.csv`：周期与逐相位证据；
- `outputs/phase7b4s_implicit_controls.png`：英文解析/守恒控制图；
- `outputs/phase7b4s_zo_mesh_motion.png`：英文移动网格审计图；
- `outputs/phase7b4s_radiation_pilot.png`：英文双频辐射储能 pilot 图。
- [[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t 完整 Lorentz 频率组与正性迭代门]]；
- `outputs/phase7b4t_summary.json`：完整 Lorentz、频率组兼容性、动态扩散和阶段判定；
- `outputs/phase7b4t_angular_controls.csv`：辐射张量与共动角测度控制；
- `outputs/phase7b4t_frequency_group_controls.csv`：40--303 物理组守恒搬移收敛；
- `outputs/phase7b4t_solver_stress.csv`：N128×160×S16 正性迭代与稀疏 LU 压力对照；
- `outputs/phase7b4t_diagnostics.npz`：逐频率、逐深度绘图诊断；
- `outputs/phase7b4t_lorentz_controls.png`：英文 Lorentz、频率组和呼吸速度控制图；
- `outputs/phase7b4t_solver_and_dynamic_diffusion.png`：英文求解器与动态扩散门；
- `outputs/phase7b4t_frequency_grid_gate.png`：英文积分节点--频率组兼容性图。
- [[eccentric_tde_observer/docs/phase7b4u_multigroup_continuum_gate|Phase 7B4u H/He 多群连续系数与原子率门]]；
- `outputs/phase7b4u_summary.json`：168 个真实物态上的多群准入和下一联立授权；
- `outputs/phase7b4u_multigroup_convergence.csv`：静态节点与 153--1205 组误差分量；
- `outputs/phase7b4u_worst_states.csv`：各候选最坏物态；
- `outputs/phase7b4u_state_sample.csv`：21 相位乘 8 深度的真实物态样本；
- `outputs/phase7b4u_multigroup_gate.png`：英文多群收敛、表示对照与状态误差图；
- `outputs/phase7b4u_worst_state_coefficients.png`：英文最坏状态连续系数图。
- [[eccentric_tde_observer/docs/phase7b4v_mixed_frame_ale_gate|Phase 7B4v 完整 Lorentz 物质源与 ALE 联立门]]；
- `outputs/phase7b4v_summary.json`：解析控制、真实一步状态频率加密与阶段授权边界；
- `outputs/phase7b4v_controls.csv`、`outputs/phase7b4v_dynamic_diffusion.csv`：平衡和四力控制；
- `outputs/phase7b4v_actual_states.csv`、`outputs/phase7b4v_actual_state_convergence.csv`：
  三个真实一步物态和 303--38496 组有限加密；
- `outputs/phase7b4v_diagnostics.npz`：未设 floor 的逐组残差；
- `outputs/phase7b4v_mixed_frame_ale_controls.png`：英文算子控制与残差图；
- `outputs/phase7b4v_actual_state_convergence.png`：英文真实状态频率收敛、误差分量与成本图。
- [[eccentric_tde_observer/docs/phase7b4w_threshold_frequency_groups|Phase 7B4w 阈值局域 P0 频率组门]]；
- `outputs/phase7b4w_summary.json`：精确阈值、三状态频率门、效率门和后续授权边界；
- `outputs/phase7b4w_controls.csv`：候选网格组宽、精确阈值和 Planck 积分恒等式；
- `outputs/phase7b4w_actual_states.csv`、`outputs/phase7b4w_state_convergence.csv`：
  568--18105 组的真实一步状态、误差分量与成本；
- `outputs/phase7b4w_diagnostics.npz`：候选组数和精确 H/He 阈值；
- `outputs/phase7b4w_threshold_group_geometry.png`：英文阈值局域网格与全局成本图；
- `outputs/phase7b4w_actual_state_convergence.png`：英文真实状态精度、效率和成本图。
- [[eccentric_tde_observer/docs/phase7b4x_p1_frequency_moments|Phase 7B4x 守恒 P1 频率矩门]]；
- `outputs/phase7b4x_summary.json`、`outputs/phase7b4x_state_convergence.csv`：
  普通对数 P1 的解析控制、三状态误差和失败授权；
- `outputs/phase7b4x_p1_frequency_convergence.png`、`outputs/phase7b4x_p1_operator_diagnostics.png`：
  英文 P1 精度、残差、能量账本、limiter 和成本图。
- [[eccentric_tde_observer/docs/phase7b4y_threshold_p1_gate|Phase 7B4y 阈值局域 P1 联合门]]；
- `outputs/phase7b4y_summary.json`、`outputs/phase7b4y_state_convergence.csv`：
  阈值局域 P1 的几何/算子通过与三状态频率失败；
- `outputs/phase7b4y_threshold_p1_convergence.png`、`outputs/phase7b4y_threshold_p1_cost.png`：
  英文联合路线精度、成本和 limiter 图。
- [[eccentric_tde_observer/docs/phase7b4z_p2_frequency_moments|Phase 7B4z 守恒 P2 频率矩门]]；
- `outputs/phase7b4z_summary.json`、`outputs/phase7b4z_state_convergence.csv`：
  普通对数 P2 的解析控制、算子/三状态失败与授权边界；
- `outputs/phase7b4z_p2_frequency_convergence.png`、`outputs/phase7b4z_p2_operator_diagnostics.png`：
  英文 P2 精度、残差、能量账本、limiter 和成本图。
- [[eccentric_tde_observer/docs/phase7b5a_log_frequency_p1_gate|Phase 7B5a 对数频率守恒 P1 门]]；
- `outputs/phase7b5a_summary.json`、`outputs/phase7b5a_state_convergence.csv`：
  $Q=\nu I_{\nu}$ log-P1 的解析控制、算子/三状态失败与授权边界；
- `outputs/phase7b5a_log_p1_frequency_convergence.png`、
  `outputs/phase7b5a_log_p1_operator_diagnostics.png`：
  英文 log-P1 精度、残差、能量账本、limiter 和成本图。
- [[eccentric_tde_observer/docs/phase7b5b_rate_kernel_grid_gate|Phase 7B5b H I 率核固定网格门]]；
- `outputs/phase7b5b_summary.json`、`outputs/phase7b5b_state_convergence.csv`：
  三档率核聚焦的网格/算子通过、三状态频率失败与稳健选择边界；
- `outputs/phase7b5b_rate_kernel_convergence.png`、
  `outputs/phase7b5b_rate_kernel_sensitivity.png`：
  英文频率收敛、组数分配、算子残差和 limiter 敏感性图。
- [[eccentric_tde_observer/docs/phase7b5c_signed_rate_error_localization|Phase 7B5c H I 率误差定位]]；
- `outputs/phase7b5c_summary.json`、`outputs/phase7b5c_signed_rate_profiles.csv`：
  候选/参考有符号率差、物理能段贡献、参考谱投影与动态余项；
- `outputs/phase7b5c_signed_rate_error_localization.png`、
  `outputs/phase7b5c_projection_dynamic_decomposition.png`：
  英文率差密度、累计抵消、区域定位、投影和可实现性诊断图。
- [[eccentric_tde_observer/docs/phase7b5d_dynamic_operator_controls|Phase 7B5d 动态子算子控制]]；
- `outputs/phase7b5d_summary.json`、`outputs/phase7b5d_operator_controls.csv`：
  匹配 P1/P0 的 Lorentz、ALE、散射和真实连续碰撞控制；
- `outputs/phase7b5d_dynamic_operator_controls.png`、
  `outputs/phase7b5d_threshold_region_response.png`：
  英文误差降低、残差和 H I 阈值带响应图。
- [[eccentric_tde_observer/docs/phase7b5e_lorentz_component_controls|Phase 7B5e Lorentz 分量控制]]；
- `outputs/phase7b5e_summary.json`、`outputs/phase7b5e_lorentz_component_controls.csv`：
  强度、消光和发射率关闭实验的匹配 P1/P0 误差、方程门与授权边界；
- `outputs/phase7b5e_lorentz_component_controls.png`、
  `outputs/phase7b5e_threshold_region_response.png`：
  英文分量响应、失败残差标记和 H I 阈值区域图。
- [[eccentric_tde_observer/docs/phase7b5f_single_pass_intensity_transform|Phase 7B5f 单次强度搬移]]；
- `outputs/phase7b5f_summary.json`、`outputs/phase7b5f_single_pass_states.csv`：
  同一解析输入的一次 P1/P0 强度搬移、能量、H I 率与独立 Planck 参考；
- `outputs/phase7b5f_single_pass_gate.png`、`outputs/phase7b5f_threshold_spectra.png`：
  英文单次搬移门、H I 误差能段和阈值组平均谱图。
- [[eccentric_tde_observer/docs/phase7b5g_fixed_point_feedback_audit|Phase 7B5g 固定点反馈审计]]；
- `outputs/phase7b5g_summary.json`、`outputs/phase7b5g_iteration_history.csv`：
  P1/P0 固定点截面、H I 率/能量增长、limiter 历史和授权边界；
- `outputs/phase7b5g_fixed_point_error_growth.png`、`outputs/phase7b5g_region_evolution.png`：
  英文固定点误差增长与 H I 阈值主导区迁移图。
- [[eccentric_tde_observer/docs/phase7b5h_recurrence_decomposition|Phase 7B5h 单步注入--传播分解]]；
- `outputs/phase7b5h_summary.json`、`outputs/phase7b5h_recurrence_decomposition.csv`：
  同一输入上的 P1/P0 单步映射、H I 率注入--传播账本和授权边界；
- `outputs/phase7b5h_recurrence_decomposition.png`、
  `outputs/phase7b5h_injection_region_evolution.png`：
  英文单步分量占比与注入误差阈值区演化图。
- [[eccentric_tde_observer/docs/phase7b5i_partition_representation_split|Phase 7B5i 分区--P1/P0 拆分]]；
- `outputs/phase7b5i_summary.json`、`outputs/phase7b5i_partition_representation.csv`：
  细 P0、同分区 P0、log-P1 与同成本 P0 的单步率账本和授权边界；
- `outputs/phase7b5i_partition_representation_decomposition.png`、
  `outputs/phase7b5i_same_cost_p0_comparison.png`、
  `outputs/phase7b5i_component_region_evolution.png`：
  英文分区--P1/P0 分量、同成本精度和阈值区演化图。
- [[eccentric_tde_observer/docs/phase7b5j_prescribed_partition_audit|Phase 7B5j 非拟合 P0 分区审计]]；
- `outputs/phase7b5j_summary.json`、`outputs/phase7b5j_partition_states.csv`：
  普通对数、固定率核与 Doppler 像锚点的三档组数、15 截面率门；
- `outputs/phase7b5j_partition_convergence.png`、
  `outputs/phase7b5j_checkpoint_sensitivity.png`、
  `outputs/phase7b5j_doppler_region_comparison.png`：
  英文分区收敛、全截面敏感性和 Doppler 带误差比例图。
- [[eccentric_tde_observer/docs/phase7b5k_high_resolution_convergence|Phase 7B5k 高分辨率相邻收敛]]；
- `outputs/phase7b5k_summary.json`、`outputs/phase7b5k_high_resolution_states.csv`、
  `outputs/phase7b5k_resource_costs.csv`：
  9632/19264 组的全截面 H I 率、单单元时间与返回数组占用；
- `outputs/phase7b5k_high_resolution_convergence.png`、
  `outputs/phase7b5k_checkpoint_errors.png`、
  `outputs/phase7b5k_resource_scaling.png`：
  英文相邻收敛、检查点误差和资源缩放图。
- [[eccentric_tde_observer/docs/phase7b5l_multiresolution_component_gate|Phase 7B5l 多分辨率组件门]]；
- `outputs/phase7b5l_summary.json`、`outputs/phase7b5l_parent_indicators.csv`、
  `outputs/phase7b5l_control_spectra.csv`：
  1--2--4 频率层级、父组联合指标、4814 叶预算和控制谱 provenance；
- `outputs/phase7b5l_frequency_hierarchy.png`、
  `outputs/phase7b5l_embedded_indicator.png`、
  `outputs/phase7b5l_transfer_controls.png`：
  英文层级组宽、确定性指标和守恒/求积控制图。
- [[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|Phase 7B5m 冻结网格独立实际态验证]]；
- `outputs/phase7b5m_summary.json`、`outputs/phase7b5m_train_validation_states.csv`、
  `outputs/phase7b5m_frozen_parent_ranking.csv`：
  预声明训练/留出划分、冻结网格哈希、15 个实际截面率误差、正式算子控制与资源账本；
- `outputs/phase7b5m_train_validation_errors.png`、
  `outputs/phase7b5m_holdout_validation.png`、
  `outputs/phase7b5m_resource_costs.png`：
  英文训练/验证误差、留出门和直接返回数组成本图。
- [[eccentric_tde_observer/docs/phase7b5n_preregistered_protocol|Phase 7B5n 新表示预注册与状态可行性失败]]；
- `outputs/phase7b5n_preregistered_protocol.json`：冻结的 1--2--4 表示、4816 预算和新留出；
- `outputs/phase7b5n_protocol_feasibility_failure.json`：预注册 $n=12$ 状态不存在且未改协议；
- [[eccentric_tde_observer/docs/phase7b5o_preregistered_protocol|Phase 7B5o 初始/收敛态预注册]]；
- [[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o 联合独立验证]]；
- `outputs/phase7b5o_summary.json`、`outputs/phase7b5o_validation_states.csv`、
  `outputs/phase7b5o_parent_choices.csv`：冻结候选、12 个新状态和父带选择；
- `outputs/phase7b5o_validation_errors.png`、`outputs/phase7b5o_hierarchy_allocation.png`、
  `outputs/phase7b5o_resource_costs.png`：联合误差、1--2--4 分配和英文成本图。
- [[eccentric_tde_observer/docs/phase7b5p_preregistered_resource_protocol|Phase 7B5p 隔离资源预注册]]；
- [[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p 隔离资源结果]]；
- `outputs/phase7b5p_resource_profile_summary.json`、
  `outputs/phase7b5p_isolated_resource_runs.csv`：10 个新进程的峰值、时间与完整性账本；
- `outputs/phase7b5p_isolated_resource_profile.png`：4816/9632 单单元峰值 RSS 与时间英文图。
- [[eccentric_tde_observer/docs/phase7b5q_preregistered_fixed_point_resource_protocol|Phase 7B5q 完整固定点资源预注册]]；
- [[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q 完整固定点资源结果]]；
- `outputs/phase7b5q_fixed_point_resource_summary.json`、
  `outputs/phase7b5q_fixed_point_resource_runs.csv`：两种初值、20 个新进程、收敛与资源账本；
- `outputs/phase7b5q_fixed_point_resource.png`：完整固定点单单元峰值和时间英文图。
- [[eccentric_tde_observer/docs/phase7b5r_preregistered_joint_convergence_protocol|Phase 7B5r 9632 组角度--辐射子网格预注册]]；
- [[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r 单单元联合失败结果]]；
- `outputs/phase7b5r_joint_convergence_summary.json`、
  `outputs/phase7b5r_joint_convergence_runs.csv`、
  `outputs/phase7b5r_joint_convergence_errors.csv`：七个固定点、连续量误差和失败判定；
- `outputs/phase7b5r_joint_convergence.png`：角度、子网格、联合误差与单单元资源英文图。
- [[eccentric_tde_observer/docs/phase7b5s_preregistered_refined_joint_protocol|Phase 7B5s 更细联合参考预注册]]；
- [[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s 更细联合失败结果]]；
- `outputs/phase7b5s_refined_joint_summary.json`、
  `outputs/phase7b5s_refined_joint_runs.csv`、
  `outputs/phase7b5s_refined_joint_errors.csv`：五个更细固定点、连续量误差和资源判定；
- `outputs/phase7b5s_refined_joint_convergence.png`：24/32/48 方向、32/64 子单元、联合误差与
  单单元资源英文图。
- [[eccentric_tde_observer/docs/phase7b5t_preregistered_characteristic_transport_protocol|Phase 7B5t 特征输运预注册]]；
- [[eccentric_tde_observer/docs/phase7b5t_characteristic_transport_gate|Phase 7B5t 单单元生产输运通过结果]]；
- `outputs/phase7b5t_characteristic_transport_summary.json`、
  `outputs/phase7b5t_characteristic_transport_runs.csv`、
  `outputs/phase7b5t_characteristic_transport_errors.csv`：解析、实际态、资源和正式接受判定；
- `outputs/phase7b5t_characteristic_transport_gate.png`：空间阶数、角边界、深度收敛和资源英文图。
- [[eccentric_tde_observer/docs/phase7b5u_preregistered_full_column_admission|Phase 7B5u 完整柱准入预注册]]；
- [[eccentric_tde_observer/docs/phase7b5u_full_column_admission|Phase 7B5u 完整柱资源与特征线审计]]；
- `outputs/phase7b5u_full_column_admission.json`、
  `outputs/phase7b5u_characteristic_phases.csv`、
  `outputs/phase7b5u_memory_arrays.csv`：完整柱形状、内存活跃集和逐相位反向节点；
- `outputs/phase7b5u_full_column_admission.png`：内存准入、反向相位和块宽资源英文图。
- [[eccentric_tde_observer/docs/phase7b5v_preregistered_streaming_turning_protocol|Phase 7B5v 流式与反向特征线预注册]]；
- [[eccentric_tde_observer/docs/phase7b5v_streaming_turning_gate|Phase 7B5v 严格失败结果]]；
- [[eccentric_tde_observer/docs/phase7b5w_preregistered_translation_invariant_remap|Phase 7B5w 平移不变搬移预注册]]；
- [[eccentric_tde_observer/docs/phase7b5w_translation_invariant_remap_gate|Phase 7B5w 平移不变搬移通过结果]]；
- `outputs/phase7b5w_translation_invariant_remap_summary.json`：逐位等价性、资源和授权判定；
- `outputs/phase7b5w_translation_invariant_remap_gate.png`：舍入修复、固定点等价和资源英文图。
- [[eccentric_tde_observer/docs/phase7b5x_preregistered_full_depth_block_probe|Phase 7B5x 整深度单块预注册]]；
- [[eccentric_tde_observer/docs/phase7b5x_full_depth_block_probe|Phase 7B5x 整深度单块实测]]；
- `outputs/phase7b5x_full_depth_block_probe_summary.json`：最坏块微物理、时间、RSS 和权限判定；
- `outputs/phase7b5x_full_depth_block_probe.png`：最坏块内存、时间和 halo 几何英文图。
- [[eccentric_tde_observer/docs/phase7b5y_remap_batch_performance|Phase 7B5y 大批次性能失败与回退]]；
- [[eccentric_tde_observer/docs/phase7b5z_lean_source_map|Phase 7B5z 精简中间源映射]]；
- [[eccentric_tde_observer/docs/phase7b6a_full_frequency_source_iteration|Phase 7B6a 完整全频单次源迭代]]；
- `outputs/phase7b6a_full_frequency_source_iteration_summary.json`：76 块覆盖、两进程资源和临时状态清理；
- `outputs/phase7b6a_full_frequency_source_iteration.png`：逐块时间、负载平衡、RSS 和总墙钟英文图。
- [[eccentric_tde_observer/docs/phase7b6b_relaxed_fixed_point|Phase 7B6b 无保护松弛失败]]；
- [[eccentric_tde_observer/docs/phase7b6c_guarded_relaxation|Phase 7B6c 整态正性保护]]；
- [[eccentric_tde_observer/docs/phase7b6d_full_depth_contraction|Phase 7B6d 最坏全深度块收缩]]；
- [[eccentric_tde_observer/docs/phase7b6e_extended_relaxation|Phase 7B6e 扩展固定权重失败]]；
- [[eccentric_tde_observer/docs/phase7b6f_full_frequency_contraction|Phase 7B6f 四次全频率收缩]]；
- [[eccentric_tde_observer/docs/phase7b6g_vector_aitken|Phase 7B6g 最坏块向量 Aitken]]；
- [[eccentric_tde_observer/docs/phase7b6h_full_frequency_aitken|Phase 7B6h 全频率 Aitken 续算]]；
- [[eccentric_tde_observer/docs/phase7b6i_recoverable_convergence_pause|Phase 7B6i 可恢复长续算暂停]]；
- [[eccentric_tde_observer/docs/phase7b6j_positivity_line_search|Phase 7B6j 正性边界线搜索]]；
- [[eccentric_tde_observer/docs/phase7b6k_anderson1|Phase 7B6k Anderson(1) 严格失败]]；
- [[eccentric_tde_observer/docs/phase7b6l_anderson2|Phase 7B6l Anderson(2) 终局局域门]]；
- [[eccentric_tde_observer/docs/phase7b6m_science_functionals|Phase 7B6m 科学泛函审计]]；
- [[eccentric_tde_observer/docs/phase7b6n_formal_face_flux|Phase 7B6n 正式 ALE 面通量复核]]；
- [[eccentric_tde_observer/docs/phase7b6o_fixed2_continuation|Phase 7B6o 16 次可恢复续算]]；
- [[eccentric_tde_observer/docs/phase7b6p_final_formal_flux|Phase 7B6p 最终正式面通量]]；
- [[eccentric_tde_observer/docs/phase7b6q_resource_recheck|Phase 7B6q 原架构资源复验]]；
- [[eccentric_tde_observer/docs/phase7b6r_worker_recycling|Phase 7B6r 短寿命工作进程终局门]]；
- [[eccentric_tde_observer/docs/phase7b7a_feedback_coefficients|Phase 7B7a 共动辐射反馈系数]]；
- [[eccentric_tde_observer/docs/phase7b7ar_resource_closure|Phase 7B7a-r 单块进程资源闭合]]；
- [[eccentric_tde_observer/docs/phase7b7b_material_response|Phase 7B7b 冻结辐射物质响应失败]]；
- [[eccentric_tde_observer/docs/phase7b7c_timescale_diagnosis|Phase 7B7c 表层响应时间尺度诊断]]；
- [[eccentric_tde_observer/docs/phase7b7d_trust_region_picard|Phase 7B7d 阻尼物质 Picard 方向]]；
- [[eccentric_tde_observer/docs/phase7b7e_radiation_direction|Phase 7B7e 全频辐射方向失败]]；
- [[eccentric_tde_observer/docs/phase7b7f_assembled_diagnostics|Phase 7B7f 全局拼接正式源项诊断]]；
- [[eccentric_tde_observer/docs/phase7b7fr_resource_closure|Phase 7B7f-r 一块一进程资源闭合]]；
- [[eccentric_tde_observer/docs/phase7b7g_assembled_atomic_rates|Phase 7B7g 全局拼接 H/He 原子率]]；
- [[eccentric_tde_observer/docs/phase7b7h_second_picard_direction|Phase 7B7h 第二固定时间层物质方向]]；
- [[eccentric_tde_observer/docs/phase7b7i_second_radiation_map|Phase 7B7i 第二全频辐射方向]]；
- [[eccentric_tde_observer/docs/phase7b7j_second_assembled_feedback|Phase 7B7j 全局正式反馈与固定点残差]]；
- [[eccentric_tde_observer/docs/phase7b7k_nonlinear_cost_decision|Phase 7B7k 朴素 Picard 成本决策]]；
- [[eccentric_tde_observer/docs/phase7b8a_protected_secant|Phase 7B8a 受保护逐单元割线提案]]；
- [[eccentric_tde_observer/docs/phase7b8b_secant_radiation_map|Phase 7B8b 割线提案全频辐射映射]]；
- [[eccentric_tde_observer/docs/phase7b8c_secant_feedback|Phase 7B8c 割线提案正式反馈与真残差失败]]；
- [[eccentric_tde_observer/docs/phase7b8d_feedback_line_search|Phase 7B8d 反馈感知受保护回溯]]；
- [[eccentric_tde_observer/docs/phase7b8e_backtracked_radiation_map|Phase 7B8e 回溯提案全频辐射映射]]；
- [[eccentric_tde_observer/docs/phase7b8f_backtracked_feedback|Phase 7B8f 回溯正式反馈与三重残差失败]]；
- [[eccentric_tde_observer/docs/phase7b9a_newton_krylov_component|Phase 7B9a 物理域 Newton--Krylov 组件门]]；
- [[eccentric_tde_observer/docs/phase7b9b_recoverable_full_frequency_residual|Phase 7B9b 可恢复全频残差与保真度门]]；
- [[eccentric_tde_observer/docs/phase7b9c_low_rank_preconditioner|Phase 7B9c 单实际割线低秩预条件器门]]；
- [[eccentric_tde_observer/docs/phase7b9d_inner_gate_audit|Phase 7B9d 基准辐射内迭代门审计]]；
- [[eccentric_tde_observer/docs/phase7b9e_science_functional_continuation|Phase 7B9e--7B9e2 基准辐射科学泛函续算]]；
- [[eccentric_tde_observer/docs/phase7b9f_converged_feedback_residual|Phase 7B9f 正式反馈与基准物质残差]]；
- [[eccentric_tde_observer/docs/phase7b9g_jv_fidelity_decision|Phase 7B9g 严格全频 Jv 保真度决策]]；
- [[eccentric_tde_observer/docs/phase7b9i_finite_trial_material|Phase 7B9i 有限受保护准 Newton 物质试探]]；
- [[eccentric_tde_observer/docs/phase7b9j_finite_trial_cost_decision|Phase 7B9j 有限试探内层辐射成本门]]；
- [[eccentric_tde_observer/docs/phase7b9k_block_aitken_pilot|Phase 7B9k 自然频率块 Aitken 失败门]]；
- [[eccentric_tde_observer/docs/phase7b9l_block_implicit_pilot|Phase 7B9l 代表块多次散射源迭代失败门]]；
- [[eccentric_tde_observer/docs/phase7b9m_exact_positive_mode_pilot|Phase 7B9m 精确正性单模外推终局失败门]]；
- [[eccentric_tde_observer/docs/phase7b9n_multimode_krylov_pilot|Phase 7B9n 未预条件多模 Krylov 失败门]]；
- [[eccentric_tde_observer/docs/phase7b9cu_dd_fixed_radiation_and_material_gate|Phase 7B9cu--7B9dd 固定物质辐射收敛与有限物质步物理域门]]；
- [[eccentric_tde_observer/docs/phase7b9de_half_trial_material|Phase 7B9de 第一次二分物质回溯候选]]；
- [[eccentric_tde_observer/docs/phase7b9dt_two_state_slow_mode_locator|Phase 7B9dt 两态慢模定位]]；
- [[eccentric_tde_observer/docs/phase7b9dv_closeout|Phase 7B9dv 固定物质辐射尾段收尾]]；
- [[eccentric_tde_observer/docs/phase7_post_convergence_branch_contract|Phase 7 后续分支决策合同]]；
- `outputs/phase7b9dt_two_state_slow_mode_locator.png`：逐块差分与慢模频率定位英文图；
- `outputs/phase7b9dv_closeout.png`：合并残差、收缩率与边界量收尾英文图；
- `outputs/phase7b9dv_closeout.json`：干净停止点、授权边界和客观限制机器账本；
- `outputs/phase7b6j_positivity_line_search_summary.json`：同起点分支残差、正性权重、资源和授权；
- `outputs/phase7b6j_positivity_line_search.png`：分支残差、权重、收益和墙钟成本英文图。
- `outputs/phase7b6k_anderson1.png`：深度一 Anderson、正性接受和失败门英文图；
- `outputs/phase7b6l_anderson2.png`：深度二 Anderson、Gram 条件数和失败门英文图；
- `outputs/phase7b6m_science_functionals.png`：体积谱、边界代理和光致电离代理英文图；
- `outputs/phase7b6n_formal_face_flux.png`：两次正式 ALE 面通量、门槛和运行成本英文图；
- `outputs/phase7b6o_fixed2_continuation.png`：16 次残差、边界泛函、成本和内存英文图；
- `outputs/phase7b6p_final_formal_flux.png`：第 29--30 次正式面通量与科学门英文图；
- `outputs/phase7b6q_resource_recheck.png`：逐位复现、原架构资源失败和成本英文图；
- `outputs/phase7b7a_feedback_coefficients.png`：共动率积分、四力、光致率和镜面对称英文图；
- `outputs/phase7b7ar_resource_closure.png`：单块逐位复现、内存和运行成本英文图；
- `outputs/phase7b7b_material_response.png`：未接受温度候选、信赖域和布居响应英文图；
- `outputs/phase7b7c_timescale_diagnosis.png`：表层响应时间、质量集中和吸收--发射抵消英文图；
- `outputs/phase7b7d_trust_region_picard.png`：阻尼物质方向、信赖域和守恒英文图；
- `outputs/phase7b7e_radiation_direction.png`：一次辐射方向、物质残差收缩和资源英文图；
- `outputs/phase7b7f_assembled_diagnostics.png`：旧 halo 与全局拼接源项、深度和门槛英文图；
- `outputs/phase7b7fr_resource_closure.png`：逐位复现、短寿命进程资源和科学门英文图；
- `outputs/phase7b7g_assembled_atomic_rates.png`：光致率、复合系数、加热复现和资源英文图；
- `outputs/phase7b7h_second_picard_direction.png`：第二固定时间层物质方向、信赖域和时间基准英文图；
- `outputs/phase7b7i_second_radiation_map.png`：第二全频方向、进程资源和诊断边界英文图；
- `outputs/phase7b7j_second_assembled_feedback.png`：三条正式源项、固定点残差和 H/He 率英文图；
- `outputs/phase7b7k_nonlinear_cost_decision.png`：实测收缩、成本外推和算法决策英文图；
- `outputs/phase7b8a_protected_secant.png`：物质割线提案、逐单元系数、廉价残差和范围英文图；
- `outputs/phase7b8b_secant_radiation_map.png`：全频辐射方向、短进程资源和验证范围英文图；
- `outputs/phase7b8c_secant_feedback.png`：正式源项、真残差、H/He 率和失败门英文图；
- `outputs/phase7b8d_feedback_line_search.png`：回溽物质态、端点残差预测和候选步长英文图；
- `outputs/phase7b8e_backtracked_radiation_map.png`：回溯全频辐射方向、资源与范围英文图；
- `outputs/phase7b8f_backtracked_feedback.png`：正式源项、三重真残差和 H/He 率英文图；
- `outputs/phase7b9a_newton_krylov_component.png`：四分量实际残差、Newton 历史、制造非局域控制和成本英文图；
- `outputs/phase7b9b_recoverable_residual_interface.png`：可恢复状态机、保真度、文件完整性控制和方向性成本下界英文图；
- `outputs/phase7b9c_low_rank_preconditioner.png`：实际割线、跨深度低秩修正、信赖域几何和制造 GMRES 控制英文图；
- `outputs/phase7b9d_inner_gate_audit.png`：无效旧账本、第一轮科学泛函和审计决策英文图；
- `outputs/phase7b9e_science_functional_continuation.png`：原预算内源变化、边界泛函、旧账本和资源英文图；
- `outputs/phase7b9e2_science_functional_extension.png`：两轮独立扩展与连续通过区英文图；
- `outputs/phase7b9f_converged_feedback_residual.png`：正式 H/He 率、三路加热、基准残差和最后两态门英文图；
- `outputs/phase7b9g_jv_fidelity_decision.png`：差分信噪、资源敏感性和严格 Jv 决策英文图；
- `outputs/phase7b9i_finite_trial_material.png`：有限候选温度、H II 分数和信赖域英文图；
- `outputs/phase7b9j_finite_trial_cost_decision.png`：候选辐射实测收缩、边界泛函、成本外推和暂停边界英文图；
- `outputs/phase7b9k_block_aitken_pilot.png`：自然块 Aitken 残差、块权重、边界泛函和失败决策英文图；
- `outputs/phase7b9l_block_implicit_pilot.png`：六个代表块内部收缩、边界稳定、成本和失败决策英文图；
- `outputs/phase7b9m_exact_positive_mode_pilot.png`：精确正性权重、新原算子残差、成本和终局决策英文图；
- `outputs/phase7b9n_multimode_krylov_pilot.png`：子空间条件数、预言、新原算子验证和失败决策英文图；
- `outputs/phase7b9cu_protected_anderson_tail.png`：受保护 Anderson 慢模候选和预测残差英文图；
- `outputs/phase7b9cv_candidate_fresh_map.png`：第一次 fresh-map 真实残差、边界和资源英文图；
- `outputs/phase7b9cw_consecutive_confirmation.png`：第二个连续收敛态与边界确认英文图；
- `outputs/phase7b9dd_material_trial_rejection.png`：正式 H/He 反馈稳定性与物理域拒绝英文图；
- `outputs/phase7b9de_half_trial_material.png`：温度、布居位移和候选授权边界英文图；
- `outputs/phase7b6r_worker_recycling.png`：短寿命进程内存、科学门和两批成本英文图。

本阶段没有产生可接受的实际 atmosphere spectrum：官方 TLUSTY 208 H/He LTE/NLTE 控制
通过，但实际代表柱接受数为 0/12。灰初值没有用于替代 modified-blackbody。Phase 7B1
随后完成动态数值底座，并在 Phase 7B2 回收一维转移解析极限。Phase 7B3 已加入可追溯的
H/He 基态光致电离、总辐射复合与静态 opacity 耦合；Phase 7B4a 又加入碰撞电离、详细
平衡三体逆率和固定背景松弛；Phase 7B4b 已在规定 ZO 周期中面完成无辐射、电荷自洽的
轨道率推进。其动力学解紧跟瞬时无辐射稳态，但该稳态与 LTE 的巨大差异直接说明缺失的
辐射逆过程不可忽略；Phase 7B4c 已加入规定 Planck 场并通过零场与热详细平衡；Phase
7B4d 又在固定 $T,\rho$ 受照板层中完成 $J_{\nu}$--基态布居--opacity 固定点；Phase 7B4e
再闭合同截面基态 Milne 连续发射、Kirchhoff/LTE、光子率和固定温度能量账本；Phase 7B4f
已联立逐深度温度并发现完整近心点单面耗散在当前薄层中无根；Phase 7B4g 随后在有限柱中
找到稳定静态根，并用 Compton 与线完全逃逸边界确认连续谱相对局域黑体差异大；Phase 7B4h
再加入 ZO 约束密度柱、中面对称边界与两种受控耗散律。静态热根存在，但全部 12 个代表柱
均要求 $H_{\rm static}/H_{\rm ZO}=0.292$--$0.356$，所以保持 ZO 几何的静力表未通过。
Phase 7B4i 已进一步联立有限步压缩功、规定耗散、H/He 基态电离能和 Rosseland 扩散，
周期能量账本闭合到约 $10^{-12}$。Phase 7B4j 随后加入共享轨道的自适应质量网格并把时间
参考提高到 1024 相位；自适应 16 单元逐点人口误差仍为 $0.05576$，512 对 1024 相位人口
误差仍为 $1.281\times10^{-3}$。Phase 7B4k 的 12/24 单元双网格估计没有消除逐点前沿与
柱积分的空间权衡，但 1024 对 2048 相位的温度/能流与人口误差已分别降到
$2.418\times10^{-4}$ 和 $3.991\times10^{-4}$，时间门通过。Phase 7B4l 的守恒子单元使制造
前沿误差改善约 $1.9$ 倍，且柱积分和前沿位置在 32 有效深度时通过；但逐点
$T/\kappa_{\rm R}$ 与人口误差仍为 $1.520\times10^{-2}$、$0.1132$。Phase 7B4m 随后用
pilot 嵌入式守恒缺陷选择可变真实自由度；排序与独立实际误差的 Spearman 相关为 $0.9912$，
N=60、62 已通过对有限 N=64 参考的空间门。Phase 7B4n 又完成 64×1024 联合有限参考，
并确认 1024 相位下 N=62 对 N=64 的空间门继续通过；Phase 7B4o 随后独立完成 64×2048，
1024 对 2048 的最大逐点人口差为 $2.887\times10^{-4}$，全部联合时间指标通过。Phase
7B4p 又完成冻结全轨道非局域形式解；7B4q--7B4r 随后关闭阈值求积、分离辐射深度和
N128×2048 物质时间门，7B4s--7B4u 再依次关闭隐式 ALE 核、Lorentz 频率组组件与静态
H/He 多群连续系数门。7B4v 已把完整 Lorentz 物质源与 ALE 写入同一残差，解析平衡、
$\beta\tau=2$ 动态扩散四力和能量账本均通过；但 1205 组真实动态原子率最大误差为
$1.2829\times10^{-2}$。7B4w 的阈值局域 P0 在 18105 组通过三状态 $10^{-3}$ 精度门，
却超过 4814 组效率上限。7B4x 的普通对数 P1 和 7B4y 的阈值局域 P1 在预算边界的
最大宽度变化误差仍分别为 $2.4547\times10^{-3}$ 和 $3.4545\times10^{-3}$。7B4z 的
普通对数 P2 改善最大速度状态，但最大宽度变化/H I 率仍为
$2.5472\times10^{-3}$，且保留 limiter 相关的算子失败点；生产频率表示仍未选定。
7B5j--7B5k 已确认 9632/19264 组有限 P0 参考，7B5l 又关闭守恒多分辨率组件门；但
7B5m 的冻结 4814 叶网格在独立最大宽度变化 $n=8$ 留出状态得到
$1.003468\times10^{-3}$，严格未过 $10^{-3}$。组数预算满足而完整效率门失败，验证集
没有用于重训。7B5n 随后因预注册 $n=12$ 状态不存在而在协议可行性门关闭；7B5o 用六个
全新病例的初始/收敛态完成联合验证，9632 master 全部门通过，4816 叶候选则在 He II
以 $1.000546\times10^{-3}$ 严格失败。生产表示仍未选择。[A/V/O]
7B5p 随后冻结这一最坏状态并各运行 5 个全新子进程；9632 的中位/最大单单元进程峰值为
$190.44/191.50\,\mathrm{MiB}$，增量内存和单步时间分别约为 4816 的 $2.04/1.94$ 倍。
它关闭资源测量门，但没有修改预算或给出全柱峰值。[A/V/O]
7B5q 又把同一审计扩展到完整固定点；两种表示从投影收敛源/默认初值分别经过 29/43 次
迭代收敛，9632 的最高峰值为 $209.44\,\mathrm{MiB}$，跨初值最终强度差约
$2\times10^{-10}$。它仍不构成角度、子网格或全柱门。[A/V/O]
7B5r 在用户批准 9632 新预算后运行 8/16/24 方向及 8/16/32 辐射子单元；所有固定点
完整性门通过，但 16/24 方向、16/32 子单元和联合门分别以
$5.448\times10^{-3}$、$1.482\times10^{-2}$、$9.589\times10^{-3}$ 失败。24×32 峰值
为 $1046.47\,\mathrm{MiB}$，生产角度--深度配置保持为空。[A/V/O]
7B5s 再加密到 24/32/48 方向和 32/64 子单元；32/48 方向、32/64 子单元和联合
32×32/48×64 的最大误差分别为 $1.221\times10^{-3}$、$7.626\times10^{-3}$、
$6.428\times10^{-3}$。48×64 峰值为 $2876.00\,\mathrm{MiB}$，资源门通过，但科学门
全部失败；当前主要瓶颈是辐射深度离散。[A/V/O]
7B5t 随后以解析板层确认旧迎风为一阶，并采用特征分区角求积与守恒单元特征积分。角度、
16/32 深度、32/64 深度和联合误差全部低于 $1.74\times10^{-4}$；正式接受 9632 组、
32 方向、16 子单元的单单元生产配置。[A/V/O]
7B5u 再把该配置映射到正式 4096 深度完整柱；单强度数组为 $9.406\,\mathrm{GiB}$，
当前算子已识别活跃集至少 $84.668\,\mathrm{GiB}$，整体路径不准入。2048 相位中另有
586 个相位的两个掠射方向反向；下一门必须同时做流式分块和守恒 turning-ray 处理。
[A/V/O]
激发态、总复合级联、全轨道动态转移与
物质反馈仍然缺失，所以结果仍不能升级成动态 NLTE 输出谱或 Phase 4 替换表。
`[V/O]`

## 核心理论论文

- [[markdown_papers/2009.06636v2|Zanazzi & Ogilvie 2020：偏心 TDE 盘动力学与热辐射]]：
  项目源模型；
- [[markdown_papers/1812.05942v1|Ogilvie & Lynch 2019：偏心盘 Hamiltonian 流体力学]]：
  嵌套轨道、Jacobian、三维呼吸和一致进动理论；
- [[markdown_papers/2011.02219v1|Lynch & Ogilvie 2021：高偏心盘动态结构]]：
  非绝热垂向结构、应力与近心点动态失效；
- [[markdown_papers/2101.01221v1|Lynch & Ogilvie 2021：高偏心盘磁场]]：
  磁场与高偏心呼吸的开放问题。

## 辐射转移和大气论文

- [[markdown_papers/Cunningham_1975_ApJ_202_788|Cunningham 1975：相对论盘传递函数]]
- [[markdown_papers/astro-ph_0602499|Davis & Hubeny 2006：非 LTE annulus 表]]
- [[markdown_papers/1510.08454v1|Roth et al. 2016：TDE X-ray 到 optical 转移]]
- [[markdown_papers/Dai_et_al_2018_A_Unified_Model_for_TDEs|Dai et al. 2018：TDE 观察方向统一图景]]
- [[markdown_papers/Roth_Kasen_2018_What_Sets_the_Line_Profiles_in_TDEs|Roth & Kasen 2018：TDE 线轮廓形成]]：只用于界定连续谱项目与线转移问题的边界，不用于本项目拟合。

## 观测联系论文

- [[markdown_papers/2202.08268v2|Wevers et al. 2022：AT 2020zso 椭圆发射区]]
- [[markdown_papers/Charalampopoulos_et_al_2022_A_Detailed_Spectroscopic_Study_of_TDEs|Charalampopoulos et al. 2022：TDE 光谱演化样本]]

## 纳入清单但不作为本项目依据

- [[markdown_papers/2601.22388v1|黑洞并合最大熵猜想]]：文件位于 `markdown_papers`，但主题是
  黑洞并合，和本项目源模型、连续谱转移及 TDE 观测没有直接关系；讲义不得引用它支持
  TDE 结论。

## 直接相关的后续调研笔记

- [[deep-research-report/deep-research-report|Steinberg 与 Stone 之后的 TDE 圆化、偏心流与方法演进]]：
  用于最终研究路线讨论，不回写为本项目已验证结论。
