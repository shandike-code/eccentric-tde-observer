# ZO 偏心 TDE 盘到观察者光谱：项目讲义入口

本目录用于解释 `/eccentric_tde_observer` 项目“做了什么、为什么这样做、哪些结果可信、
哪些仍未知”。它不是阶段报告的简单拼接。当前代码检查点已完成 Phase 5A 的观察者系
$F_{\lambda}$ 映射、Phase 5B1 的 $e\to0$ 线性自由边界拱点本征模门、Phase 5B2 的
三维非线性局域 Hamiltonian 与偏导门、Phase 6 的
corrected ZO 条件性谱线响应、Phase 7A 的静态 H/He 环带
可行性审计、Phase 7B1 的规定背景周期柱与守恒布居控制、Phase 7B2 的一维频率--角度
转移解析控制、Phase 7B3 的可追溯 H/He 连续谱原子率与静态耦合、Phase 7B4a 的
碰撞电离与固定背景松弛、Phase 7B4b 的无辐射电荷自洽轨道推进，以及 Phase 7B4c 的规定
Planck 场与逐相位光致电离耦合；Phase 7B4d 已闭合固定板层的 $J_{\nu}$--布居--opacity
反馈，Phase 7B4e 又完成同截面基态 Milne 连续发射与固定温度能量账本；Phase 7B4f 已
联立逐深度温度、根拓扑和热稳定性，并发现完整近心点耗散在当前薄控制层中无根；Phase
7B4g 进一步扫描有限沉积柱，得到稳定静态根并判定连续谱相对局域黑体差异大；Phase 7B4h
随后加入 ZO 约束的有限密度柱、中面对称边界和两种受控耗散律。静态热根存在，但 12 个
代表柱都要求 $H_{\rm static}/H_{\rm ZO}=0.292$--$0.356$，未通过保持 ZO 几何的静力表
准入门。Phase 7B4i 已建立含压缩功、基态电离能和 Rosseland 扩散的周期动态半柱，周期
能量、电荷和粒子数闭合；Phase 7B4j 又建立共享轨道的自适应拉格朗日质量网格并把时间审计
提高到 1024 相位点。自适应网格改善逐点前沿却恶化柱平均量，16 对 24 单元逐点人口误差
仍为 $0.05576$；512 对 1024 相位人口误差仍为 $1.281\times10^{-3}$。Phase 7B4k 的双网格
误差估计仍未使逐点前沿和柱积分同时收敛，但 1024 对 2048 相位的温度/能流与人口误差已降到
$2.418\times10^{-4}$ 和 $3.991\times10^{-4}$，时间门通过。Phase 7B4l 已补上守恒线性
子单元、物理域限制和总比能温度反演；制造前沿误差约改善
$1.9$ 倍，但 32 对 64 有效深度的逐点人口误差仍为 $0.1132$，空间门未通过。Phase 7B4m
随后用 N=32 pilot 的嵌入式守恒缺陷排序可变子单元；排序对独立 N=64 有限参考的
Spearman 相关为 $0.9912$，N=60 与 N=62 通过 $10^{-3}$ 空间门。Phase 7B4n 已完成
64×1024 联合有限参考；1024 相位下 N=62 对 N=64 的空间门继续通过，但 N=64 的 512 对
1024 最大 He III 差为 $1.087\times10^{-3}$，高深度时间门轻微失败。Phase 7B4o 随后
独立完成 N=64、2048 相位参考；1024 对 2048 最大逐点人口差降为
$2.887\times10^{-4}$，全部联合时间指标通过。Phase 7B4p 随后完成冻结非局域形式解；
形式解守恒和时间轴通过，但正式角度、频率、深度和准静态门失败。263 对 519 频点的最大
速率差仍为 $0.3688$，且 $\max(t_{\rm diff}/P_{\rm orb})=0.7379$。Phase 7B4q 已完成
阈值显式正权求积、独立 N128×1024 动态物质参考和辐射子网格；每物质单元 16 对 32
子单元、160 对 304 频率节点和 16 对 24 角阶均通过。Phase 7B4r 又独立完成
N128×2048；1024 对 2048 最大逐点人口差为 $2.911\times10^{-4}$，全部联合时间指标
通过且前沿状态零错配。Phase 7B4s 已进一步实现隐式 ALE 辐射储能核，并在 N128×2048
物质轨道上完成 10/60 eV 双频周期 pilot；第二周期逐位闭合，最大能量账本残差为
$1.424\times10^{-9}$。Phase 7B4t 随后实现完整 Lorentz 射线关系、阈值对齐守恒
频率组和正性批量源迭代。153 个物理组的实际呼吸控制略微失败，303 组以
$7.735\times10^{-4}$ 通过；最大系统 $\beta\tau=6.554\times10^{3}$，因此未经验证的
一阶速度展开被否决。Phase 7B4u 又在 168 个真实 N128×2048 物态上检验组平均连续系数、
Milne 发射、光致率、复合率和净加热。604 组以 $1.0093\times10^{-3}$ 轻微失败，1205 组
以 $2.5271\times10^{-4}$ 通过。Phase 7B4v 随后把完整 Lorentz 碰撞源与 ALE 储能和
移动界面通量写入同一后向 Euler 残差。零速度、刚体平移、同源呼吸和
$\beta\tau=2$ 动态扩散四力控制均通过；但 1205 组在三个真实一步物态上的最大动态
原子率误差为 $1.2829\times10^{-2}$，生产频率表示没有通过。19249 组仅相对 38496 组
有限单元参考通过，未获生产选择。Phase 7B4w 随后测试 H/He 阈值局域有限体积 P0 网格；
几何、移动热平衡和算子控制通过，三个真实一步状态首次同时低于 $10^{-3}$ 时需 18105 个
物理组，超过预声明的 4814 组效率上限。Phase 7B4x 随后实现普通对数 P1，2408 组的
最大宽度变化误差仍为 $2.4547\times10^{-3}$；Phase 7B4y 再联合阈值局域边界和 P1，
2265 组误差为 $3.4545\times10^{-3}$，没有优于普通 P1。Phase 7B4z 的 P2 在 4812
自由度下仍保留 $2.5472\times10^{-3}$；Phase 7B5a 又把 $Q=\nu I_{\nu}$ 放在真正的
$y=\ln\nu$ 守恒坐标上，但最高预算误差仍为 $2.4569\times10^{-3}$，与普通 P1 实质
相同。Phase 7B5b 再按 H I 率核重分配固定网格；三档聚焦比例的网格、移动平衡和实际
算子门都通过，但最高预算决定性误差仍为 $2.1329\times10^{-3}$--
$5.6739\times10^{-3}$，无一通过。Phase 7B5c 又把移动状态主差定位到
$13.60$--$13.71\ {\rm eV}$ H I Doppler 阈值带，但最冷表层主导于 H I shoulder；
末态压缩误差仅约 $10^{-12}$--$10^{-10}$，动态余项主导。Phase 7B5d 再排除 ALE
宽度和散射单项，并把瓶颈缩小到 Lorentz--真实连续碰撞交互。Phase 7B5e 的 Lorentz
分量控制中，只有完整算子与 no intensity 三态通过；后者使两个移动误差降至完整值的
$1.424\%$/$1.331\%$，而消光/发射率关闭因残差失败不能用于因果分类。
Phase 7B5f 又证明同一解析输入的一次强度搬移 H I 率差仅为
$3.17\times10^{-8}$--$2.38\times10^{-7}$。Phase 7B5g 的固定点截面进一步显示最大速度
与最大宽度分别到第 2/8 次才超过最终误差的 $50\%$。Phase 7B5h 再用同一输入单步账本
证明两个移动状态中，新注入分量最低仍占绝对分量和的 $95.3\%$，已有误差传播不是主因；
Phase 7B5i 又证明 2408 组频率分区项稳定占 $60.1\%$--$64.3\%$，但同分区 P1--P0
项仍占约 $36\%$--$40\%$，4816 组同成本 P0 也保留两个失败截面。下一门审计预声明的
非拟合频率分区。Phase 7B5j 已完成该审计：预算内三种 P0 分区均失败；率核与 Doppler
锚点仅在 9632 组通过，普通对数仍失败，且锚点没有稳定优选。Phase 7B5k 已完成
19264 组相邻复算：两种非均匀 P0 分区均在 9632/19264 组连续通过，确认有限高分辨率
参考；但原 4816 组效率门仍失败，资源证据也不构成改预算授权。下一门设计封闭局域
多分辨率压缩。Phase 7B5l 已关闭该组件门：严格嵌套、P0 守恒传递、能量/H/He 联合
排序和 4816 叶账本均通过；但解析控制谱不替代独立动态验证。Phase 7B5m 已按预声明
$n=0,2,4$ 训练、$n=1,8$ 留出协议冻结 4814 叶网格。训练集全部通过，但最大宽度变化
的 $n=8$ 留出误差为 $1.003468\times10^{-3}$，严格高于 $10^{-3}$；9632 组 master
在同一点为 $8.95887\times10^{-4}$。Phase 7B5n 的新预注册协议因一个病例在
$n=11$ 已收敛、所需 $n=12$ 状态不存在而原样失败，没有事后换点。Phase 7B5o 随后
排除已打开病例，用六个全新几何病例的初始态和参考收敛态检验精确 4816 叶层级 P0；
协议、参考源、完整算子与 9632 master 联合门通过，但候选 He II 最坏误差为
$1.000546\times10^{-3}$，仍严格失败。生产表示尚未选定，修改为 9632 组预算需要
明确授权。Phase 7B5p 已补测 10 个隔离单单元进程：9632 的中位/最大峰值 RSS 为
$190.44/191.50\,\mathrm{MiB}$，算子增量内存与单步时间约为 4816 的 $2.04/1.94$ 倍；
Phase 7B5q 随后完成完整固定点包络：两种初值需 29/43 次迭代，9632 所有运行的最高峰值
为 $209.44\,\mathrm{MiB}$，跨初值最终强度差约 $2\times10^{-10}$。用户随后批准 9632
新预算；Phase 7B5r 的 16/24 方向、16/32 子单元和联合门分别以
$5.448\times10^{-3}$、$1.482\times10^{-2}$、$9.589\times10^{-3}$ 失败。频率预算
已采用，角度--深度生产配置为空。Phase 7B5s 又将参考加密到 24/32/48 方向和 32/64
子单元；32/48 方向、32/64 子单元和联合 32×32/48×64 仍分别以
$1.221\times10^{-3}$、$7.626\times10^{-3}$、$6.428\times10^{-3}$ 失败。资源门通过，
但辐射深度离散仍是主瓶颈。Phase 7B5t 已用特征分区角求积和守恒单元特征积分关闭该门：
角度、16/32 深度、32/64 深度和联合误差均低于 $1.74\times10^{-4}$，正式接受 9632 组、
32 方向、16 子单元的单单元配置。Phase 7B5u 随后审计正式完整柱：当前整体实现的活跃
数组下界为 $84.668\,\mathrm{GiB}$，并有 586/2048 个相位的两个最掠射方向发生特征反向。
Phase 7B5v 已关闭 turning-ray 与固定点门，但单次流式映射以
$3.93775\times10^{-12}$ 严格失败 $10^{-12}$ 门；Phase 7B5w 改用平移不变局域交叠后，
正式单次映射和最终固定点均与整体路径逐位相同，stream256 峰值为 392.08 MiB。下一门
的 7B5x 已实测最坏 4096 深度块：峰值为 2863.14 MiB，总时间 10.83 s，其中单次源
映射为 9.66 s。7B5y 的大批次候选失败并回退；7B5z 的精简中间源映射保持输出逐位相同，
把最坏块算子中位时间降到 6.137 s。7B6a 再用两进程完成全部 9632 组的一次映射，墙钟
244.88 s、每进程峰值约 2.9 GiB，但最大变化仍为 0.282899。完整算子组件已闭合，但全轨道
动态连续谱和物质反馈仍未实现；
激发态总复合级联也仍未实现，
故物理 X-ray、高偏心源的绝对进动周期、真实
仪器响应、动态 NLTE 谱和绝对原子线光度仍未完成。

独立的拱点本征值支路已推进到 Phase 5B3d：期刊、Crossref、arXiv v2 源包、GitHub 与
Zenodo 都没有给出 Fig. 6/7 的公开求解器或原始数组；论文要求向通讯作者合理请求。项目
已于 2026-08-30 按授权发送
[[eccentric_tde_observer/docs/zo2020_author_source_request_draft|唯一一封作者请求]]，当前
等待回复，因此 $\Phi\mapsto t$ 仍未授权。`[L/V/O]`

## 推荐阅读顺序

1. [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]：从物理问题到代码与结果的
   逻辑闭环；
2. [[eccentric_tde_observer/lecture/项目讲义/00_document_map|Markdown 文档地图]]：查找每个阶段页和
   本地论文；
3. [[eccentric_tde_observer/docs/phase5a_observer_frame_flambda|Phase 5A 报告]]与
   [[eccentric_tde_observer/docs/phase6_line_response|Phase 6 报告]]：观察者系连续谱和条件性
   运动学线核的边界；
4. [[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1 报告]]：线性
   拱点本征模的独立强--弱验证、自由边界和 Eq. (48) 物理尺度开放问题；
5. [[eccentric_tde_observer/docs/phase5b2_nonlinear_hamiltonian_gate|Phase 5B2 报告]]：如何
   从 $(e,f)$ 逐点求三维呼吸、Hamiltonian 和稳定偏导，并保留全局模边界；
6. [[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|Phase 5B3d 报告]]：
   为什么当前公开入口不足以复现 published Fig. 6/7，以及作者请求的权限边界；
6. [[eccentric_tde_observer/docs/phase7a_static_annulus|Phase 7A 报告]]：为什么当前静态 H/He
   求解尚未给出可替代 modified-blackbody 的实际谱；
5. [[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 报告]]：如何建立完整轨道
   背景、守恒周期率方程和解析时标控制；
6. [[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 报告]]：如何逐项回收
   真空、纯吸收、保守散射和时间静态极限；
7. [[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 报告]]：如何从文献原子
   数据建立阈值分段、守恒电离稳态、静态 transfer 耦合，并保留 NLTE 边界；
8. [[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a 报告]]：如何加入
   碰撞电离、构造三体详细平衡、验证固定松弛和审计 ZO 中面时标；
9. [[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 报告]]：如何在
   周期 ZO 中面自洽更新电荷，并区分微小时间滞后与巨大的缺失辐射效应；
10. [[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c 报告]]：
    如何把规定场转成逐相位光致率，并验证零场、热详细平衡和稀释敏感性；
11. [[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d 报告]]：如何关闭固定板层
    $J_{\nu}$--基态布居--opacity 固定点并检验初态和分层收敛；
12. [[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e 报告]]：如何用同一
    基态截面构造 Milne 率与连续发射，并验证 Kirchhoff、光子率和固定温度能量账本；
13. [[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f 报告]]：如何联立
    逐深度温度、识别稳定根/无根，并把完整耗散无根限制在明确薄层边界内；
14. [[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 报告]]：如何
    扫描有限耗散柱、分别打开 Compton/线边界并据连续谱差异选择静力大气表路线；
15. [[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 报告]]：如何
    构造有限静力柱、检验两种耗散律并据厚度失配切换到周期动态路线；
16. [[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 报告]]：如何
    联立周期能量与基态人口，并区分守恒基础通过和生产分辨率未通过；
17. [[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase 7B4j 报告]]：如何
    构造共享轨道的自适应质量网格，并区分逐点、柱平均和时间收敛；
18. [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 报告]]：如何
    用嵌套双网格误差构造监视函数，并区分通过的时间门和失败的深度门；
19. [[eccentric_tde_observer/docs/phase7b4l_conservative_subcell_reconstruction|Phase 7B4l 报告]]：
    如何保守延拓总比能与 H/He 人口，并区分通过的积分量和失败的逐点空间门；
20. [[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 报告]]：
    如何用独立 pilot 缺陷选择真实变量自由度并关闭有限空间门；
21. [[eccentric_tde_observer/docs/phase7b4n_joint_depth_time_reference|Phase 7B4n 报告]]：
    如何建立三色 Jacobian、整周期检查点和联合参考，并保留轻微失败的 He III 时间门；
22. [[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o 报告]]：
    如何用独立 64×2048 周期解关闭高深度时间门，并保留有限参考边界；
23. [[eccentric_tde_observer/docs/phase7b4p_frozen_nonlocal_transfer|Phase 7B4p 报告]]：
    如何用冻结形式解审计局域 Planck 闭合、四条数值轴和准静态辐射门；
24. [[eccentric_tde_observer/docs/phase7b4q_threshold_quadrature|Phase 7B4q 报告]]：
    如何关闭阈值求积并分离动态物质网格与辐射转移子网格；
25. [[eccentric_tde_observer/docs/phase7b4r_n128_time_reference|Phase 7B4r 报告]]：
    如何用独立 N128×2048 参考关闭有限物质时间门并保留动态辐射边界；
26. [[eccentric_tde_observer/docs/phase7b4s_implicit_ale_radiation|Phase 7B4s 报告]]：
    如何用隐式 ALE 核保留辐射储能、验证移动网格守恒并界定速度项缺口；
27. [[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t 报告]]：
    如何用完整 Lorentz 关系、守恒频率组和正性迭代关闭组件门，并保留联立算子边界；
28. [[eccentric_tde_observer/docs/phase7b4u_multigroup_continuum_gate|Phase 7B4u 报告]]：
    如何在真实物态上关闭 H/He 多群连续系数门，并从 604 组切换到 1205 组候选；
29. [[eccentric_tde_observer/docs/phase7b4v_mixed_frame_ale_gate|Phase 7B4v 报告]]：
    如何联立完整 Lorentz 碰撞源与 ALE，并区分通过的算子门和失败的 1205 组动态原子率门；
30. [[eccentric_tde_observer/docs/phase7b4w_threshold_frequency_groups|Phase 7B4w 报告]]：
    如何构造阈值局域有限体积组，并区分 18105 组精度通过与 4814 组效率失败；
31. [[eccentric_tde_observer/docs/phase7b4x_p1_frequency_moments|Phase 7B4x 报告]]：
    如何构造守恒可实现 P1，并保留普通对数 P1 的残差与三状态频率失败；
32. [[eccentric_tde_observer/docs/phase7b4y_threshold_p1_gate|Phase 7B4y 报告]]：
    如何联合阈值局域边界与 P1，并证明它未在预算内优于普通 P1；
33. [[eccentric_tde_observer/docs/phase7b4z_p2_frequency_moments|Phase 7B4z 报告]]：
    如何构造守恒可实现 P2，并区分最大速度改善、最大宽度变化失败与 limiter 算子风险；
34. [[eccentric_tde_observer/docs/phase7b5a_log_frequency_p1_gate|Phase 7B5a 报告]]：
    如何用 $Q=\nu I_{\nu}$ 保持对数频率积分与 Doppler 平移，并证明只改坐标仍未过门；
35. [[eccentric_tde_observer/docs/phase7b5b_rate_kernel_grid_gate|Phase 7B5b 报告]]：
    如何用 H I 率核分配固定网格，并区分算子通过、频率失败与不事后挑选聚焦比例；
36. [[eccentric_tde_observer/docs/phase7b5c_signed_rate_error_localization|Phase 7B5c 报告]]：
    如何定位有符号 H I 率差，并区分末态谱压缩与动态余项；
37. [[eccentric_tde_observer/docs/phase7b5d_dynamic_operator_controls|Phase 7B5d 报告]]：
    如何用匹配候选/参考的一因子控制定位 Lorentz--真实连续碰撞交互；
38. [[eccentric_tde_observer/docs/phase7b5e_lorentz_component_controls|Phase 7B5e 报告]]：
    如何区分可接受的强度响应与未闭合的消光/发射率关闭控制；
39. [[eccentric_tde_observer/docs/phase7b5f_single_pass_intensity_transform|Phase 7B5f 报告]]：
    如何把单次强度搬移与隐式碰撞反馈累积分开；
40. [[eccentric_tde_observer/docs/phase7b5g_fixed_point_feedback_audit|Phase 7B5g 报告]]：
    如何定位固定点误差增长、阈值区迁移和两个移动状态的起始检查点；
41. [[eccentric_tde_observer/docs/phase7b5h_recurrence_decomposition|Phase 7B5h 报告]]：
    如何逐位复现单步映射并分离同输入注入与已有误差传播；
42. [[eccentric_tde_observer/docs/phase7b5i_partition_representation_split|Phase 7B5i 报告]]：
    如何分离频率分区与同分区 P1--P0 项并检验同成本 P0；
43. [[eccentric_tde_observer/docs/phase7b5j_prescribed_partition_audit|Phase 7B5j 报告]]：
    如何比较三种非拟合分区并保留预算内失败；
44. [[eccentric_tde_observer/docs/phase7b5k_high_resolution_convergence|Phase 7B5k 报告]]：
    如何确认相邻高分辨率收敛并区分返回数组占用与峰值内存；
45. [[eccentric_tde_observer/docs/phase7b5l_multiresolution_component_gate|Phase 7B5l 报告]]：
    如何构造严格嵌套 P0 层级、联合指标和闭合叶预算；
46. [[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|Phase 7B5m 报告]]：
    如何冻结训练网格、隔离留出状态并严格保留极窄失败；
47. [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]：当前检查点后的深度调研
   与可执行计划；
48. [[eccentric_tde_observer/lecture/AI任务简报/phase5_literature_package|第五阶段文献包]]：下一步观测
   算子、进动时序、人口比较和 NLTE 扩展所需的新增 PDF/Markdown 入口。

## 规范

所有双链、证据标签、单位与页面角色遵守
[[eccentric_tde_observer/docs/obsidian_linking_standard|Obsidian 双链与讲义文档规范]]。
