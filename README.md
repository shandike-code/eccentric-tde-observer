# eccentric-tde-observer

## 学校 Slurm 运行入口（2026-09-14）

仓库：[shandike-code/eccentric-tde-observer](https://github.com/shandike-code/eccentric-tde-observer)（私有）。

- **先读 [学校端快速运行说明](hpc/README.md)**：环境、输入下载、Slurm 提交和断点恢复。
- **执行 [给学校端 agent 的任务单](handoff/AGENT_TASKS_ZH.md)**：当前成果、自动流水线边界、后续科学任务与停止条件。
- 新增 `hpc/pipeline.py` 可从小型物质参考重新初始化，无需先搬运大辐射态；也支持 warm seed。
  自动流程为：初始化、可恢复全频映射、连续两态检查、H/He 反馈、一个有限物质试探步的判定。
- 历史原子率和传输核保持原样。新运行在独立目录记录自己的阈值与源哈希，默认研究
  `2.5e-4` 内层残差门；旧 `1e-4` 结果和失败点没有被改写。
- `outputs/` 不进入 Git。起跑用约 **29 MB 的 runtime 输入包**，完整历史小型结果包另行提供。
  下载地址与校验清单见 [输入包说明](hpc/README.md#输入与检查点)。
- 项目仍未得到完整耦合盘大气；自动流程完成一次物质试探判定，不等于完成整盘 NLTE 或真实线谱。

下方是保留的历史阶段记录。阅读当前进度请优先看上述任务单；历史文档中的“下一步”和
“未授权”属于当时阶段语境，不要求学校端 agent 为本次已经委托的普通运行反复询问。

> [!abstract] 项目状态
> 本项目把 Zanazzi--Ogilvie（ZO）解析偏心 TDE 盘逐层映射为远方观察者可测的连续谱。
> 截至 2026-08-31，连续谱链已完成到 Phase 5A，并完成 ZO 2022 Erratum 专项修正；
> Phase 5A 可以输出随倾角、近心点方位和进动相位变化的 optical/UV $F_{\nu}$，并转换为
> 带红移、光度距离和银河系前景消光的 $F_{\lambda}$；Phase 6 新增 corrected 曲面上的
> 条件性窄线运动学响应。Phase 7A 已审计低温、极低 $Q$ 的 TLUSTY 208 静态 H/He 环带，
> 但 12 个实际代表柱接受数为 0；Phase 7B1 已建立规定 ZO 背景的周期柱和守恒布居控制核，
> Phase 7B2 又完成一维频率--角度转移的解析验证；Phase 7B3 已加入可追溯 H/He 基态
> 光致电离、总辐射复合、守恒稳态和静态 opacity 耦合；Phase 7B4a 进一步加入 H I、He I、
> He II 碰撞电离、详细平衡三体逆率及固定背景松弛控制；Phase 7B4b 已把同一组率放回
> 规定 ZO 周期中面并自洽更新电子密度；Phase 7B4c 已加入可关闭的规定 Planck 场和逐相位
> 光致电离率，并通过零场与热详细平衡控制；Phase 7B4d 又在固定 $T,\rho$ 的受照板层中
> 闭合了 $J_{\nu}$--基态布居--连续 opacity 固定点；Phase 7B4e 进一步用同一基态截面
> 加入 Milne 束缚--自由发射、Kirchhoff 自由--自由发射和固定温度能量账本；Phase 7B4f
> 已联立逐深度温度并完成规定加热的稳定根/无根门；Phase 7B4g 又在保持 ZO 单面耗散
> 不变时扫描有限沉积柱，并得到稳定静态根、Compton/线冷却边界及大连续谱差异门；Phase
> 7B4h 已进一步建立 ZO 约束的 $n=3$ 密度柱、中面对称边界、两种受控耗散律和 H/He
> Rosseland 静力门。静态热根存在，但全部 12 个代表柱只在
> $H_{\rm static}/H_{\rm ZO}=0.292$--$0.356$ 时得到压力匹配，故不能保持 ZO 几何，Phase 4
> 替换与 UVOT 均未获准。Phase 7B4i 已在同一 ZO 拉格朗日半柱上联立有限步压缩功、规定耗散、
> H/He 基态电离能与布居以及 Rosseland 扩散，并以约 $10^{-12}$ 的残差闭合周期能量账本；但
> 128 对 256 相位的误差仍约 $0.85\%$，8 对 12 个半柱单元的人口误差可达 $0.331$，所以只通过
> 动态守恒基础门，没有通过生产分辨率。Phase 7B4j 随后建立共享轨道的自适应拉格朗日质量
> 网格并把时间审计提高到 1024 相位点；自适应 16 单元把逐点人口误差降到 $0.05576$，但仍
> 未达到 $10^{-3}$，512 对 1024 相位的人口误差也仍为 $1.281\times10^{-3}$。Phase 7B4k
> 已进一步用 12/24 单元差异构造四分量双网格误差监视函数，并以 2048 相位审计时间误差。
> 1024 对 2048 相位的温度/能流与人口误差分别为 $2.418\times10^{-4}$ 和
> $3.991\times10^{-4}$，时间门通过；但所有 16 单元网格仍无法同时收敛逐点前沿与柱积分，
> 深度生产门失败。Phase 7B4l 随后加入保守线性子单元、物理域限制和总比能温度反演；制造
> 前沿误差改善约 $1.9$ 倍且守恒门通过，但 32 对 64 有效深度单元的逐点
> $T/\kappa_{\rm R}$ 和人口误差仍为 $1.520\times10^{-2}$、$0.1132$，空间门继续失败。
> Phase 7B4m 已用 N=32 pilot 的嵌入式守恒缺陷关闭有限 N=64 空间门。Phase 7B4n 随后
> 完成真正的 64 深度、1024 相位联合周期参考，并用 dense 对三色 Jacobian 控制验证
> $4.578\times10^{-9}$ 的最大数值差异。N=62 对 N=64 的 1024 相位空间门继续通过；但
> N=64 的 512 对 1024 高深度时间比较在最表层 He III 上得到
> $1.087\times10^{-3}$，比预声明的 $10^{-3}$ 门高约 $8.7\%$。Phase 7B4o 现已独立完成
> 64 深度、2048 相位有限参考；1024 对 2048 的最大逐点人口差降到
> $2.887\times10^{-4}$，其余连续指标为 $3.486\times10^{-5}$--$1.660\times10^{-4}$，
> 前沿状态错配为 0。联合有限深度--时间门因此通过，下一微阶段获准进入非局域、频率依赖
> 动态转移。Phase 7B4p 现已在冻结的 64×1024 和 64×2048 物质态上完成全轨道
> 频率--角度非局域形式解：解析/热力学控制、全部相位形式解守恒和 1024 对 2048 时间门
> 通过，但正式 4 方向、71 频点与 N=64 深度配置没有通过联合数值门。扩展角度 16 对 24
> 已达到 $6.626\times10^{-5}$，而 263 对 519 频点的最大速率误差仍为 $0.3688$，N=62
> 对 N=64 的最大非局域积分量差为 $3.013\times10^{-3}$。同时
> $\max(t_{\rm diff}/P_{\rm orb})=0.7379$，逐相位稳态辐射场的准静态门失败。所以下一步
> Phase 7B4q 已完成阈值显式正权求积、独立 N128×1024 动态物质参考、稀疏界面形式解和
> 独立辐射子网格。N64 动态逐点物态及未加密形式转移仍失败；N128 物质网格上每物质单元
> 16 个辐射子单元相对 32 子单元的最大误差为 $3.602\times10^{-4}$，160 对 304 频率节点、
> 16 对 24 角阶的最大误差分别为 $1.554\times10^{-12}$、$1.156\times10^{-6}$，均通过。
> Phase 7B4r 现已独立完成 N128×2048 周期物质参考；两周期残差为
> $3.839\times10^{-10}$，N128 的 1024 对 2048 最大逐点人口差为
> $2.911\times10^{-4}$，表面能流差为 $1.660\times10^{-4}$，前沿状态零错配，有限物质
> 深度--时间门通过。Phase 7B4s 随后实现移动拉格朗日柱上的全隐式 ALE 离散纵标核；
> 吸收、纯散射、几何守恒、真空平流和冻结回归均通过。N128×2048 的 10/60 eV 双频
> 周期 pilot 在第二周期逐位闭合，最大能量账本残差为 $1.424\times10^{-9}$。但最大垂向
> 速度为 $0.00803c$，高于 $10^{-3}$ 精度目标。Phase 7B4t 随后通过完整 Lorentz
> 射线/角测度、阈值对齐守恒频率组和正性批量源迭代组件门。153 个物理组的实际呼吸
> 共动平均误差为 $1.157\times10^{-3}$，被保留为失败；303 组降到
> $7.735\times10^{-4}$。N128×160×S16 压力步的迭代解与稀疏 LU 相差
> $1.76\times10^{-14}$，能量账本残差为 $7.72\times10^{-10}$。但 160 个 Gauss
> 积分节点没有频率控制体边界，不能直接用于守恒 Doppler 搬移；完整 Lorentz 碰撞源尚未
> 与 ALE 方程联立。Phase 7B4u 随后在 21 个轨道相位、8 个固定质量深度共 168 个
> N128×2048 真实物态上检验 H/He 多群 opacity、Milne 发射、光致率、复合率与净加热。
> 153、303 组失败；604 组以 $1.0093\times10^{-3}$ 轻微失败；1205 组以
> $2.5271\times10^{-4}$ 通过。Phase 7B4v 已把完整 Lorentz 物质碰撞源与 ALE 储能及
> 移动界面通量写入同一残差；零速度、刚体平移、同源呼吸和 $\beta\tau=2$ 动态扩散
> 四力控制均通过。可是 1205 组在三个真实一步物态上相对 38496 组有限参考的最大动态
> 原子率误差为 $1.2829\times10^{-2}$，没有通过 $10^{-3}$ 门；19249 组只在三个单元状态
> 上相对有限参考通过，未获生产选择。完整算子门通过与动态频率表示门失败必须同时保留，
> Phase 7B4w 随后检验 H I、He I、He II 阈值显式对齐的阈值局域 P0 网格。几何、
> Planck 积分恒等式和不规则网格移动平衡均通过；三个真实一步状态相对 38496 组有限参考
> 首次同时低于 $10^{-3}$ 时需要 18105 个物理组，超过预声明的 4814 组效率上限。频率
> 精度通过但效率失败，仍无生产网格。Phase 7B4x 随后实现守恒、非负可实现的组内 P1
> 频率矩；普通对数 P1 在 2408 组把最大速度误差降到 $9.0435\times10^{-4}$，但最大宽度
> 变化状态仍为 $2.4547\times10^{-3}$。Phase 7B4y 再把阈值局域边界与 P1 联合，几何、
> 移动平衡和算子门全部通过，但 2265 组最大宽度变化误差仍为 $3.4545\times10^{-3}$，
> 没有优于普通 P1。Phase 7B4z 随后实现独立的守恒 P2 Lorentz--ALE；1604 组、4812
> 自由度把最大速度误差降到 $7.5063\times10^{-4}$，但最大宽度变化/H I 率仍为
> $2.5472\times10^{-3}$，且实际状态中可实现性 limiter 频繁触发。P2 也未选为生产表示；
> Phase 7B5a 随后真正以 $y=\ln\nu$ 为守恒坐标并保存 $Q=\nu I_{\nu}$。解析 Doppler 平移、
> Jacobian 和移动平衡均通过，但 2408 组、4816 自由度的最大宽度变化/H I 率误差仍为
> $2.4569\times10^{-3}$，与普通 P1 只差约 $0.09\%$；粗冷状态残差失败点也被保留。
> Phase 7B5b 随后否决了未闭合的“单一全局率矩”捷径，并只按已知 H I 率核重分配固定
> log-P1 网格。三档聚焦比例的网格、移动平衡和全部实际算子门都通过；但 4816 自由度下
> 最大宽度变化/H I 率误差仍为 $2.1329\times10^{-3}$--$5.6739\times10^{-3}$，没有
> 一档通过，更不满足相邻两档共同通过的稳健规则。下一步先做有符号率误差的能量区间定位，
> Phase 7B5c 已完成该定位：两个移动应力状态分别有 $61.94\%$ 和 $90.59\%$ 的绝对
> H I 率差位于 $13.60$--$13.71\ {\rm eV}$ 的 Doppler 阈值带，最冷表层却有
> $85.11\%$ 位于 $13.71$--$24.59\ {\rm eV}$。参考末态谱压缩误差只有约
> $10^{-12}$--$10^{-10}$，实际误差来自动态余项；三态没有统一主导区，故下一步必须拆分
> 动态子算子，而不是设计未经授权的固定基函数。Phase 7B5d 的匹配候选/参考一因子控制
> 进一步显示：ALE 宽度变化和散射不是稳定主因；令 $D=1$ 或关闭真实吸收/热发射都会把
> 两个移动状态误差降低 $99.9\%$ 以上，故瓶颈是 Lorentz 与真实连续碰撞的交互，尚不能
> 唯一归因于单项。Phase 7B5e 随后分别关闭强度、消光和发射率 Lorentz 支路；只有完整
> 算子与 no intensity Lorentz 的三态受控方程通过，后者把两个移动误差降至完整值的
> $1.424\%$/$1.331\%$。消光与发射率关闭控制因 P1 联立残差失败而不能用于因果分类，
> 因此只授权一次强度平移审计，仍不授权修算符。Phase 7B5f 已完成该审计：同一解析输入
> 的三态单次 P1/P0 H I 率差仅为 $2.38\times10^{-7}$、$3.17\times10^{-8}$ 和
> $6.83\times10^{-8}$，能量差低于 $5.4\times10^{-13}$。单次强度搬移不是主因，
> 下一门转向固定点碰撞反馈的逐迭代累积。Phase 7B5g 已保存固定点截面：最大速度到第 2
> 次、最大宽度到第 8 次才超过最终误差的 $50\%$，最终相对第 0 次分别放大
> $1.79\times10^{4}$/$3.12\times10^{4}$。Phase 7B5h 随后逐位复现 15 个单步映射，并
> 把标量 H I 率严格拆成同输入新注入与已有误差传播；两个移动状态的注入分量最低仍占
> 绝对分量和的 $95.3\%$。所以增长主要来自每一步重新写入离散差，不是已有误差的
> Jacobian 放大。Phase 7B5i 再以 2408 组 P0 中间控制拆分该注入：频率分区项在两个
> 移动状态中稳定占绝对分量和的 $60.1\%$--$64.3\%$，同分区 P1--P0 项约占
> $35.7\%$--$39.9\%$，两者异号抵消；4816 组同成本 P0 仍有两个最大宽度截面失败。
> Phase 7B5j 的非拟合分区审计进一步显示预算内三种 P0 分区均失败；率核与 Doppler
> 锚点要到 9632 组才分别以 $8.96\times10^{-4}$/$8.86\times10^{-4}$ 通过，而普通
> 对数仍失败。Phase 7B5k 已在 19264 组复算全部检查点：率核与 Doppler 锚点的最坏
> 误差进一步降至 $2.57\times10^{-4}$/$3.43\times10^{-4}$，因此有限高分辨率 P0
> 参考解得到相邻确认。单单元求解时间和返回数组约随组数线性增长，但这不改变 4816 组
> 原效率门失败，也不授权把 9632 组直接改成新预算；下一门只设计封闭局域多分辨率压缩。
> Phase 7B5l 已通过该组件门：建立 2408--4816--9632 严格 1--2--4 嵌套、P0 守恒
> 限制/延拓、能量与 H/He 率联合指标，以及 4816 上限内的 4814 叶网格。解析控制谱只
> 授权下一步做互不重叠的实际训练/验证审计，不构成生产精度通过。Phase 7B5m 已完成
> 该独立审计：只用 $n=0,2,4$ 的 9 个训练状态冻结网格，在 $n=1,8$ 的 6 个留出状态
> 上不再重训。4814 叶网格训练最坏 H I 率误差为 $6.45865\times10^{-4}$，但最大宽度
> 变化的 $n=8$ 留出误差为 $1.003468\times10^{-3}$，严格高于 $10^{-3}$；9632 组
> master 在同一点为 $8.95887\times10^{-4}$。因此组数账本通过而完整 4816 组效率门
> 失败，生产表示仍未选择。Phase 7B5n 随后预注册 1--2--4 分层 P0 新表示和全新留出，
> 但 `surface temperature q75` 在 $n=11$ 已收敛，预注册的 $n=12$ 状态不存在；协议
> 没有事后改写，候选也没有判定。Phase 7B5o 因而排除这六个旧病例，冻结另外六个几何
> 分位病例，并验证每例必然存在的初始态和参考收敛态。精确 4816 叶候选由 1408 个单叶、
> 296 个双叶和 704 个四叶父带组成；协议、参考源、映射、算子和 9632 master 联合门均
> 通过，但候选在 `signed width change q80` 收敛态的 He II 率误差为
> $1.000546\times10^{-3}$，严格失败 $10^{-3}$ 门。生产表示仍未选择，下一步需要明确
> 决定是否把已通过的 9632 master 作为新资源预算。Phase 7B5p 现已在冻结最坏状态上
> 完成 10 个全新子进程的单单元资源审计：4816/9632 的中位进程峰值 RSS 分别为
> $158.86/190.44\,\mathrm{MiB}$，扣除共同加载基线后的中位算子高水位增量比为
> $2.044$，中位单步时间比为 $1.935$。这支持下一单单元门的资源可行性，但不是全柱
> 峰值，也没有自动修改预算。Phase 7B5q 又把测量扩展到完整固定点：投影收敛源和默认
> 初值分别需要 29/43 次迭代；9632 在默认初值下的中位完整固定点时间为
> $0.3668\,\mathrm{s}$，全部运行中的最大峰值为 $209.44\,\mathrm{MiB}$。两种初值的
> 最终强度只差约 $2\times10^{-10}$。用户随后明确批准 9632 组新预算和单单元角度--
> 辐射子网格门。Phase 7B5r 的七个完整固定点均通过守恒与非负性，但 16 对 24 方向、
> 16 对 32 子单元和 16×16 对 24×32 的最大误差分别为
> $5.448\times10^{-3}$、$1.482\times10^{-2}$ 和 $9.589\times10^{-3}$，均严格失败
> $10^{-3}$ 门。9632 频率预算已采用，但单单元生产角度--深度配置仍未选择。
> Phase 7B5s 随后加密到 24/32/48 方向和 32/64 子单元；32 对 48 方向、32 对 64
> 子单元以及 32×32 对 48×64 的最大误差分别为 $1.221\times10^{-3}$、
> $7.626\times10^{-3}$ 和 $6.428\times10^{-3}$。资源门通过，但三项科学门仍失败，
> 当前主收敛瓶颈是辐射深度离散，生产配置继续为空。
> Phase 7B5t 已以解析门确认旧迎风为一阶，并引入守恒的单元特征积分和特征分区角求积。
> 新方案的角度、16/32 深度、32/64 深度和联合误差分别为
> $1.73\times10^{-5}$、$1.65\times10^{-4}$、$4.39\times10^{-5}$ 和
> $1.74\times10^{-4}$，全部通过；正式单单元配置为 9632 组、32 方向、16 子单元。
> Phase 7B5u 随后审计全部 2048 个相位：正式完整柱有 12.62 亿个强度未知量，单强度
> 数组为 $9.406\,\mathrm{GiB}$，当前实现已识别的同时驻留数组下界为
> $84.668\,\mathrm{GiB}$，所以不能整体运行。另有 586 个相位的两个最掠射方向发生
> ALE 特征线反向。Phase 7B5v 已验证守恒 turning-ray 与流式固定点，但预注册的单次
> 映射以 $3.93775\times10^{-12}$ 严格失败 $10^{-12}$ 门。Phase 7B5w 随后改用频率
> 切片起点平移不变的局域交叠积分；单次映射和最终固定点均与整体路径逐位相同，stream256
> 峰值 RSS 为 392.08 MiB，对比整体 1251.75 MiB。Phase 7B5x 已实测最坏 4096 深度块：
> 峰值 RSS 为 2863.14 MiB，总时间 10.83 s，其中一次源映射占 9.66 s。内存门已通过，
> 但完整柱固定点仍需先做性能架构决策。7B5y 的大批次候选严格失败并回退；7B5z 的精简
> 中间源映射保持强度逐位相同并加速 1.574 倍。7B6a 随后以两进程完成全部 76 块的一次
> 全频映射，墙钟 244.88 s、每进程峰值约 2.9 GiB。7B6b--7B6h 又依次排除了无保护
> 超松弛和过大固定权重，验证了整态正性保护、最坏块向量 Aitken 与可恢复全频续算。
> 7B6i 在第 12 次完整状态安全暂停，残差为 $2.44809\times10^{-4}$；7B6j 从同一起点
> 证明正性边界权重 2.0 比固定 1.8 略优，但第 14 次残差仍为
> $2.10811\times10^{-4}$。7B6k 的 Anderson(1) 比向量 Aitken 更慢；7B6l 的
> Anderson(2) 虽改善 $17.5\%$，仍未达到预注册的两倍加速门。7B6m 的体积谱、能量和
> 光致电离代理已过 $10^{-3}$，但边界谱通量与总通量未过；7B6n 用正式 ALE 面通量确认
> 这不是边界代理的假失败。7B6o 随后从第 14 次状态可恢复地续跑到第 30 次，最终边界谱与
> 总通量变化降到 $5.246\times10^{-4}$ 和 $4.482\times10^{-4}$。7B6p 的正式面通量
> 科学门通过但长寿命进程越过 6 GiB；7B6q 逐位复现同一结果并确认资源失败；7B6r 用四个
> 逻辑进程分两批回收内存，正式谱仍逐位相同，四个峰值均低于 6 GiB。固定物质、单相位全柱
> 科学泛函收敛现已通过。7B7a 随后从正式共动辐射场提取 9632 组 H/He 率与净加热；率积分
> 对逆四力的体积 $L_{1}$ 为 $9.424\times10^{-4}$，镜面对称残差为
> $1.199\times10^{-11}$。原工作组资源失败后，7B7a-r 以一块一进程逐位复现，峰值降到
> 4706 MiB。7B7b 的一次真实 889 s 物质响应虽把守恒残差闭合到约 $10^{-16}$，却使最强
> 单元的物质能增加 9.47 倍、温度相对变化 36.1，故候选被拒绝。7B7c 定位最短 10% 物质能
> 响应时间仅 9.40 s，至少 95 个能量信赖域子步只是下界。7B7d 没有缩短物理步长，而以
> $1.38345\times10^{-3}$ 的求解器阻尼取得一个最大温变 5% 的 Picard 方向。7B7e 在此物质
> 态上完成一次全频辐射映射；辐射残差为 $3.866\times10^{-4}$，物质残差体积 $L_{1}$ 比为
> $0.9610$，但率积分与逆四力的体积 $L_{1}$ 差达到 $5.500\times10^{-3}$，严格失败
> $10^{-3}$ 参考系/源项一致性门。7B7f 随后证明该失败来自在每块“新核心 + 旧 halo”的
> Jacobi 内部态上过早提取正式源项；76 个新核心拼接后，体积 $L_{1}$ 和柱积分差降到
> $7.338\times10^{-6}$ 与 $5.238\times10^{-5}$。7B7f-r 用一块一进程逐位复现三条
> 科学数组，最大 RSS 为 2586 MiB，总门通过。7B7g--7B7j 随后完成第二条固定时间层
> 物质方向、第二次全频辐射映射和全局拼接反馈。正式原子率--四力体积
> $L_{1}$ 差为 $7.990\times10^{-6}$，但质量加权固定点残差只从 $0.2086$ 降到
> $0.1934$，最大逐单元残差仍为 $0.9971$。7B7k 据实测成本否决继续朴素 Picard，
> 转入受保护非线性加速设计。7B8a--7B8c 已构造逐单元割线、完成新的全频辐射映射并
> 重算正式反馈；质量加权残差降到 $0.1014$，但上一最难单元的真残差扩大到原来的
> $1.0305$，严格失败预注册局域门。7B8d--7B8f 又用两个完整反馈端点做离散回溯并重跑
> 全频辐射；质量加权残差进一步降到 $0.06672$，但原最难单元和全柱最大残差分别扩大到
> $1.0475$、$1.0857$ 倍。回溯同样被拒绝，当前瓶颈已定位为跨深度非局域刚性耦合。
> 全轨道、Phase 4 替换和 UVOT 仍未获准。当前仍无激发态、
> 收敛的全频动态
> 非局域反馈，因此**没有物理可信的 X-ray 或绝对原子线谱，也没有加入
> 自由盘风或事件拟合**。
>
> **2026-09-02 收尾状态。** 用户选择不再为达到预注册的 $10^{-4}$ 全态残差继续进行
> 重型迭代。0.0625 固定物质候选在一个完整 76 块边界安全停止；最后残差为
> $2.10413\times10^{-4}$、收缩因子为 $0.991982$，边界谱与 bolometric 变化为
> $4.4010\times10^{-6}$ 和 $2.8378\times10^{-6}$。`[V]` 这表明慢收缩和边界量稳定，
> **不等于严格收敛**；正式 feedback pair、物质反馈、Phase 4 替换、UVOT、动态 NLTE
> 与真实线形成均未授权。`[O]` 慢模定位到约 $9.10\,\mathrm{eV}$ 的分子控制点，但尚无
> 因果归因。后续三分支合同保持 `not_ready`。Phase 5B8 另为两条方程自洽候选建立了
> $40.81395/42.92803$ 年的相对进动时间钟；没有绝对历元，也不适用于旧常偏心 atlas。

导航：[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/docs/project_closeout_2026-09-02|2026-09-02 项目阶段性收尾]] ·
[[eccentric_tde_observer/docs/erratum_2022_correction|ZO 2022 Erratum 修正]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]] ·
[[eccentric_tde_observer/lecture/项目讲义/00_document_map|完整文档地图]] ·
[[eccentric_tde_observer/docs/phase5b8_candidate_source_time_mapping|Phase 5B8 候选相对时间钟]] ·
[[eccentric_tde_observer/docs/phase7b9dv_closeout|Phase 7B9dv 干净边界收尾]] ·
[[eccentric_tde_observer/docs/phase7a_static_annulus|Phase 7A 静态环带审计]] ·
[[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 周期柱控制]] ·
[[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 转移控制]] ·
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 原子率与静态耦合]] ·
[[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a 碰撞动力学控制]] ·
[[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 轨道耦合动力学]] ·
[[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c 规定辐射耦合]] ·
[[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d 固定板层自洽反馈]] ·
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e 基态连续发射与能量账本]] ·
[[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f 规定加热温度平衡]] ·
[[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 有限沉积柱静态门]] ·
[[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 静力大气表准入门]] ·
[[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 周期动态能量柱]] ·
[[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase 7B4j 自适应深度与时间审计]] ·
[[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 双网格误差与 2048 相位审计]] ·
[[eccentric_tde_observer/docs/phase7b4l_conservative_subcell_reconstruction|Phase 7B4l 保守子单元重构]] ·
[[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 前沿感知可变细化]] ·
[[eccentric_tde_observer/docs/phase7b4n_joint_depth_time_reference|Phase 7B4n 联合深度--时间参考]] ·
[[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o 高深度时间参考]] ·
[[eccentric_tde_observer/docs/phase7b4p_frozen_nonlocal_transfer|Phase 7B4p 冻结非局域转移审计]] ·
[[eccentric_tde_observer/docs/phase7b4q_threshold_quadrature|Phase 7B4q 阈值求积与分离深度网格]] ·
[[eccentric_tde_observer/docs/phase7b4r_n128_time_reference|Phase 7B4r N128 时间参考]] ·
[[eccentric_tde_observer/docs/phase7b4s_implicit_ale_radiation|Phase 7B4s 隐式 ALE 辐射储能]] ·
[[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t Lorentz 频率组门]] ·
[[eccentric_tde_observer/docs/phase7b4u_multigroup_continuum_gate|Phase 7B4u 多群连续系数门]] ·
[[eccentric_tde_observer/docs/phase7b4v_mixed_frame_ale_gate|Phase 7B4v 完整混合系 ALE 门]] ·
[[eccentric_tde_observer/docs/phase7b4w_threshold_frequency_groups|Phase 7B4w 阈值局域 P0 门]] ·
[[eccentric_tde_observer/docs/phase7b4x_p1_frequency_moments|Phase 7B4x 普通对数 P1 门]] ·
[[eccentric_tde_observer/docs/phase7b4y_threshold_p1_gate|Phase 7B4y 阈值局域 P1 门]] ·
[[eccentric_tde_observer/docs/phase7b4z_p2_frequency_moments|Phase 7B4z 普通对数 P2 门]] ·
[[eccentric_tde_observer/docs/phase7b5a_log_frequency_p1_gate|Phase 7B5a 对数频率 P1 门]] ·
[[eccentric_tde_observer/docs/phase7b5b_rate_kernel_grid_gate|Phase 7B5b H I 率核网格门]] ·
[[eccentric_tde_observer/docs/phase7b5c_signed_rate_error_localization|Phase 7B5c H I 率误差定位]] ·
[[eccentric_tde_observer/docs/phase7b5d_dynamic_operator_controls|Phase 7B5d 动态子算子控制]] ·
[[eccentric_tde_observer/docs/phase7b5e_lorentz_component_controls|Phase 7B5e Lorentz 分量控制]] ·
[[eccentric_tde_observer/docs/phase7b5f_single_pass_intensity_transform|Phase 7B5f 单次强度搬移]] ·
[[eccentric_tde_observer/docs/phase7b5g_fixed_point_feedback_audit|Phase 7B5g 固定点反馈审计]] ·
[[eccentric_tde_observer/docs/phase7b5h_recurrence_decomposition|Phase 7B5h 单步注入--传播分解]] ·
[[eccentric_tde_observer/docs/phase7b5i_partition_representation_split|Phase 7B5i 分区--P1/P0 拆分]] ·
[[eccentric_tde_observer/docs/phase7b5j_prescribed_partition_audit|Phase 7B5j 非拟合分区审计]] ·
[[eccentric_tde_observer/docs/phase7b5k_high_resolution_convergence|Phase 7B5k 高分辨率相邻收敛]] ·
[[eccentric_tde_observer/docs/phase7b5l_multiresolution_component_gate|Phase 7B5l 多分辨率组件门]] ·
[[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|Phase 7B5m 独立实际态验证]] ·
[[eccentric_tde_observer/docs/phase7b5n_preregistered_protocol|Phase 7B5n 协议可行性失败]] ·
[[eccentric_tde_observer/docs/phase7b5o_preregistered_protocol|Phase 7B5o 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o 独立验证]] ·
[[eccentric_tde_observer/docs/phase7b5p_preregistered_resource_protocol|Phase 7B5p 资源预注册]] ·
[[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p 隔离资源测量]] ·
[[eccentric_tde_observer/docs/phase7b5q_preregistered_fixed_point_resource_protocol|Phase 7B5q 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q 固定点资源]] ·
[[eccentric_tde_observer/docs/phase7b5r_preregistered_joint_convergence_protocol|Phase 7B5r 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r 联合收敛]] ·
[[eccentric_tde_observer/docs/phase7b5s_preregistered_refined_joint_protocol|Phase 7B5s 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s 更细联合参考]] ·
[[eccentric_tde_observer/docs/phase7b5t_preregistered_characteristic_transport_protocol|Phase 7B5t 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5t_characteristic_transport_gate|Phase 7B5t 特征输运门]] ·
[[eccentric_tde_observer/docs/phase7b5u_preregistered_full_column_admission|Phase 7B5u 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5u_full_column_admission|Phase 7B5u 完整柱准入审计]] ·
[[eccentric_tde_observer/docs/phase7b5v_preregistered_streaming_turning_protocol|Phase 7B5v 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5v_streaming_turning_gate|Phase 7B5v 严格失败门]] ·
[[eccentric_tde_observer/docs/phase7b5w_preregistered_translation_invariant_remap|Phase 7B5w 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5w_translation_invariant_remap_gate|Phase 7B5w 平移不变搬移门]] ·
[[eccentric_tde_observer/docs/phase7b5x_preregistered_full_depth_block_probe|Phase 7B5x 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5x_full_depth_block_probe|Phase 7B5x 整深度块资源实测]] ·
[[eccentric_tde_observer/docs/phase7b5y_remap_batch_performance|Phase 7B5y 性能失败]] ·
[[eccentric_tde_observer/docs/phase7b5z_lean_source_map|Phase 7B5z 精简源映射]] ·
[[eccentric_tde_observer/docs/phase7b6a_full_frequency_source_iteration|Phase 7B6a 全频单次迭代]] ·
[[eccentric_tde_observer/docs/phase7b6b_relaxed_fixed_point|Phase 7B6b 无保护松弛失败]] ·
[[eccentric_tde_observer/docs/phase7b6c_guarded_relaxation|Phase 7B6c 整态正性保护]] ·
[[eccentric_tde_observer/docs/phase7b6d_full_depth_contraction|Phase 7B6d 最坏块收缩]] ·
[[eccentric_tde_observer/docs/phase7b6e_extended_relaxation|Phase 7B6e 扩展权重失败]] ·
[[eccentric_tde_observer/docs/phase7b6f_full_frequency_contraction|Phase 7B6f 全频收缩]] ·
[[eccentric_tde_observer/docs/phase7b6g_vector_aitken|Phase 7B6g 最坏块 Aitken]] ·
[[eccentric_tde_observer/docs/phase7b6h_full_frequency_aitken|Phase 7B6h 全频 Aitken]] ·
[[eccentric_tde_observer/docs/phase7b6i_recoverable_convergence_pause|Phase 7B6i 可恢复暂停]] ·
[[eccentric_tde_observer/docs/phase7b6j_positivity_line_search|Phase 7B6j 正性边界线搜索]] ·
[[eccentric_tde_observer/docs/phase7b6k_anderson1|Phase 7B6k Anderson(1) 失败]] ·
[[eccentric_tde_observer/docs/phase7b6l_anderson2|Phase 7B6l Anderson(2) 失败]] ·
[[eccentric_tde_observer/docs/phase7b6m_science_functionals|Phase 7B6m 科学泛函审计]] ·
[[eccentric_tde_observer/docs/phase7b6n_formal_face_flux|Phase 7B6n 正式面通量复核]] ·
[[eccentric_tde_observer/docs/phase7b6o_fixed2_continuation|Phase 7B6o 可恢复续算]] ·
[[eccentric_tde_observer/docs/phase7b6p_final_formal_flux|Phase 7B6p 最终正式面通量]] ·
[[eccentric_tde_observer/docs/phase7b6q_resource_recheck|Phase 7B6q 资源复验]] ·
[[eccentric_tde_observer/docs/phase7b6r_worker_recycling|Phase 7B6r 工作进程回收]] ·
[[eccentric_tde_observer/docs/phase7b7a_feedback_coefficients|Phase 7B7a 共动反馈系数]] ·
[[eccentric_tde_observer/docs/phase7b7ar_resource_closure|Phase 7B7a-r 资源闭合]] ·
[[eccentric_tde_observer/docs/phase7b7b_material_response|Phase 7B7b 物质响应失败]] ·
[[eccentric_tde_observer/docs/phase7b7c_timescale_diagnosis|Phase 7B7c 时间尺度诊断]] ·
[[eccentric_tde_observer/docs/phase7b7d_trust_region_picard|Phase 7B7d 阻尼物质方向]] ·
[[eccentric_tde_observer/docs/phase7b7e_radiation_direction|Phase 7B7e 辐射方向失败]] ·
[[eccentric_tde_observer/docs/phase7b7f_assembled_diagnostics|Phase 7B7f 全局拼接诊断]] ·
[[eccentric_tde_observer/docs/phase7b7fr_resource_closure|Phase 7B7f-r 资源闭合]] ·
[[eccentric_tde_observer/docs/phase7b7g_assembled_atomic_rates|Phase 7B7g 全局原子率]] ·
[[eccentric_tde_observer/docs/phase7b7h_second_picard_direction|Phase 7B7h 第二物质方向]] ·
[[eccentric_tde_observer/docs/phase7b7i_second_radiation_map|Phase 7B7i 第二辐射方向]] ·
[[eccentric_tde_observer/docs/phase7b7j_second_assembled_feedback|Phase 7B7j 正式反馈与残差]] ·
[[eccentric_tde_observer/docs/phase7b7k_nonlinear_cost_decision|Phase 7B7k 非线性成本决策]] ·
[[eccentric_tde_observer/docs/phase7b8a_protected_secant|Phase 7B8a 受保护割线提案]] ·
[[eccentric_tde_observer/docs/phase7b8b_secant_radiation_map|Phase 7B8b 割线辐射映射]] ·
[[eccentric_tde_observer/docs/phase7b8c_secant_feedback|Phase 7B8c 割线真残差失败]] ·
[[eccentric_tde_observer/docs/phase7b8d_feedback_line_search|Phase 7B8d 反馈感知回溯]] ·
[[eccentric_tde_observer/docs/phase7b8e_backtracked_radiation_map|Phase 7B8e 回溯辐射映射]] ·
[[eccentric_tde_observer/docs/phase7b8f_backtracked_feedback|Phase 7B8f 三重真残差失败]] ·
[[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1 线性拱点本征模门]] ·
[[eccentric_tde_observer/docs/phase5b2_nonlinear_hamiltonian_gate|Phase 5B2 非线性局域 Hamiltonian 门]] ·
[[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3 非线性全局模与文献基准门]] ·
[[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a 已发表分支反演审计]] ·
[[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|Phase 5B3b 完整二维非线性诊断]] ·
[[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c 印刷方程路径审计]] ·
[[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|Phase 5B3d 公开来源审计]] ·
[[eccentric_tde_observer/docs/zo2020_author_source_request_draft|ZO 2020 作者数据请求及发送记录]] ·
[[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4 候选时标与模形兼容门]] ·
[[eccentric_tde_observer/docs/phase5b5_mode_matched_time_axis|Phase 5B5 模形绑定候选时间钟]] ·
[[eccentric_tde_observer/docs/code_conventions|代码与写作规范]]

---

## 1. 项目要解决什么

ZO 理论提供解析偏心盘源场
$e(a),\varpi(t),\Sigma(a,E),j(a,E),H(a,E),T_{\rm eff}(a,E)$，但原文的辐射结果主要是
局域黑体的 face-on 全盘积分。这个项目保留该解析理论为唯一源模型，补上从源面到真实
观察者方向所必需的几何、辐射与观测算子：

```mermaid
flowchart LR
  A["[L] ZO 解析源场"]
  B["[A] 垂向密度与光球"]
  C["[A] 三维表面、投影与自遮挡"]
  D["[A] 热化、谱硬化与角分布"]
  E["[A] 频移、像平面与 Stokes"]
  F["[V] F_nu(i, Phi) 与无量纲光变"]
  G["[V] 红移、距离、消光与 F_lambda"]
  H["[V] Phase 7B1 周期柱与布居控制"]
  I["[V/O] Phase 7B2 频率--角度转移控制"]
  J["[L/A/V/O] Phase 7B3 H/He 连续谱原子率"]
  K["[L/A/V/O] Phase 7B4a 碰撞动力学控制"]
  L["[A/V/O] Phase 7B4b 轨道耦合基态动力学"]
  M["[A/V/O] Phase 7B4c 规定辐射--布居耦合"]
  N["[A/V/O] Phase 7B4d 固定板层 J_nu--布居反馈"]
  O["[A/V/O] Phase 7B4e 基态 Milne 发射与能量账本"]
  P["[A/V/O] Phase 7B4f 规定加热温度平衡"]
  Q["[A/V/O] Phase 7B4g 有限沉积柱静态门"]
  R["[A/V/O] Phase 7B4h 静力大气表准入门"]
  S["[A/V/O] Phase 7B4i 周期动态能量柱"]
  T["[A/V/O] Phase 7B4j 自适应深度与时间审计"]
  U["[A/V/O] Phase 7B4k 双网格误差与 2048 相位审计"]
  V["[A/V/O] Phase 7B4l 保守子单元重构"]
  W["[A/V/O] Phase 7B4m 前沿感知可变细化"]
  X["[A/V/O] Phase 7B4n 64 深度乘 1024 相位联合参考"]
  Y["[A/V/O] Phase 7B4o 64 深度乘 2048 相位时间门"]
  Z["[V/O] Phase 7B4p 冻结非局域转移审计"]
  AA["[V/O] Phase 7B4q 阈值求积、N128 与辐射子网格"]
  AB["[A/V/O] Phase 7B4r N128 乘 2048 相位时间门"]
  AC["[A/V/O] Phase 7B4s 隐式 ALE 辐射储能核"]
  AD["[A/V/O] Phase 7B4t Lorentz 频率组与正性迭代门"]
  AE["[A/V/O] Phase 7B4u H/He 多群连续系数门"]
  AF["[A/V/O] Phase 7B4v 完整混合系 ALE 门"]
  AG["[A/V/O] Phase 7B4w 阈值局域 P0 精度与效率门"]
  AH["[A/V/O] Phase 7B4x 普通对数 P1 门"]
  AI["[A/V/O] Phase 7B4y 阈值局域 P1 联合门"]
  AJ["[A/V/O] Phase 7B4z 普通对数 P2 门"]
  AK["[A/V/O] Phase 7B5a 对数频率守恒 P1 门"]
  AL["[A/V/O] Phase 7B5b H I 率核目标导向网格门"]
  AM["[A/V/O] Phase 7B5c H I 率有符号频段误差定位"]
  AN["[A/V/O] Phase 7B5d Lorentz、ALE 与碰撞一因子控制"]
  AO["[A/V/O] Phase 7B5e Lorentz 分量控制"]
  AP["[A/V/O] Phase 7B5f 单次强度 Lorentz 平移审计"]
  AQ["[A/V/O] Phase 7B5g 固定点碰撞反馈逐迭代审计"]
  AR["[A/V/O] Phase 7B5h 单步注入与已有误差传播分解"]
  AS["[A/V/O] Phase 7B5i 候选频率分区与同分区 P1-P0 拆分"]
  AT["[A/V/O] Phase 7B5j 预声明非拟合频率分区审计"]
  AU["[A/V/O] Phase 7B5k 高分辨率相邻收敛与资源审计"]
  AV["[A/V/O] Phase 7B5l 守恒局域多分辨率组件门"]
  AW["[A/V/O] Phase 7B5m 冻结网格独立验证失败"]
  AX["[A/V/O] Phase 7B5n 预注册状态不可实现"]
  AY["[A/V/O] Phase 7B5o He II 联合留出失败"]
  AZ["[A/V/O] Phase 7B5p 隔离进程资源审计"]
  BA["[A/V/O] Phase 7B5q 完整固定点资源包络"]
  A --> B --> C --> D --> E --> F --> G
  A --> H --> I --> J --> K --> L --> M --> N --> O --> P --> Q --> R --> S --> T --> U --> V --> W --> X --> Y --> Z --> AA --> AB --> AC --> AD --> AE --> AF --> AG --> AH --> AI --> AJ --> AK --> AL --> AM --> AN --> AO --> AP --> AQ --> AR --> AS --> AT --> AU --> AV --> AW --> AX --> AY --> AZ --> BA
  BA -.production path not authorized.-> D
```

其中 $\Phi=\phi_{\rm obs}-\varpi(t)$ 是观察者方位相对近心点的相位。逻辑方向不能反转：
观测者模块只能消费源模型，不能通过重标定温度、裁剪无效状态或选择自由风参数来修复源端
物理缺口。`[A]`

本项目不做以下事情：

- 不从流体模拟输出替代 ZO 解析源；
- 不把连续谱任务变成宽发射线拟合；
- 不在裸盘失败前加入任意盘风；
- 不把弱场直接像称为完整 Kerr ray tracing；
- 不把 LTE H/He 审计或形式 Wien 尾称为 NLTE X-ray 预言；
- 不拟合某个具体 TDE，Phase 5A 的红移和消光只是演示参数。

---

## 2. 当前科学检查点

| 问题 | 当前结论 | 证据状态 |
|---|---|---|
| Erratum 面积是否落实 | 正式面积唯一使用 $a j(1-e\cos E)\,da\,dE$；$aj\,da\,dE$ 只保留为显式 pre-Erratum 历史回归 | `[L/V]` |
| ZO 源是否保留 | 代码复现常偏心参考源的 ZO Eqs. (10, 16, 18, 31, 35, 55)，Erratum 不回写源场 | `[L/V]` |
| 典型高偏心源能否使用局域光球 | 参考点 $(e,\mathcal V)=(0.8,1)$ 约 $99\%$ 的 corrected 面积有 $z_{\rm ph}/r\ge1$；Gaussian 与 $n=3$ 闭合都失败 | `[V]` |
| 严格有效域在哪里 | $(0.6,0.01)$ 仍通过；$(0.65,0.01)$ 也通过并作为边界案例，故不再称 $e=0.6$ 为最高偏心严格点 | `[A/V]` |
| optical/UV 是否可预测 | 在明确的 modified-blackbody、角律和弱场直接像条件下，可输出 $F_{\nu}(i,\Phi)$、颜色、$T_{\rm bb}$、$R_{\rm bb}$、偏振和相位调制 | `[A/V]` |
| 相位调制是否来自自遮挡 | 严格参考源在 $i\le75^\circ$ 没有直线自遮挡；有效图谱中的调制来自非轴对称温度、投影、临边昏暗和 Doppler | `[V]` |
| X-ray 是否可发布 | 不可。自由--自由有效光深在 0.3 keV 全盘小于 1；LTE 束缚态又依赖未闭合的离化布居 | `[V/O]` |
| 静态 NLTE annulus 表能否直接接入 | Davis--Hubeny 2006 已发表表对当前 $(T_{\rm eff},m_{0},Q)$ 的联合覆盖面积为 0，且仅 $12.9\%$ 面积满足严格准静态指标 | `[L/V/O]` |
| 进动能否变成天数 | 旧 atlas 还不能。Phase 5B5 已实现模形 SHA-256 绑定的 $\Phi\leftrightarrow t-t_{0}$ 接口，并逐位回收约 $1.49$--$1.57\times10^{4}\ {\rm day}$ 的方程自洽候选周期；但常偏心 atlas 因与候选 $e(a)$ 形状差超过 $62\%$ 而被接口拒绝。Fig. 6/7、Eq. (48) 十倍归一化和绝对历元仍开放，故现有图谱仍只能输出无量纲相位 | `[L/A/V/O]` |
| 是否已经接近真实观测格式 | Phase 5A 已有 $F_{\lambda}$、红移、光度距离与银河系前景消光；尚未卷积真实仪器响应或实际采样 | `[L/A/V/O]` |
| corrected 裸盘是否允许双峰 | 允许；三种受控权重都产生双峰，但圆盘控制也产生双峰，真实线谱仍缺少 NLTE 发射与转移 | `[A/V/O]` |
| 静态 H/He 大气能否替换 modified-blackbody | 官方 TLUSTY 208 LTE/NLTE 控制通过，但 12 个实际准静态代表柱直接 LTE 接受数为 0；代表柱 03 的续接只到目标 $Q$ 的 91.296 倍 | `[V/O]` |
| 温度方程是否已经闭合 | Phase 7B4f 已在固定密度薄板层联立逐深度温度；零机械加热有稳定根，但把完整 ZO 近心点单面耗散沉积到该薄层时无根。结果要求先扫描有限耗散柱质量，尚不能替换 Phase 4 | `[A/V/O]` |
| 有限沉积柱能否承载完整 ZO 耗散 | 可以。声明温度域中最低采样稳定柱为 $1.5\ {\rm g\,cm^{-2}}$；$3\ {\rm g\,cm^{-2}}$ 逐深度根稳定，热时间约为轨道周期的 $6.55\times10^{-7}$ | `[A/V]` |
| 保持 ZO 几何的静力表是否通过 | 未通过。两种耗散律、12 个代表柱的 $H_{\rm static}/H_{\rm ZO}=0.292$--$0.356$，几何保持通过数均为 0/12；静态热根存在不等于静力几何自洽 | `[A/V/O]` |
| 周期动态柱的第一道守恒门是否通过 | 通过。Phase 7B4i 的局域能量、粒子、电荷和周期账本均闭合，且失去初态记忆；但时间和尤其深度人口尚未收敛，不能成为 Phase 4 表 | `[A/V/O]` |
| 自适应深度与高时间分辨率是否通过生产门 | 未通过。7B4j 的共享自适应网格改善全部共同分辨率的逐点误差，但恶化柱平均误差；16 对 24 单元逐点人口误差为 $0.05576$。512 对 1024 相位的温度/能流误差为 $7.313\times10^{-4}$，人口误差仍为 $1.281\times10^{-3}$ | `[A-classification/V/O]` |
| 双网格误差估计和 2048 相位审计改变了什么 | 时间门通过：1024 对 2048 相位的温度/能流和人口误差为 $2.418\times10^{-4}$、$3.991\times10^{-4}$。深度门仍失败：two-grid 16 的逐点人口与柱平均人口误差为 $0.1346$、$2.267\times10^{-3}$，且没有同时优于 fixed 16 和 gradient 16 | `[A-classification/V/O]` |
| 保守子单元能否关闭空间门 | 尚不能。制造前沿平均/最大误差分别改善 $1.900$/$1.932$ 倍，初态和动态限制守恒通过；但 32 对 64 有效深度的逐点 $T/\kappa_{\rm R}$ 与人口误差仍为 $1.520\times10^{-2}$、$0.1132$。柱平均量和前沿位置已通过，局域状态仍失败 | `[A-classification/V/O]` |
| 联合深度--时间参考是否通过 | 通过。7B4o 的独立 64×2048 解在 2 个周期后以 $4.114\times10^{-10}$ 闭合；1024 对 2048 的最大逐点人口差为 $2.887\times10^{-4}$，全部连续指标低于 $10^{-3}$，前沿状态零错配。下一微阶段获准进入非局域动态转移，但 2048 相位仍只是有限参考 | `[A-classification/V/O]` |
| 冻结非局域转移能否替代局域闭合 | 不能。7B4p 的形式解控制和时间轴通过，但正式角度、频率和深度门失败；扩散时间最高为 $0.7379P_{\rm orb}$，逐相位静态转移也缺少辐射储能。当前谱只作探索诊断 | `[A-classification/V/O]` |
| Phase 7B4q 是否关闭冻结形式解数值底座 | 关闭代表相位上的频率、角度和辐射转移深度门。正式配置为 N128 动态物质单元、每物质单元 16 个辐射子单元、160 个阈值显式节点和 16 阶角求积；但 N128 时间门与动态辐射储能仍未关闭 | `[A-classification/V/O]` |
| Phase 7B4r 是否关闭 N128 时间门 | 关闭。独立 N128×2048 解两周期闭合；1024 对 2048 最大逐点人口差为 $2.911\times10^{-4}$，全部联合指标通过且前沿状态零错配。它仍是局域闭合物质基线，不含辐射储能 | `[A-classification/V/O]` |
| Phase 7B4s 是否关闭动态辐射门 | 只关闭数值核门。全隐式 ALE 核的解析/守恒控制和 N128×2048 双频周期 pilot 通过；但 $v_{\rm max}/c=0.00803$，混合系速度项、160 频率、正式角度/辐射子网格收敛和温度--布居反馈尚未关闭 | `[A-classification/V/O]` |
| Phase 7B4t 是否关闭混合系门 | 只关闭组件门。完整 Lorentz 射线与守恒频率组、303 组实际呼吸控制和正性批量源迭代通过；153 组失败，160 个 Gauss 节点不能直接做 Doppler 控制体，Lorentz 源项尚未与 ALE 联立 | `[A-classification/V/O]` |
| Phase 7B4u 是否关闭实际多群连续系数门 | 关闭，但候选从运动学门的 303 组提高到 1205 组。168 个真实物态上 604 组以 $1.0093\times10^{-3}$ 轻微失败，1205 组以 $2.5271\times10^{-4}$ 通过；只授权下一步联立 ALE | `[A-classification/V/O]` |
| Phase 7B4v 是否关闭完整混合系 ALE 门 | 算子门关闭，生产频率门未关闭。零速度、移动平衡、同源呼吸与动态扩散四力均通过；1205 组在三个真实一步物态上的最坏动态原子率误差为 $1.2829\times10^{-2}$。19249 组只相对 38496 组有限参考通过，当前不选生产组数 | `[A-classification/V/O]` |
| Phase 7B4w 的阈值局域 P0 是否解决频率成本 | 没有。网格、移动平衡和算子门通过，三个真实状态的频率门在 18105 组通过；但它超过预声明的 4814 组效率上限，正式组件门失败且不选生产组数 | `[A-classification/V/O]` |
| Phase 7B4x 的普通对数 P1 是否在预算内关闭频率门 | 没有。P1 解析和移动平衡通过；2408 组的最大速度误差通过，但最大宽度变化/H I 率误差仍为 $2.4547\times10^{-3}$，且 153 组冷表层残差点被保留为算子失败 | `[A-classification/V/O]` |
| Phase 7B4y 的阈值局域 P1 是否优于普通 P1 | 没有。几何、移动平衡和算子门通过，但 2265 组最大宽度变化误差为 $3.4545\times10^{-3}$，高于普通 P1 的 $2.4547\times10^{-3}$ | `[A-classification/V/O]` |
| Phase 7B4z 的普通对数 P2 是否关闭同成本频率门 | 没有。移动平衡通过；1604 组、4812 自由度使最大速度误差通过，但最大宽度变化/H I 率仍为 $2.5472\times10^{-3}$，略高于同成本 P1；全部候选算子门也因保留的粗网格/limiter 失败点未通过 | `[A-classification/V/O]` |
| Phase 7B5a 的对数频率守恒 P1 是否解决坐标误差 | 没有。$Q=\nu I_{\nu}$ 的解析 Doppler 平移、Jacobians 和移动平衡通过；2408 组最大速度误差通过，但最大宽度变化/H I 率仍为 $2.4569\times10^{-3}$，与普通 P1 实质相同，且 153 组冷表层残差越门 | `[A-classification/V/O]` |
| Phase 7B5b 的 H I 率核网格是否在预算内控制目标率 | 没有。三档网格、移动平衡和全部 45 个实际算子门通过；但 4816 自由度下最大宽度变化/H I 率误差为 $2.1329\times10^{-3}$、$3.3565\times10^{-3}$、$5.6739\times10^{-3}$，无一通过。样本中最好的 $f=0.25$ 不获选择 | `[A-classification/V/O]` |
| Phase 7B5c 把 H I 率误差定位到哪里 | 两个移动状态的主导差位于 $13.60$--$13.71\ {\rm eV}$ Doppler 阈值带；最冷表层主导于 $13.71$--$24.59\ {\rm eV}$。末态参考谱压缩误差仅约 $10^{-12}$--$10^{-10}$，动态余项主导；三态无统一主导区，不授权新固定基函数 | `[A-classification/V/O]` |
| Phase 7B5d 是否定位到唯一动态子算子 | 没有。刚体 ALE 宽度控制几乎不改变误差，关闭散射也不稳定改善；$D=1$ 与关闭真实吸收/热发射都使两个移动状态误差降低 $99.9\%$ 以上。结果指向 Lorentz--真实连续碰撞交互，但尚未区分强度、消光和发射率搬移 | `[A-classification/V/O]` |
| Phase 7B5e 是否定位到唯一 Lorentz 分量 | 没有。no intensity Lorentz 的三态受控方程通过，并把两个移动误差降至完整值的 $1.424\%$/$1.331\%$；但 no extinction 和 no emissivity 至少有一个状态联立残差失败，不能参与唯一性分类。只授权单次强度平移审计 | `[A-classification/V/O]` |
| Phase 7B5f 的一次强度搬移是否产生动态误差 | 没有。同一解析输入的三态 P1/P0 H I 率差仅为 $2.38\times10^{-7}$、$3.17\times10^{-8}$ 和 $6.83\times10^{-8}$，输入/输出能量差低于 $5.4\times10^{-13}$。下一门定位真实碰撞固定点中的误差累积 | `[A-classification/V/O]` |
| Phase 7B5g 的误差何时在固定点中出现 | 不是第一步共同定型。最大速度在第 2 次、最大宽度在第 8 次才超过最终误差的 $50\%$；最终相对第 0 次放大 $1.79\times10^{4}$/$3.12\times10^{4}$，且主导区从 H I shoulder 迁移到 Doppler 带 | `[A-classification/V/O]` |
| Phase 7B5h 中新注入还是已有误差传播占主导 | 同输入单步注入占主导。15 个 P0/P1 下一截面逐位复现，H I 率账本残差不超过 $1.81\times10^{-16}$；两个移动状态的注入分量最低占绝对分量和的 $95.3\%$。不授权 Jacobian--vector 或算符修正，下一门拆频率分区与组内表示 | `[A-classification/V/O]` |
| Phase 7B5i 的同输入注入主要来自哪里 | 2408 组频率分区项稳定占两个移动状态绝对分量和的 $60.1\%$--$64.3\%$，同分区 P1--P0 项占其余约 $36\%$--$40\%$，且两者异号抵消。4816 组同成本 P0 在最大宽度第 4/8 次仍失败；只授权分区审计 | `[A-classification/V/O]` |
| Phase 7B5j 是否找到预算内 P0 分区 | 没有。普通对数、固定率核和 Doppler 像锚点在 4816 组内均失败；率核与锚点只在 9632 组通过，且没有相邻两档共同通过。Doppler 锚点不稳定优于率核，不获选择 | `[A-classification/V/O]` |
| Phase 7B5k 是否确认有限高分辨率参考并解决成本 | 9632/19264 组的率核与 Doppler 锚点均在全部 15 截面通过，最坏误差降至 $2.57\times10^{-4}$/$3.43\times10^{-4}$，有限参考得到确认；单单元时间和返回数组近线性增长，但原 4816 组效率门仍失败，生产表示未选择 | `[A-classification/V/O]` |
| Phase 7B5l 是否关闭局域多分辨率组件门 | 关闭。严格 1--2--4 层级、H/He 阈值、P0 守恒传递、8/16 阶指标和 4816 预算账本全部通过；预算网格为 4814 叶。但只在 24 个解析 boosted-Planck 控制谱上验证，尚未通过独立动态验证 | `[A-classification/V/O]` |
| Phase 7B5m 的冻结多分辨率网格能否通过独立实际态验证 | 不能。$n=0,2,4$ 的 9 个训练状态最坏误差为 $6.45865\times10^{-4}$，但未参与构网的 maximum width change、$n=8$ 为 $1.003468\times10^{-3}$；9632 组 master 在同一点通过。组数账本通过，完整效率门失败，未选择生产表示 | `[A-classification/V/O]` |
| Phase 7B5o 的 1--2--4 新表示是否通过全新联合留出 | 没有。7B5n 先因预注册状态不存在而作废且未改协议；7B5o 的协议、参考源、映射、算子和 9632 master 全部通过，但精确 4816 叶候选在 width-change q80 收敛态的 He II 率误差为 $1.000546\times10^{-3}$。不舍入为通过，生产表示仍未选择 | `[A-preregistered/V/O]` |
| Phase 7B5p 是否量到了 9632 的实际资源代价 | 量到单单元，不是全柱。10 个隔离进程全部通过完整性门；9632 的中位/最大峰值 RSS 为 $190.44/191.50\,\mathrm{MiB}$，算子增量内存和单步时间约为 4816 的 $2.04/1.94$ 倍。该证据不自动修改预算 | `[A-preregistered/V/O]` |
| Phase 7B5q 的完整固定点是否改变资源判断 | 没有出现新障碍。20 个新进程全部收敛；投影/默认初值需 29/43 次迭代，9632 默认初值中位时间为 $0.3668\,\mathrm{s}$，最大峰值 $209.44\,\mathrm{MiB}$。两种初值回到同一解，但这仍不是全柱门 | `[A-preregistered/V/O]` |
| Phase 7B5r 是否关闭 9632 的单单元角度--子网格门 | 没有。七个固定点的守恒、非负性和边界哈希全部通过；16/24 方向、16/32 子单元和联合 16×16/24×32 的最大误差为 $5.448\times10^{-3}$、$1.482\times10^{-2}$、$9.589\times10^{-3}$，均由 H I 率主导。失败点完整保留，生产配置为空 | `[A-preregistered/V/O]` |
| Phase 7B5s 的更细参考是否接受 32×32 | 没有。五个固定点和 $6\,\mathrm{GiB}$ 资源门通过，但 32/48 方向、32/64 子单元和联合 32×32/48×64 的最大误差为 $1.221\times10^{-3}$、$7.626\times10^{-3}$、$6.428\times10^{-3}$。角度接近门，辐射深度仍明显失败；生产配置为空 | `[A-preregistered/V/O]` |
| Phase 7B5t 是否关闭单单元生产输运门 | 是。特征分区角求积把 32/48 误差降到 $1.73\times10^{-5}$；守恒单元特征积分的 16/32、32/64 和联合误差为 $1.65\times10^{-4}$、$4.39\times10^{-5}$、$1.74\times10^{-4}$。接受 9632 组、32 方向、16 子单元 | `[A-preregistered/V/O]` |
| Phase 7B5u 是否准许当前实现直接运行完整柱 | 不准许。单数组为 $9.406\,\mathrm{GiB}$，已识别活跃集至少 $84.668\,\mathrm{GiB}$，是本机物理内存的 5.292 倍；586/2048 个相位还有两个掠射方向反向。必须先做流式分块和守恒 turning-ray 算子 | `[A-preregistered/V/O]` |
| Phase 7B5v 的首个流式实现是否通过 | 没有。turning-ray、最终固定点和资源门通过，但单次 stream256 映射误差为 $3.93775\times10^{-12}$，高于预注册的 $10^{-12}$ 门；失败原样保留 | `[A-preregistered/V/O]` |
| Phase 7B5w 是否修复频率切片依赖 | 是。局域交叠积分使合成切片、正式单次映射和收敛固定点与整体路径逐位相同；stream256 峰值 RSS 为 392.08 MiB，只授权完整深度单块资源探针 | `[A-preregistered/V/O]` |
| Phase 7B5x 的正式最坏整深度块是否可运行 | 可运行。4096 深度、32 方向、128 核心组的最坏块峰值 RSS 为 2863.14 MiB，总时间 10.83 s；但 9.66 s 集中在一次源映射，76 块外推约 12--14 min/次迭代，因此只授权性能架构决策 | `[A-preregistered/V/O]` |
| Phase 7B5y/7B5z 是否降低了最坏块时间 | 7B5y 的大批次候选失败并回退；7B5z 只延后中间迭代的重复末态诊断，输出逐位相同，算子中位时间降到 6.137 s，加速 1.574 倍 | `[A-preregistered/V/O]` |
| Phase 7B6a 是否完成完整柱固定点 | 没有。它完成全部 9632 组的一次源映射：两进程墙钟 244.88 s、峰值各约 2.9 GiB，但最大相对变化仍为 0.282899，只授权下一步收敛架构决策 | `[A-preregistered/V/O]` |
| Phase 7B6b--7B6h 是否找到安全加速 | 找到有限加速。无保护权重 1.2--1.8 首步即产生负强度；整态保护的 1.8 在单单元和最坏全深度块通过。向量 Aitken 在最坏块把同成本残差降到固定 1.8 的 0.2012，并在四次全频续算中把残差从 $1.7915\times10^{-3}$ 降到 $4.4303\times10^{-4}$ | `[A-preregistered/V/O]` |
| Phase 7B6i/7B6j 是否完成全柱固定点 | 没有。7B6i 因连续巨大但不满足正性的 Aitken 候选在第 12 次安全暂停；7B6j 的精确正性边界为 2.0，同成本残差只比固定 1.8 低 0.3166%。它授权继续研究低存储加速，不授权物质反馈或 Phase 4 替换 | `[A-preregistered/V/O]` |
| Phase 7B6k/7B6l 的低存储 Anderson 是否值得全频运行 | 不值得。Anderson(1) 的末次残差是向量 Aitken 的 1.475 倍；Anderson(2) 降到 0.825 倍，但没有通过预注册的 0.5 门。两者的提案均未被正性线搜索截短，因此这是收益不足，不是保护器误杀 | `[A-preregistered/V/O]` |
| Phase 7B6m/7B6n 是否已经达到科学泛函收敛 | 还没有。体积平均谱变化为 $8.965\times10^{-5}$，但边界代理谱变化为 $2.128\times10^{-3}$；正式 ALE 面通量复核仍为 $2.008\times10^{-3}$，总通量变化为 $1.326\times10^{-3}$，均高于 $10^{-3}$ | `[A-preregistered/V/O]` |
| Phase 7B6o--7B6r 是否关闭固定物质单相位全柱门 | 是。16 次可恢复续算后，正式面通量谱和总通量变化为 $5.054\times10^{-4}$、$4.339\times10^{-4}$。原两进程长寿命架构两次越过 6 GiB；四逻辑进程、两并发的回收架构逐位复现正式谱，峰值为 5259--5374 MiB，最终通过。只授权单次有界物质反馈，不授权全轨道或 Phase 4 | `[A-preregistered/V/O]` |
| Phase 7B7a--7B7k 是否已得到耦合新物质态 | 还没有。第二条固定时间层物质方向、第二次全频映射和全局正式反馈都已通过；原子率--四力体积 $L_{1}$ 差为 $7.990\times10^{-6}$。然而质量加权残差仍为 $0.1934$，最大单元残差为 $0.9971$。实测收缩恒定外推约需 70/4601 循环，故 7B7k 不授权继续朴素 Picard，只转入加速设计 | `[A-preregistered/A-resource-policy/V/O]` |
| Phase 7B8a--7B8c 的受保护割线是否被接受 | 没有。新全频映射与正式源项一致性、镜像、资源门都通过；质量加权残差从 $0.1934$ 降到 $0.1014$，但上一最难单元残差收缩因子为 $1.0305$，高于预注册的 $0.99$ 门。提案被拒绝，说明主要瓶颈是非局域刚性耦合而不只是单轮算力 | `[A-preregistered/V/O]` |
| Phase 7B8d--7B8f 的反馈感知回溯是否修复局域失败 | 没有。离散回溯预测选择 $\lambda=0.75$，但新全频映射后的质量加权、原最难单元和最大单元收缩分别为 $0.3449$、$1.0475$、$1.0857$；后两项严格失败。端点仿射残差不能代表表层真实非局域反馈，不再授权步长试探 | `[A-preregistered/V/O]` |
| 是否应先做 UVOT | 暂不。有限柱与局域 ZO 黑体的归一化谱形距离为 $1.239$，$\nu F_{\nu}$ 峰能量比为 $3.87$，按预先声明阈值属于大差异 | `[A-classification/V/O]` |

当前最强、可以被数据证伪的结论是：

> 在指定的局域谱、角分布和弱场传递闭合下，ZO 严格域裸偏心盘给出频率、倾角和进动相位
> 分辨的 optical/UV 连续谱与偏振预言。它尚不能自洽解释 optical/UV 与 X-ray 的相对强度。

完整推理、全部公式和阶段图的逐图分析见
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]。

---

## 3. 五分钟恢复项目状态

### 3.1 环境与测试

要求 Python 3.11 或更高版本，使用 `uv` 管理环境：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv sync --all-groups
uv run pytest -q
```

本 README 更新时的现场结果为 `690 passed in 63.82s`。以后应以当次测试输出为准，阶段文档
中的较小测试数只是历史快照。

### 3.2 重建当前优先产物

```bash
uv run python scripts/phase3_complete.py --output-dir outputs
uv run python scripts/phase4_final_atlas.py --output-dir outputs
uv run python scripts/phase5a_observer_frame_flambda.py --output-dir outputs
uv run python scripts/phase7a_static_annulus_audit.py --output-dir outputs
uv run python scripts/phase7b_periodic_column_control.py --output-dir outputs
uv run python scripts/phase7b2_transfer_controls.py --output-dir outputs
uv run python scripts/phase7b3_atomic_continuum_controls.py --output-dir outputs
uv run python scripts/phase7b4a_collisional_kinetics_controls.py --output-dir outputs
uv run python scripts/phase7b4b_orbit_coupled_kinetics.py --output-dir outputs
uv run python scripts/phase7b4c_prescribed_radiation_kinetics.py --output-dir outputs
uv run python scripts/phase7b4d_coupled_slab.py --output-dir outputs
uv run python scripts/phase7b4e_continuum_emission.py --output-dir outputs
uv run python scripts/phase7b4f_temperature_balance.py --output-dir outputs
uv run python scripts/phase7b4g_finite_deposition_column.py --output-dir outputs
uv run python scripts/phase7b4h_hydrostatic_table_gate.py --output-dir outputs
uv run python scripts/phase7b4i_periodic_dynamic_energy.py --output-dir outputs
uv run python scripts/phase7b4j_adaptive_dynamic_convergence.py --output-dir outputs
uv run python scripts/phase7b4k_error_estimated_dynamic_convergence.py --output-dir outputs --stage all
uv run python scripts/phase7b4l_conservative_subcell_reconstruction.py --output-dir outputs --stage all
uv run python scripts/phase7b4m_front_aware_variable_refinement.py --output-dir outputs --stage all
uv run python scripts/phase7b4n_joint_depth_time_reference.py --output-dir outputs --stage all
uv run python scripts/phase7b4o_high_depth_time_reference.py --output-dir outputs --stage all
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --output-dir outputs --stage all --workers 8
uv run python scripts/phase7b4q_threshold_quadrature.py --output-dir outputs --stage all --workers 8
uv run python scripts/phase7b4r_n128_time_reference.py --output-dir outputs --stage all
uv run python scripts/phase7b4s_implicit_ale_radiation.py --output-dir outputs --force
uv run python scripts/phase7b4t_mixed_frame_group_gate.py --output-dir outputs --force
uv run python scripts/phase7b4u_multigroup_continuum_gate.py --output-dir outputs --force
uv run python scripts/phase7b4v_mixed_frame_ale_gate.py --force
uv run python scripts/phase7b4w_threshold_frequency_groups.py --force
uv run python scripts/phase7b4x_p1_frequency_moments.py --force
uv run python scripts/phase7b4y_threshold_p1_gate.py --force
uv run python scripts/phase7b4z_p2_frequency_moments.py --force
uv run python scripts/phase7b5a_log_frequency_p1_gate.py --force
uv run python scripts/phase5b1_linear_apsidal_mode_gate.py --output-dir outputs
uv run python scripts/phase5b2_nonlinear_hamiltonian_gate.py --output-dir outputs
uv run python scripts/phase5b3_nonlinear_apsidal_benchmark_gate.py
uv run python scripts/phase5b3a_published_branch_inverse_audit.py
uv run python scripts/phase5b3b_full_2d_nonlinear_diagnostic.py
uv run python scripts/phase5b3c_printed_equation_path_audit.py
uv run python scripts/phase5b3d_public_source_availability_audit.py --force
uv run python scripts/phase5b4_strict_domain_candidate_timescale_gate.py
```

运行后优先检查：

1. `outputs/phase3_complete_report.json`：角分布、偏振、弱场像和再处理约束；
2. `outputs/phase4_complete_report.json`：动态 annulus 失效门和观察者图谱；
3. `outputs/phase5a_observer_flambda_report.json`：红移、距离、消光假设与守恒残差；
4. `outputs/phase5a_observer_flambda_spectra.png`：当前最接近直接观测格式的谱图；
5. `outputs/phase5b1_linear_apsidal_report.json`：线性拱点模、自由边界、GR 和物理尺度审计；
6. `outputs/phase5b3a_published_branch_inverse_audit_report.json`：published 分支反演、节点拓扑和时间轴授权；
7. `outputs/phase5b4_strict_domain_candidate_timescale_report.json`：候选周期、模形兼容和旧 atlas 授权；
8. `outputs/phase5b3d_public_source_availability_report.json`：公开来源哈希、arXiv 源包成员与外部请求边界；
9. `outputs/phase6_line_response_report.json`：条件性线核、双峰诊断与收敛边界；
6. `outputs/phase7a_static_annulus_report.json`：实际代表柱失败、官方控制和续接边界；
7. `outputs/phase7b_periodic_column_report.json`：周期背景、守恒率方程、解析控制与收敛。
8. `outputs/phase7b2_transfer_report.json`：频率--角度转移解析门、高光深压力测试与边界。
9. `outputs/phase7b3_atomic_continuum_report.json`：可追溯 H/He 原子率、静态耦合与开放物理。
10. `outputs/phase7b4a_collisional_kinetics_report.json`：碰撞率、详细平衡、固定松弛、ZO
    中面时标和收敛边界。
11. `outputs/phase7b4b_orbit_coupled_kinetics_report.json`：无辐射、电荷自洽的周期轨道动力学。
12. `outputs/phase7b4c_prescribed_radiation_report.json`：规定辐射场、热详细平衡、稀释敏感性
    与三条收敛轴。
13. `outputs/phase7b4d_coupled_slab_report.json`：固定板层的 $J_{\nu}$--布居--opacity 固定点。
14. `outputs/phase7b4e_continuum_emission_report.json`：基态 Milne 发射、光子率和固定温度能量账本。
15. `outputs/phase7b4f_temperature_balance_report.json`：逐深度温度、稳定根、无根门和直接加密。
16. `outputs/phase7b4g_finite_column_report.json`：有限沉积柱根、微物理边界、谱差和路线决策。
17. `outputs/phase7b4h_hydrostatic_gate_report.json`：静力厚度、压力剖面、收敛和动态路线门。
18. `outputs/phase7b4i_periodic_dynamic_report.json`：周期能量账本、人口、初态独立性和三轴收敛。
19. `outputs/phase7b4j_adaptive_convergence_report.json`：梯度自适应深度和 1024 相位审计。
20. `outputs/phase7b4k_depth_report.json`：双网格误差监视函数、嵌套深度与权重敏感性。
21. `outputs/phase7b4k_time_report.json`：512、1024、2048 相位直接时间审计。
22. `outputs/phase7b4k_error_estimated_convergence_report.json`：深度和时间准入门的合并决策。
23. `outputs/phase7b4l_complete_report.json`：保守子单元控制、空间收敛与后续准入判据。
24. `outputs/phase7b4m_complete_report.json`：前沿感知变量网格、空间门与联合参考准入判据。
25. `outputs/phase7b4n_complete_report.json`：64×1024 联合参考、耦合误差与下一时间门。
26. `outputs/phase7b4o_complete_report.json`：64×2048 独立参考、高深度时间门与下一阶段授权。
27. `outputs/phase7b4p_complete_report.json`：冻结非局域形式解、四轴收敛、准静态门和下一微阶段否决。
28. `outputs/phase7b4q_summary.json`：阈值求积、N128 物质参考和辐射子网格准入门。
29. `outputs/phase7b4r_summary.json`：N128×2048 有限物质时间门。
30. `outputs/phase7b4s_summary.json`：隐式 ALE 储能核、网格速度和双频周期 pilot。
31. `outputs/phase7b4t_summary.json`：完整 Lorentz、守恒频率组、正性迭代压力步和下一联立门。
32. `outputs/phase7b4u_summary.json`：真实 H/He 多群连续系数、原子率、净加热和
    1205 组准入判定。
33. `outputs/phase7b4v_summary.json`：完整 Lorentz--ALE 算子、真实一步状态频率加密和
    “1205 组失败、生产组数未选定”的阶段判定。
34. `outputs/phase7b4w_summary.json`：阈值局域 P0 的网格/算子控制、18105 组频率通过和
    4814 组效率门失败判定。
35. `outputs/phase7b4x_summary.json`：普通 P1 的同预算频率失败和粗网格算子失败。
36. `outputs/phase7b4y_summary.json`：阈值局域 P1 未优于普通 P1 的联合判定。
37. `outputs/phase7b4z_summary.json`：P2 同成本权衡、limiter 风险和失败授权边界。
38. `outputs/phase7b5a_summary.json`：log-P1 坐标控制、三状态误差及未授权判定。
39. `outputs/phase7b5b_summary.json`：H I 率核网格、三档聚焦敏感性、实际算子通过和
    动态频率失败判定。
40. `outputs/phase7b5c_summary.json`：H I 率有符号频段定位、末态投影与动态余项分解。
41. `outputs/phase7b5d_summary.json`：Lorentz、ALE、散射与真实连续碰撞的一因子控制。
42. `outputs/phase7b5e_summary.json`：强度、消光和发射率 Lorentz 分量控制。
43. `outputs/phase7b5f_summary.json`：同输入单次强度搬移控制。
44. `outputs/phase7b5g_summary.json`：固定点反馈截面和误差增长。
45. `outputs/phase7b5h_summary.json`：单步注入与已有误差传播账本。
46. `outputs/phase7b5i_summary.json`：频率分区与组内表示拆分。
47. `outputs/phase7b5j_summary.json`：三种非拟合 P0 分区审计。
48. `outputs/phase7b5k_summary.json`：9632/19264 组相邻收敛和资源账本。
49. `outputs/phase7b5l_summary.json`：局域多分辨率组件门。
50. `outputs/phase7b5m_summary.json`：冻结 4814 叶网格的独立留出失败。
51. `outputs/phase7b5n_protocol_feasibility_failure.json`：预注册 $n=12$ 状态不存在的协议失败。
52. `outputs/phase7b5o_summary.json`：新初始/收敛态联合门和 4816 叶 He II 失败。
53. `outputs/phase7b5p_resource_profile_summary.json`：10 个隔离进程的峰值 RSS、时间、哈希
    与未授权判定。
54. `outputs/phase7b5q_fixed_point_resource_summary.json`：20 个完整固定点进程、两种初值、
    收敛残差与资源包络。
55. `outputs/phase7b5r_joint_convergence_summary.json`：9632 组角度--辐射子网格联合失败门、
    七个隔离进程和连续量误差账本。

![Phase 7B5o joint validation errors](outputs/phase7b5o_validation_errors.png)

四个面板分别检验总能量与 H I、He I、He II 光致电离率。9632 组 master 的 12 个新状态
全部低于黑色 $10^{-3}$ 门；4816 叶候选只有右下角 width-change q80 收敛态的 He II
误差以 $1.000546\times10^{-3}$ 严格失败。黑叉保留了这个极窄但真实的失败，不能据前三个
面板通过就进入下游；完整协议、层级分配与资源图见
[[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o 报告]]。`[A/V/O]`

![Phase 7B5p isolated resource profile](outputs/phase7b5p_isolated_resource_profile.png)

左图怎么看：4816 与 9632 的五个新进程高水位点完全分离，但共同 Python/模块基线使总
峰值比只有约 $1.20$；扣除基线后的算子增量约翻倍。右图怎么看：单步算子时间约翻倍，
完整子进程墙钟受共同导入成本主导，不能用来外推全柱运行。完整边界见
[[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p 报告]]。`[A/V/O]`

![Phase 7B5q converged fixed-point resource](outputs/phase7b5q_fixed_point_resource.png)

左图怎么看：完整固定点循环复用主要数组，所以峰值没有按 29/43 次迭代倍增；最高的
$209.44\,\mathrm{MiB}$ 点没有删除。右图怎么看：默认初值需要 43 次迭代，9632 的中位
时间约为 4816 的 $2.01$ 倍；投影收敛源只需 29 次。完整边界见
[[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q 报告]]。`[A/V/O]`

![Phase 7B5r joint convergence](outputs/phase7b5r_joint_convergence.png)

左上和右上分别比较 8/16 对 24 方向、8/16 对 32 辐射子单元；左下是唯一预声明的
16×16 对 24×32 联合候选。H I/He I 率、平均强度和全谱 L1 差仍高于黑色 $10^{-3}$ 门，
所以不能据已经通过的 He II、逸出通量或物质加热选择配置。右下保留 24×32 参考的
$1046.47\,\mathrm{MiB}$ 峰值。详见
[[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r 报告]]。`[A/V/O]`

![Phase 7B5s refined joint convergence](outputs/phase7b5s_refined_joint_convergence.png)

左上图怎么看：32 对 48 方向已把最大差降到 $1.221\times10^{-3}$，但不能向下舍入为
通过。右上图怎么看：32 对 64 子单元的能量、H I/He I 率和谱 L1 仍约为
$0.68\%$--$0.76\%$，成为主瓶颈。左下图保留 32×32 对 48×64 的联合失败；右下图显示
最细单单元 48×64 的峰值为 $2876.00\,\mathrm{MiB}$，低于预注册资源上限。详见
[[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s 报告]]。`[A/V/O]`

![Phase 7B5t characteristic transport gate](outputs/phase7b5t_characteristic_transport_gate.png)

左上图确认旧迎风是一阶、新特征积分接近二阶；右上图显示特征分区把角误差从千分之一
降到约 $10^{-5}$；左下图保留旧迎风的失败并显示新方案两档深度均通过；右下图给出真实
单单元资源包络。详见
[[eccentric_tde_observer/docs/phase7b5t_characteristic_transport_gate|Phase 7B5t 报告]]。`[A/V/O]`

![Phase 7B5u full-column admission](outputs/phase7b5u_full_column_admission.png)

左上图把 16 GiB 物理内存与 $84.668\,\mathrm{GiB}$ 活跃集下界直接比较；右上图显示
近心点邻域的网格速度越过最小 $|\mu|$；左下图给出 586 个反向相位；右下图说明 256 组
流式块是合理的首次资源探针，但尚未成为生产块宽。详见
[[eccentric_tde_observer/docs/phase7b5u_full_column_admission|Phase 7B5u 报告]]。`[A/V/O]`

![Phase 7B5w translation-invariant remap gate](outputs/phase7b5w_translation_invariant_remap_gate.png)

左上图保留 7B5v 超门的单次映射误差，并显示 7B5w 已降为逐位相同；右上图的三个固定点
柱位于零是因为强度、谱和标量都逐位相同，并非缺测。左下图显示 stream256 在基本不增加
单单元时间的情况下把峰值 RSS 从 1251.75 MiB 降至 392.08 MiB；右下图确认新整体科学
积分量没有相对 7B5v 发生物理移动。详见
[[eccentric_tde_observer/docs/phase7b5v_streaming_turning_gate|Phase 7B5v 报告]]与
[[eccentric_tde_observer/docs/phase7b5w_translation_invariant_remap_gate|Phase 7B5w 报告]]。`[A/V/O]`

![Phase 7B5x full-depth block probe](outputs/phase7b5x_full_depth_block_probe.png)

左上图显示最坏块实测峰值为 2.80 GiB，低于 6 GiB 门；右上图定位一次源映射占绝大部分
时间；左下图说明 128 个核心组因 Doppler halo 扩为 263/397 个碰撞/外层组；右下图给出
四项冻结门均通过。该图只证明单块资源可行，没有证明完整柱固定点收敛。详见
[[eccentric_tde_observer/docs/phase7b5x_full_depth_block_probe|Phase 7B5x 报告]]。`[A/V/O]`

![Phase 7B6a full-frequency source iteration](outputs/phase7b6a_full_frequency_source_iteration.png)

左上图给出全部 76 块的实测时间和 halo 中段增耗；右上图显示两个进程负载几乎完全平衡；
左下图确认每进程峰值约 2.9 GiB；右下图显示一次全频映射墙钟约 245 s。该结果仍不是固定点
或动态连续谱，详见
[[eccentric_tde_observer/docs/phase7b5y_remap_batch_performance|Phase 7B5y 报告]]、
[[eccentric_tde_observer/docs/phase7b5z_lean_source_map|Phase 7B5z 报告]]与
[[eccentric_tde_observer/docs/phase7b6a_full_frequency_source_iteration|Phase 7B6a 报告]]。`[A/V/O]`

![Phase 7B6j positivity line search](outputs/phase7b6j_positivity_line_search.png)

左上比较共同第 13 次映射与两条第 14 次分支；右上显示正性边界权重为 2.0，固定对照为
1.8；左下给出同成本残差比，线搜索只改善约 $0.3166\%$；右下表明每次全频映射仍需
约 4--5 分钟。该图证明正性线搜索有效但收益有限，并不表示固定点已经完成。详见
[[eccentric_tde_observer/docs/phase7b6i_recoverable_convergence_pause|Phase 7B6i 暂停记录]]与
[[eccentric_tde_observer/docs/phase7b6j_positivity_line_search|Phase 7B6j 报告]]。`[A/V/O]`

![Phase 7B6m science functionals](outputs/phase7b6m_science_functionals.png)

左上图显示体积与光致电离代理均过 $10^{-3}$ 门，只有边界代理失败；右上和左下分别比较
相邻两次体积谱与边界谱；右下给出 H I、He I、He II 光致电离率代理的深度变化。体积量稳定
不能替代最终出射通量稳定。详见
[[eccentric_tde_observer/docs/phase7b6m_science_functionals|Phase 7B6m 报告]]。`[A/V/O]`

![Phase 7B6n formal face flux](outputs/phase7b6n_formal_face_flux.png)

上排比较由第 13、14 次状态分别执行完整形式输运得到的两侧 ALE 面通量及其差；左下显示谱形
与总通量两项仍高于 $10^{-3}$；右下记录每次正式复核约需 6.2 分钟。因此边界未收敛是真实的，
不是代理定义造成。详见
[[eccentric_tde_observer/docs/phase7b6n_formal_face_flux|Phase 7B6n 报告]]。`[A/V/O]`

![Phase 7B6o fixed two continuation](outputs/phase7b6o_fixed2_continuation.png)

左上显示第 15--30 次残差持续下降；右上显示总通量先过门、谱形在第 22 次后过门并继续获得
裕量；左下记录单次约 315--363 s；右下显示源映射阶段每进程低于 6 GiB。详见
[[eccentric_tde_observer/docs/phase7b6o_fixed2_continuation|Phase 7B6o 报告]]。`[A/V/O]`

![Phase 7B6r worker recycling](outputs/phase7b6r_worker_recycling.png)

左图保留最终正式谱与总通量门；中图显示四个短寿命逻辑进程的峰值均为约 5.3 GiB；右图
记录两批总墙钟约 383 s。它与 7B6p/7B6q 的长寿命进程资源失败共同证明：进程回收改变的
是内存高水位，不是科学结果。详见
[[eccentric_tde_observer/docs/phase7b6p_final_formal_flux|Phase 7B6p]]、
[[eccentric_tde_observer/docs/phase7b6q_resource_recheck|Phase 7B6q]]与
[[eccentric_tde_observer/docs/phase7b6r_worker_recycling|Phase 7B6r]]。`[A/V/O]`

![Phase 7B7a feedback coefficients](outputs/phase7b7a_feedback_coefficients.png)

左上比较 Milne 率积分与实验室四力逆变换得到的共动加热；右上显示两者的放大差异；左下是
三条基态光致电离率；右下给出镜面对称门。科学量通过，但标题保留原进程 6359 MiB 的资源
失败。详见[[eccentric_tde_observer/docs/phase7b7a_feedback_coefficients|Phase 7B7a]]。`[A/V/O]`

![Phase 7B7a-r resource closure](outputs/phase7b7ar_resource_closure.png)

左图确认两个超限 owner 的重新聚合数组逐位相同；中图显示一块一进程后最大峰值降到
4706 MiB；右图给出 38 块的隔离成本。详见
[[eccentric_tde_observer/docs/phase7b7ar_resource_closure|Phase 7B7a-r]]。`[A/V/O]`

![Phase 7B7b material response](outputs/phase7b7b_material_response.png)

左上把未接受候选与初态温度并列；右上和右下分别显示温度、物质能强迫远超 10% 门；左下
则显示布居变化很小。守恒通过不代表冻结辐射近似有效。详见
[[eccentric_tde_observer/docs/phase7b7b_material_response|Phase 7B7b]]。`[A/V/O]`

![Phase 7B7c timescale diagnosis](outputs/phase7b7c_timescale_diagnosis.png)

左上定位最短 10% 响应时间；右上给出失败深度；左下表明绝对净加热集中在小比例表层质量；
右下显示净加热来自大吸收与大发射的微小差。详见
[[eccentric_tde_observer/docs/phase7b7c_timescale_diagnosis|Phase 7B7c]]。`[A/V/O]`

![Phase 7B7d trust-region Picard direction](outputs/phase7b7d_trust_region_picard.png)

左上比较阻尼前后的温度；右上显示 5% 温度门实际限制了松弛因子；左下显示物质能方向仍在
信赖域内；右下验证布居和守恒。这里没有缩短物理步长，得到的只是可测试的非线性方向，
不是耦合固定点。详见
[[eccentric_tde_observer/docs/phase7b7d_trust_region_picard|Phase 7B7d]]。`[A/V/O]`

![Phase 7B7e radiation direction](outputs/phase7b7e_radiation_direction.png)

左上和左下显示一次辐射映射只带来弱物质残差收缩；右上给出局域加热反馈；右下确认辐射
方向及资源门。率积分--逆四力的一致性没有出现在图的通过门中，而在独立严格门上以
$5.500\times10^{-3}$ 失败，故没有继续迭代。详见
[[eccentric_tde_observer/docs/phase7b7e_radiation_direction|Phase 7B7e]]。`[A/V/O]`

![Phase 7B7f assembled-state formal diagnostics](outputs/phase7b7f_assembled_diagnostics.png)

左上保留阈值附近逐块的大有符号差；右上显示旧 halo 的频带累积留下 3.84%，而全局新 halo
在完整频带末端抵消到 $5.24\times10^{-5}$；左下比较拼接态的两条深度加热曲线；右下
显示三项正式门通过。详见
[[eccentric_tde_observer/docs/phase7b7f_assembled_diagnostics|Phase 7B7f]]。`[A/V/O]`

![Phase 7B7f-r resource closure](outputs/phase7b7fr_resource_closure.png)

左图确认率积分、共动直接源和逆四力三条数组逐位相同；中图显示 76 个短寿命进程全部低于
6 GiB；右图复现三项科学门。详见
[[eccentric_tde_observer/docs/phase7b7fr_resource_closure|Phase 7B7f-r]]。`[A/V/O]`

![Phase 7B7g assembled H/He atomic rates](outputs/phase7b7g_assembled_atomic_rates.png)

四个面板依次给出光致电离率、总复合系数、对 7B7f 加热的独立复现和资源门。
全局态加热体积 $L_{1}$ 复现误差为 $5.33\times10^{-14}$。详见
[[eccentric_tde_observer/docs/phase7b7g_assembled_atomic_rates|Phase 7B7g]]。`[A/V/O]`

![Phase 7B7h second fixed-time-level Picard direction](outputs/phase7b7h_second_picard_direction.png)

图中分开物理旧时间层、当前非线性迭代、完整候选和第二阻尼态，并确认没有把同一个
$889.42\,\mathrm{s}$ 物理步重复累加。详见
[[eccentric_tde_observer/docs/phase7b7h_second_picard_direction|Phase 7B7h]]。`[A/V/O]`

![Phase 7B7i second full-frequency radiation direction](outputs/phase7b7i_second_radiation_map.png)

左图保留精确零变化并显示全局辐射残差只占信赖门的 $6.73\times10^{-3}$；中图给出 76
个短进程资源；右图明确不在块内旧 halo 上宣称正式源项。详见
[[eccentric_tde_observer/docs/phase7b7i_second_radiation_map|Phase 7B7i]]。`[A/V/O]`

![Phase 7B7j second assembled feedback](outputs/phase7b7j_second_assembled_feedback.png)

左上显示三条能量交换路径重合；右上则显示质量加权固定点残差虽收缩到 $0.1934$，
表层最大残差仍为 $0.9971$。详见
[[eccentric_tde_observer/docs/phase7b7j_second_assembled_feedback|Phase 7B7j]]。`[A/V/O]`

![Phase 7B7k nonlinear cost decision](outputs/phase7b7k_nonlinear_cost_decision.png)

实测收缩小于 $1$ 说明方向并非发散，但恒定收缩外推约需 70 个质量加权循环或 4601 个
最差单元循环。因此否决继续朴素 Picard，转入受保护非线性加速设计。详见
[[eccentric_tde_observer/docs/phase7b7k_nonlinear_cost_decision|Phase 7B7k]]。`[A/V/O]`

![Phase 7B8a protected diagonal secant](outputs/phase7b8a_protected_secant.png)

受保护割线在不重复累计物理时间的条件下保持物质能量、粒子数和 H/He simplex；未经保护
的表层外推被一个全局信赖因子限制。冻结辐射预检查不能证明耦合收敛。详见
[[eccentric_tde_observer/docs/phase7b8a_protected_secant|Phase 7B8a]]。`[A/V/O]`

![Phase 7B8b secant radiation map](outputs/phase7b8b_secant_radiation_map.png)

割线物质态上的 9632 组全频映射以 $396.38\,\mathrm{s}$ 完成，最大进程 RSS 为
$4037\,\mathrm{MiB}$；这一步只授权正式反馈装配。详见
[[eccentric_tde_observer/docs/phase7b8b_secant_radiation_map|Phase 7B8b]]。`[A/V/O]`

![Phase 7B8c accelerated assembled feedback](outputs/phase7b8c_secant_feedback.png)

正式源项门通过，质量加权残差收缩到 $0.5244$ 倍；但上一最难单元扩大到 $1.0305$ 倍，
所以逐单元割线严格失败并被拒绝。详见
[[eccentric_tde_observer/docs/phase7b8c_secant_feedback|Phase 7B8c]]。`[A/V/O]`

![Phase 7B8d feedback-informed line search](outputs/phase7b8d_feedback_line_search.png)

固定候选 $0.25/0.50/0.75$ 中，端点仿射预测选择 $0.75$；三个预测残差门和物质守恒门
通过，但图中明确尚未重算中间态辐射。详见
[[eccentric_tde_observer/docs/phase7b8d_feedback_line_search|Phase 7B8d]]。`[A/V/O]`

![Phase 7B8e backtracked radiation map](outputs/phase7b8e_backtracked_radiation_map.png)

回溽物质态上的正式全频映射耗时 $393.01\,\mathrm{s}$，峰值 RSS 为
$4023.55\,\mathrm{MiB}$，所有数值与资源门通过。详见
[[eccentric_tde_observer/docs/phase7b8e_backtracked_radiation_map|Phase 7B8e]]。`[A/V/O]`

![Phase 7B8f backtracked assembled feedback](outputs/phase7b8f_backtracked_feedback.png)

质量加权残差收缩到 $0.3449$ 倍，但原最难单元和全柱最大残差分别扩大到 $1.0475$、
$1.0857$ 倍；三重门严格失败，回溯被拒绝。详见
[[eccentric_tde_observer/docs/phase7b8f_backtracked_feedback|Phase 7B8f]]。`[A/V/O]`

![Phase 7B9a Newton--Krylov component gate](outputs/phase7b9a_newton_krylov_component.png)

物理域编码把每个单元的正热能和 H/He simplex 写成四个无约束变量；实际 128 单元冻结
反馈控制在 15 次 Newton、30 次 $Jv$ 后把编码残差降到 $3.024\times10^{-11}$，制造
非局域系统也通过。该图没有使用新的全频映射。详见
[[eccentric_tde_observer/docs/phase7b9a_newton_krylov_component|Phase 7B9a]]。`[A/V/O]`

![Phase 7B9b recoverable residual interface](outputs/phase7b9b_recoverable_residual_interface.png)

图中区分单映射诊断和辐射内收敛残差，验证部分检查点拒绝、频率块与清单篡改检测、物理域
失败终态及合法残差恢复；生产检查点尺寸与 $9632\times32\times4096$ 布局一致。30 次
方向性 $Jv$ 的实测下界为 $5.69\,\mathrm{h}$，尚未包括辐射内迭代。详见
[[eccentric_tde_observer/docs/phase7b9b_recoverable_full_frequency_residual|Phase 7B9b]]。`[A/V/O]`

![Phase 7B9c low-rank preconditioner](outputs/phase7b9c_low_rank_preconditioner.png)

唯一可编码的 512 维实际方向性割线以 $1.121\times10^{-15}$ 满足低秩逆割线恒等式；
制造低秩系统的 GMRES 从 5 次降为 1 次。图同时显示跨深度稠密修正和信赖域几何，但现有
实际割线数只有 1 且尚非辐射内收敛残差，因此不授权直接 Newton 步。详见
[[eccentric_tde_observer/docs/phase7b9c_low_rank_preconditioner|Phase 7B9c]]。`[A/V/O]`

![Phase 7B9d inner-gate audit](outputs/phase7b9d_inner_gate_audit.png)

旧块内能量账本在四次方向性映射中均约为 $0.977$，不会随固定点迭代趋零，故被审计为
无效准入量；第一轮状态和失败协议完整保留。详见
[[eccentric_tde_observer/docs/phase7b9d_inner_gate_audit|Phase 7B9d]]。`[V/O]`

![Phase 7B9e2 minimal extension](outputs/phase7b9e2_science_functional_extension.png)

改用全局源变化和正式边界科学泛函后，附加映射 8--10 连续通过；最终源、边界谱和
bolometric 变化分别为 $5.53863\times10^{-5}$、$2.09312\times10^{-4}$ 和
$1.06225\times10^{-4}$。详见
[[eccentric_tde_observer/docs/phase7b9e_science_functional_continuation|Phase 7B9e--7B9e2]]。`[A/V/O]`

![Phase 7B9f converged feedback and residual](outputs/phase7b9f_converged_feedback_residual.png)

最后两态的 H/He 率和加热变化均低于 $10^{-3}$，可恢复基准物质残差正式完成；其
$L_{2}=15.5889$ 说明外层物质--辐射耦合仍远未收敛。详见
[[eccentric_tde_observer/docs/phase7b9f_converged_feedback_residual|Phase 7B9f]]。`[A/V/O]`

![Phase 7B9g Jv fidelity decision](outputs/phase7b9g_jv_fidelity_decision.png)

当前内层剩余变化约为预期有限差分信号的 $293.48$ 倍，因此严格全频 $Jv$ 不可辨识且
没有执行；只授权 $0.125$ 的有限受保护真残差试探。详见
[[eccentric_tde_observer/docs/phase7b9g_jv_fidelity_decision|Phase 7B9g]]。`[A/V/O]`

![Phase 7B9i finite material trial](outputs/phase7b9i_finite_trial_material.png)

有限候选通过温度、物质比能和 H/He simplex 信赖域，但这只是物质几何门，不是 $Jv$，
也不是已接受的非线性步。详见
[[eccentric_tde_observer/docs/phase7b9i_finite_trial_material|Phase 7B9i]]。`[A/V/O]`

![Phase 7B9j finite-trial cost decision](outputs/phase7b9j_finite_trial_cost_decision.png)

候选态前三轮全频映射的实测收缩因子为 $0.913614/0.920446$；最乐观外推下第 12 轮仍为
$4.52514\times10^{-3}$，预计第 56 轮、额外约 $6.82\,\mathrm{h}$ 才满足停止门。
因此当前 $\omega=1$ 续算被成本门拒绝；候选真残差尚未评价，不能物理拒绝候选。详见
[[eccentric_tde_observer/docs/phase7b9j_finite_trial_cost_decision|Phase 7B9j]]。`[A/V/O]`

![Phase 7B9k natural-block Aitken pilot](outputs/phase7b9k_block_aitken_pilot.png)

自然频率块 Aitken 将最近两步残差比分别改善到 $0.858451/0.868577$，边界谱和总能流也
单调改善；但它没有通过预注册的 $0.80$ 单步门，预计停止点仍在第 38 次映射，晚于资源
门的第 28 次。故停止这条标量加速路线；候选物理真残差尚未评价。详见
[[eccentric_tde_observer/docs/phase7b9k_block_aitken_pilot|Phase 7B9k]]。`[A/V/O]`

![Phase 7B9l representative-block source-iteration pilot](outputs/phase7b9l_block_implicit_pilot.png)

六个物理代表块各做 8 次块内散射源更新后，局域残差中位数仍为首步的 $0.64625$，He I
和软 X 块分别为 $0.85436/0.81926$；汇总成本却是单次更新的 $4.058$ 倍。边界谱稳定明显
快于体内场，不能据此宣布内收敛。故不授权约 $1662\,\mathrm{s}$ 的全频八更新映射；下一门
必须直接预条件散射算子。详见
[[eccentric_tde_observer/docs/phase7b9l_block_implicit_pilot|Phase 7B9l]]。`[A/V/O]`

![Phase 7B9m exact-positive dominant-mode pilot](outputs/phase7b9m_exact_positive_mode_pilot.png)

去掉历史 $5.87095$ 权重上界后，四个代表块接受了更大的未约束权重且仍保持非负；但新的
原输运映射显示，H I 两侧和 He I 块的体内残差反而放大 $14.3$、$16.6$ 和 $36.0$ 倍，
六块中位数为 $7.8478$。因此非负性不是充分条件，所有逐块标量外推路线正式关闭；下一步
必须处理多模散射算子。详见
[[eccentric_tde_observer/docs/phase7b9m_exact_positive_mode_pilot|Phase 7B9m]]。`[A/V/O]`

![Phase 7B9n multimode minimum-residual pilot](outputs/phase7b9n_multimode_krylov_pilot.png)

3/5/7 维未正则化残差子空间显著改善光学、H I 和软 X 块，但 He I 的新原算子残差仍放大
到 $1.6147$，四块中位数 $0.3819$ 未过 $0.25$ 门；7 维 Gram 条件数已升至
$10^{8}$--$5.6\times10^{10}$，仿射预言保真门也失败。故不运行约 $1954\,\mathrm{s}$ 的
全频版本，下一步必须先构造物理 ALI 预条件器。详见
[[eccentric_tde_observer/docs/phase7b9n_multimode_krylov_pilot|Phase 7B9n]]。`[A/V/O]`

![Phase 7B9cu protected Anderson slow-mode candidate](outputs/phase7b9cu_protected_anderson_tail.png)

冻结物质态的 Picard 慢模在长序列尾部仍未越过 $10^{-4}$；受保护 Anderson(1) 只用已有
尾部构造候选，把预测全局原算子残差从 $1.27557\times10^{-4}$ 降至
$6.00598\times10^{-5}$，并保持逐块有限、非负。该图只给出候选及其预注册保护门，预测值
随后必须由新的完整映射复核。`[A/V]`

![Phase 7B9cv fresh full-map validation](outputs/phase7b9cv_candidate_fresh_map.png)

全部 76 个自然频率块的 fresh map 给出真实残差 $6.0059811515\times10^{-5}$，与 Anderson
预测的相对差约为 $1.76\times10^{-10}$；边界谱和 bolometric 变化分别为
$4.97877\times10^{-7}$ 和 $1.29250\times10^{-7}$。运行保持 2 个 worker，峰值进程 RSS
为 $2788.97\,\mathrm{MiB}$。`[V]`

![Phase 7B9cw consecutive convergence confirmation](outputs/phase7b9cw_consecutive_confirmation.png)

第二次独立完整映射确认相邻输入态残差为 $5.96185\times10^{-5}$，边界谱和 bolometric
变化为 $4.76534\times10^{-7}$ 和 $1.25817\times10^{-7}$。两个连续 fresh-map 输入态
同时通过辐射残差与边界门，正式 H/He 反馈端点由此获准。`[V]`

![Phase 7B9dd finite material trial rejection](outputs/phase7b9dd_material_trial_rejection.png)

最后两态的光致电离、复合及三种加热变化全部低于 $10^{-3}$；图 (a) 给出最终 H/He
光致率深度结构，图 (b) 显示两条正式加热曲线几乎重合。右侧记录真正的物理拒绝：同一个
$0.125$ 物质响应在两态上都使气体热能失去正值。程序没有使用 clip、floor 或写出目标
残差。它只拒绝这个方向--步长组合，不能由一次失败宣布所有静态解不存在。详见
[[eccentric_tde_observer/docs/phase7b9cu_dd_fixed_radiation_and_material_gate|Phase 7B9cu--7B9dd]]。
`[A/V/O]`

![Phase 7B9de first dyadic material backtrack](outputs/phase7b9de_half_trial_material.png)

原 $0.125$ 物质候选被正式物理域门拒绝后，7B9de 在同一冻结编码方向上只构造第一次二分
候选 $0.0625$。最大温度、物质比能和布居变化分别为 $0.216307$、$0.0631827$ 和
$1.02511\times10^{-6}$；全部廉价物质门通过。He simplex 的最大闭合误差是一个机器
epsilon，采用由两次浮点加法给出的 $4\epsilon_{\rm mach}$ 界，没有重归一化。图 (c)
明确说明尚未计算新辐射和正式反馈，因此这不是已接受的非线性步。详见
[[eccentric_tde_observer/docs/phase7b9de_half_trial_material|Phase 7B9de]]。`[A/V/O]`

![Phase 7B9dv clean-boundary closeout](outputs/phase7b9dv_closeout.png)

Phase 7B9dv 按用户决定在完整 map 边界冻结当前结果。上面板显示 7B9dp 与 7B9du 去重后
49 个状态的残差由 $8.22621\times10^{-4}$ 单调降至 $2.10413\times10^{-4}$，但仍在
$10^{-4}$ 目标之上；中面板显示 $q$ 已接近 $0.992$，纯 Picard 进入低收益慢尾；下面板
显示两项边界变化已远低于 $10^{-3}$。这支持“边界量稳定、内部全态尚未严格收敛”，不支持
正式 H/He feedback pair、物质步接受或 observer atlas 替换。详见
[[eccentric_tde_observer/docs/phase7b9dv_closeout|Phase 7B9dv 收尾报告]]与
[[eccentric_tde_observer/docs/phase7_post_convergence_branch_contract|Phase 7 后续分支合同]]。`[V/O]`

为避免再新增两个 $9.40625\,\mathrm{GiB}$ 完整态，Phase 7B9df 先做零检查点内容读取的
元数据预检；获得用户定向批准后，Phase 7B9dg 顺序重算两个历史态的 SHA-256 并与冻结
记录完全匹配。授权只覆盖这两个命名路径，保留旧哈希和历史引用，三个当前收敛/审计态
不可修改；真正覆盖还必须等待固定物质辐射协议冻结。`[V-hash/A-resource/O]`

![Phase 5A 观察者系波长谱](outputs/phase5a_observer_flambda_spectra.png)

图中采用 $z=0.05$、$E(B-V)=0.03$、$R_{\rm V}=3.1$，只为演示观察者映射，
`event_fit=false`。左右面板分别是不加和加入银河系前景消光的方向分辨 $F_{\lambda}$；完整
读图说明见[[eccentric_tde_observer/docs/phase5a_observer_frame_flambda|Phase 5A 报告]]。

![Phase 5B1 物理进动尺度审计](outputs/phase5b1_precession_scale_audit.png)

左图把 ZO Eqs. (9)--(12)、(39) 的直接量纲账本与论文 Eq. (48) 印刷系数并列，二者在
$\widetilde{\omega}=0.1$ 时相差 $10.000862$ 倍；右图显示局域 GR 率随半长轴快速下降，
不能被当成无需压力通信的刚体进动率。线性求解器已通过，但高偏心源仍未获得 day 轴；
详见[[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1 报告]]。`[L/V/O]`

![Phase 5B2 非线性局域 Hamiltonian](outputs/phase5b2_hamiltonian_surface.png)

颜色面由 130 个非交叉 $(e,q)$ 状态逐点求三维周期呼吸后得到，说明高偏心 Hamiltonian
同时依赖偏心率和径向梯度，不能用 Phase 5B1 的常数线性系数外推。局域核及偏导已通过，
但该图不是全局本征模；详见
[[eccentric_tde_observer/docs/phase5b2_nonlinear_hamiltonian_gate|Phase 5B2 报告]]。`[L/V/O]`

![Phase 5B3 ZO Fig. 6 本征函数审计](outputs/phase5b3_fig6_profile_audit.png)

黑线是从原始矢量 Fig. 6 读出的 $\lambda_{e}=0.2$ 路径；蓝线是三维 Eqs. (34)/(38)
全局解；橙线是二维线性控制。三维解已通过两档 Hamiltonian 表、双端自由边界、射击--
配点互证和 Phase 5B1 线性极限，却不复现 published 曲线或频率。因此 Phase 5B3 的
方程内部门通过、文献基准门失败，绝对时间轴继续关闭；详见
[[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3 报告]]。[L/V/O]

![Phase 5B3a 已发表分支反演](outputs/phase5b3a_published_branch_inverse_audit.png)

左图把 Fig. 7 矢量数字化曲线与相同 $e_{\rm in}$ 上的三维 Eq. (38) 无节点延续并列；
18 个三维频率始终为正。右图显示
$e_{\rm in}(\widetilde{\omega}_{\rm pub}-\widetilde{\omega}_{\rm 3D})$ 只缓慢变化，
说明差异含明显的 $1/e_{\rm in}$ 型分量，但这只是诊断而非错误归因。线性强形式另行确认
只有高节点支在窄环端发散；published 原因仍未唯一定位，时间轴继续关闭。详见
[[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a 报告]]。[A/V/O]

![Phase 5B3b 完整二维非线性诊断](outputs/phase5b3b_full_2d_nonlinear_diagnostic.png)

左上说明完整二维非线性频率几乎与二维线性控制重合，而没有走向 published 分支；右上、
左下分别比较半径比 1.3 和 3 的 Fig. 6 模形，右下直接量化非线性频率修正只有
约 $10^{-3}$。二维完整公式的二阶展开、轨道求积、表偏导和 BVP 均通过，所以这个失败
排除了“只遗漏二维非线性”这一候选解释，却不能归因原作者未公开实现。详见
[[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|Phase 5B3b 报告]]。[L/A/V/O]

![Phase 5B3c 印刷方程与边界审计](outputs/phase5b3c_printed_equation_path_audit.png)

左上把主文 Eq. (38)、附录字面减号、完整二维和 published 频率并列；附录减号虽把频率
改成逆行，仍同时失败两个半径比。右下用原始 PDF 矢量折线估计边界切线：published
外端接近三维自由根，两个内端却明显偏离。源文件还含 Fig. 6 半径比倒写和 Eq. (48)
十倍归一化差。本阶段只缩小未公开实现的原因空间，不拟合新边界。详见
[[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c 报告]]。[L/A/V/O]

Phase 5B3d 又逐项查询期刊 Data Availability、Crossref、arXiv v2 源包、GitHub 与 Zenodo。
arXiv 的 28 个成员包含论文源、审稿意见和 17 个 PDF 图，但没有数值源文件；DOI 没有
dataset relation，标题/DOI/arXiv ID 的 GitHub 与 Zenodo 查询也为零。论文明确把底层数据
放在“向通讯作者合理请求”的边界。用户已授权并于 2026-08-30 发送唯一一封 Fig. 6/7
数值材料请求；当前等待作者回复，时间轴仍关闭。详见
[[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|Phase 5B3d 报告]]。[L/V/O]

![Phase 5B4 候选模形兼容门](outputs/phase5b4_mode_shape_compatibility.png)

方程自洽候选模从 $e_{\rm in}=0.60,0.65$ 分别降到
$e_{\rm out}=0.2171,0.2419$，而旧 atlas 保持常偏心。高偏心表、射击--配点和直接偏导
门均通过，直接 Eq. (39) 候选周期约为 $14907,15679\ {\rm day}$；但模形差超过 $62\%$，
所以不能只给旧 atlas 改横轴。详见
[[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4 报告]]。[A/V/O]

![Phase 5B5 模形绑定候选时间钟](outputs/phase5b5_mode_matched_time_axis.png)

左图显示候选本征模与常偏心 atlas 的径向模形分离；时间接口对两者的 profile fingerprint
逐字比较，因此旧 atlas 被直接拒绝。右图的实线是直接 Eq. (39) 候选相对天数，点线只保留
Eq. (48) 十倍归一化审计而不采用。相位--时间往返误差为
$8.88\times10^{-16}\,\mathrm{rad}$；没有绝对历元，也没有把候选日轴贴到现有谱图。详见
[[eccentric_tde_observer/docs/phase5b5_mode_matched_time_axis|Phase 5B5 报告]]。[A/V/O]

![Phase 5B6 equation-self-consistent candidate source](outputs/phase5b6_candidate_source_diagnostics.png)

用户批准后，Phase 5B6 没有给旧常偏心 atlas 换标签，而是从冻结的 $e(a)$ 与 $q(a)$
重新构造两条独立 ZO 候选源。左上显示偏心率向外下降；右上给出始终为正的 Jacobian
包络；下排分别显示近/远心点的 $H/r$ 与 ZO Eq. (55) 温度。两条候选均通过当前
$256\times128$ 原生网格的通用局域有效域接口，但正式网格收敛仍开放；它们的身份是
`[A-candidate]`，不是 published benchmark，旧常偏心分支继续保留为历史和圆盘极限
控制。详见
[[eccentric_tde_observer/docs/phase5b6_equation_self_consistent_candidate_source|Phase 5B6 报告]]。
`[A/V/O]`

![Phase 5B7 candidate validity convergence](outputs/phase5b7_candidate_validity_convergence.png)

Phase 5B7 在冻结原生径向节点上分别加密 $a$ 与 $E$/表面三角网格。图 (a) 表明
$e_{\rm in}=0.65$ Gaussian 候选的 $z_{\rm ph}/r\geq0.3$ corrected 面积分数收敛到
$0.0081109$；把径向和 $E$/三角末两级绝对差保守相加后，上界仍只有 $0.0081965<0.01$。
图 (b)--(d) 显示显式表面面积比、最小总垂向光深和最大表面斜率也稳定；所有
$z_{\rm ph}/r\geq1$ 面积分数为零。两条 `[A-candidate]` 因而关闭当前有效域收敛门，
但仍不是 published benchmark。详见
[[eccentric_tde_observer/docs/phase5b7_candidate_validity_convergence|Phase 5B7 报告]]。`[A/V/O]`

![Phase 5B8 candidate-source apsidal time mapping](outputs/phase5b8_candidate_source_time_mapping.png)

Phase 5B8 只对两条已经通过有效域门、且 $(a,e,q)$ 指纹完全匹配的方程自洽候选源建立
相对进动时间钟。$e_{\rm in}=0.60$ 与 $0.65$ 的周期分别为 $40.81395$ 年和
$42.92803$ 年，对应每年约 $8.8205^{\circ}$ 与 $8.3861^{\circ}$。左图给出
$\Phi\rightarrow t-t_{0}$，右图给出十年内累计相位；两图都没有绝对 $t_{0}$、
$\Phi_{0}$ 或事件 MJD。旧常偏心 atlas 与候选模形不一致，因此仍不得把这条时间轴贴到
旧图上。详见
[[eccentric_tde_observer/docs/phase5b8_candidate_source_time_mapping|Phase 5B8 报告]]。`[A/V/O]`

---

## 4. 阶段与可复现入口

| 阶段 | 关闭的问题 | 主要脚本 | 阶段说明 |
|---|---|---|---|
| 1A--1D | face-on 基线、面积、垂向闭合、Newtonian 射线 | `phase1_faceon_benchmark.py` 至 `phase1d_raytrace_benchmark.py` | [[eccentric_tde_observer/docs/phase1_baseline|1A]]、[[eccentric_tde_observer/docs/phase1d_raytrace|1D]] |
| 1E--1G | ZO 参考源、自适应热点、垂向闭合敏感性 | `phase1e_zo_constant_e_benchmark.py`、`phase1f_adaptive_surface_benchmark.py`、`phase1g_vertical_closure_benchmark.py` | [[eccentric_tde_observer/docs/phase1e_zo_reference|1E]]、[[eccentric_tde_observer/docs/phase1g_vertical_closure|1G]] |
| 1H--1I | $(e,\mathcal V)$ 有效域与严格域观察者谱 | `phase1h_validity_domain_benchmark.py`、`phase1i_strict_domain_spectra.py` | [[eccentric_tde_observer/docs/phase1h_validity_domain|1H]]、[[eccentric_tde_observer/docs/phase1i_strict_domain_spectra|1I]] |
| 2A--2D | 弱场频移、热化、能量守恒 modified-blackbody | `phase2a_weakfield_frequency_shift.py` 至 `phase2d_complete_summary.py` | [[eccentric_tde_observer/docs/phase2_complete|第二阶段完成报告]] |
| 3A--3D | H/He 非灰失效门、临边昏暗、偏振、弱场像、再处理约束 | `phase3_complete.py` | [[eccentric_tde_observer/docs/phase3_complete|第三阶段完成报告]] |
| 4A--4B | 动态柱到 annulus 接口、倾角--相位图谱与无量纲光变 | `phase4_final_atlas.py` | [[eccentric_tde_observer/docs/phase4_complete|第四阶段完成报告]] |
| 5A | 红移、光度距离、$F_{\nu}\leftrightarrow F_{\lambda}$、前景消光 | `phase5a_observer_frame_flambda.py` | [[eccentric_tde_observer/docs/phase5a_observer_frame_flambda|Phase 5A 报告]] |
| 5B1 | $e\to0$ 三维自由边界拱点本征模、GR 与物理尺度审计 | `phase5b1_linear_apsidal_mode_gate.py` | [[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1 报告]] |
| 5B2 | 三维非线性局域呼吸、$F(e,f)$、线性极限与偏导门 | `phase5b2_nonlinear_hamiltonian_gate.py` | [[eccentric_tde_observer/docs/phase5b2_nonlinear_hamiltonian_gate|Phase 5B2 报告]] |
| 5B3 | 三维全局非线性 BVP、双求解器互证与 ZO Fig. 6/7 基准审计 | `phase5b3_nonlinear_apsidal_benchmark_gate.py` | [[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3 报告]] |
| 5B3a | 18 点无节点连续追踪、$1/e_{\rm in}$ 差异诊断与线性节点拓扑 | `phase5b3a_published_branch_inverse_audit.py` | [[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a 报告]] |
| 5B3b | OL 完整二维非线性 Hamiltonian、二阶极限与 published 排除诊断 | `phase5b3b_full_2d_nonlinear_diagnostic.py` | [[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|Phase 5B3b 报告]] |
| 5B3c | 主文/附录符号、Fig. 6 caption 与 published 边界切线审计 | `phase5b3c_printed_equation_path_audit.py` | [[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c 报告]] |
| 5B3d | DOI、arXiv 源包、GitHub/Zenodo 与作者请求边界审计 | `phase5b3d_public_source_availability_audit.py` | [[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|Phase 5B3d 报告]] |
| 5B4 | 严格域高偏心候选周期、直接单位账本与常偏心 atlas 模形兼容门 | `phase5b4_strict_domain_candidate_timescale_gate.py` | [[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4 报告]] |
| 5B5 | 以精确径向模形指纹绑定候选本征频率与相对时间，并拒绝旧 atlas | `phase5b5_mode_matched_time_axis.py` | [[eccentric_tde_observer/docs/phase5b5_mode_matched_time_axis|Phase 5B5 报告]] |
| 5B6 | 用冻结的 $e(a),q(a)$ 重建方程自洽候选源并接入通用有效域接口 | `phase5b6_equation_self_consistent_candidate_source.py` | [[eccentric_tde_observer/docs/phase5b6_equation_self_consistent_candidate_source|Phase 5B6 报告]] |
| 5B7 | 对候选源的径向、近心点与显式表面三角网格关闭有效域收敛门 | `phase5b7_candidate_validity_convergence.py` | [[eccentric_tde_observer/docs/phase5b7_candidate_validity_convergence|Phase 5B7 报告]] |
| 5B8 | 为指纹匹配的方程自洽候选源建立相对拱点时间钟 | `phase5b8_candidate_source_time_mapping.py` | [[eccentric_tde_observer/docs/phase5b8_candidate_source_time_mapping|Phase 5B8 报告]] |
| 6 | corrected 曲面上的条件性 Halpha 运动学线核 | `phase6_line_response.py` | [[eccentric_tde_observer/docs/phase6_line_response|Phase 6 报告]] |
| 7A | 低温、极低 $Q$ 静态 H/He 环带可行性审计 | `phase7a_static_annulus_audit.py` | [[eccentric_tde_observer/docs/phase7a_static_annulus|Phase 7A 报告]] |
| 7B1 | 规定 ZO 背景、周期时间轴与守恒布居控制核 | `phase7b_periodic_column_control.py` | [[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 报告]] |
| 7B2 | 一维频率--角度静态/时间转移解析控制 | `phase7b2_transfer_controls.py` | [[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 报告]] |
| 7B3 | 可追溯 H/He 连续谱原子率与静态频率耦合 | `phase7b3_atomic_continuum_controls.py` | [[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 报告]] |
| 7B4a | H/He 碰撞电离、详细平衡三体逆率与固定背景松弛 | `phase7b4a_collisional_kinetics_controls.py` | [[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a 报告]] |
| 7B4b | 无辐射 ZO 周期中面的电荷自洽 H/He 基态动力学 | `phase7b4b_orbit_coupled_kinetics.py` | [[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 报告]] |
| 7B4c | 规定 Planck 场、逐相位光致电离率与周期基态布居耦合 | `phase7b4c_prescribed_radiation_kinetics.py` | [[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c 报告]] |
| 7B4d | 固定温度、固定密度板层的 $J_{\nu}$--基态布居--opacity 固定点 | `phase7b4d_coupled_slab.py` | [[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d 报告]] |
| 7B4e | 同截面基态 Milne 连续发射、Kirchhoff 自由--自由发射与固定温度能量账本 | `phase7b4e_continuum_emission.py` | [[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e 报告]] |
| 7B4f | 固定密度板层的规定加热、逐深度温度平衡、根拓扑与热稳定性 | `phase7b4f_temperature_balance.py` | [[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f 报告]] |
| 7B4g | 保持 ZO 总耗散的有限沉积柱、Compton/线边界、稳定根和连续谱差异门 | `phase7b4g_finite_deposition_column.py` | [[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 报告]] |
| 7B4h | ZO 约束 $n=3$ 柱、受控耗散、H/He Rosseland 扩散和静力几何准入门 | `phase7b4h_hydrostatic_table_gate.py` | [[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 报告]] |
| 7B4i | ZO 拉格朗日半柱的压缩功、基态电离能、周期扩散与守恒门 | `phase7b4i_periodic_dynamic_energy.py` | [[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 报告]] |
| 7B4j | 共享轨道的自适应质量网格、固定/自适应深度对照与 1024 相位时间审计 | `phase7b4j_adaptive_dynamic_convergence.py` | [[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase 7B4j 报告]] |
| 7B4k | 双网格误差估计、严格嵌套深度网格与 2048 相位时间审计 | `phase7b4k_error_estimated_dynamic_convergence.py` | [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 报告]] |
| 7B4l | 保守线性子单元、物理域限制、总比能反演与空间生产门 | `phase7b4l_conservative_subcell_reconstruction.py` | [[eccentric_tde_observer/docs/phase7b4l_conservative_subcell_reconstruction|Phase 7B4l 报告]] |
| 7B4m | 嵌入式守恒误差排序、可变子单元和有限 N=64 空间门 | `phase7b4m_front_aware_variable_refinement.py` | [[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 报告]] |
| 7B4n | 三色 Jacobian、整周期检查点、64×1024 联合参考和耦合收敛门 | `phase7b4n_joint_depth_time_reference.py` | [[eccentric_tde_observer/docs/phase7b4n_joint_depth_time_reference|Phase 7B4n 报告]] |
| 7B4o | 64×2048 独立周期参考、三档时间收敛和联合生产门 | `phase7b4o_high_depth_time_reference.py` | [[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o 报告]] |
| 7B4p | 冻结物质态非局域形式解、局域 Planck 偏差、四轴收敛和辐射时标门 | `phase7b4p_frozen_nonlocal_transfer.py` | [[eccentric_tde_observer/docs/phase7b4p_frozen_nonlocal_transfer|Phase 7B4p 报告]] |
| 7B4q | 阈值显式频率求积、N128 动态参考、稀疏界面解和独立辐射子网格 | `phase7b4q_threshold_quadrature.py` | [[eccentric_tde_observer/docs/phase7b4q_threshold_quadrature|Phase 7B4q 报告]] |
| 7B4r | N128×2048 独立周期物质参考、1024 对 2048 时间门和最差误差定位 | `phase7b4r_n128_time_reference.py` | [[eccentric_tde_observer/docs/phase7b4r_n128_time_reference|Phase 7B4r 报告]] |
| 7B4s | 移动柱上的全隐式 ALE 辐射储能、守恒账本、网格速度审计和双频周期 pilot | `phase7b4s_implicit_ale_radiation.py` | [[eccentric_tde_observer/docs/phase7b4s_implicit_ale_radiation|Phase 7B4s 报告]] |
| 7B4t | 完整 Lorentz 射线、阈值对齐守恒频率组、正性批量隐式迭代和动态扩散门 | `phase7b4t_mixed_frame_group_gate.py` | [[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t 报告]] |
| 7B4u | 真实 N128×2048 物态上的 H/He 组平均 opacity、Milne 发射、原子率和净加热门 | `phase7b4u_multigroup_continuum_gate.py` | [[eccentric_tde_observer/docs/phase7b4u_multigroup_continuum_gate|Phase 7B4u 报告]] |
| 7B4v | 完整 Lorentz 物质源与 ALE 储能/移动通量联立、四力控制和真实状态频率加密 | `phase7b4v_mixed_frame_ale_gate.py` | [[eccentric_tde_observer/docs/phase7b4v_mixed_frame_ale_gate|Phase 7B4v 报告]] |
| 7B4w | H/He 阈值局域有限体积 P0 网格、不规则守护组、真实状态精度与效率门 | `phase7b4w_threshold_frequency_groups.py` | [[eccentric_tde_observer/docs/phase7b4w_threshold_frequency_groups|Phase 7B4w 报告]] |
| 7B4x | 守恒可实现 P1 频率矩、完整 Lorentz--ALE 联立和普通对数网格成本门 | `phase7b4x_p1_frequency_moments.py` | [[eccentric_tde_observer/docs/phase7b4x_p1_frequency_moments|Phase 7B4x 报告]] |
| 7B4y | 阈值局域有限体积边界与 P1 频率矩联合精度门 | `phase7b4y_threshold_p1_gate.py` | [[eccentric_tde_observer/docs/phase7b4y_threshold_p1_gate|Phase 7B4y 报告]] |
| 7B4z | 守恒可实现 P2 频率矩、独立 Lorentz--ALE 联立和同成本三状态门 | `phase7b4z_p2_frequency_moments.py` | [[eccentric_tde_observer/docs/phase7b4z_p2_frequency_moments|Phase 7B4z 报告]] |
| 7B5a | $Q=\nu I_{\nu}$ 对数频率守恒 P1、平移式 Lorentz--ALE 和同预算三状态门 | `phase7b5a_log_frequency_p1_gate.py` | [[eccentric_tde_observer/docs/phase7b5a_log_frequency_p1_gate|Phase 7B5a 报告]] |
| 7B5b | H I 率核目标导向固定网格、三档聚焦敏感性和稳健选择门 | `phase7b5b_rate_kernel_grid_gate.py` | [[eccentric_tde_observer/docs/phase7b5b_rate_kernel_grid_gate|Phase 7B5b 报告]] |
| 7B5c | 失败候选的有符号 H I 率频段定位、参考谱投影和动态余项诊断 | `phase7b5c_signed_rate_error_localization.py` | [[eccentric_tde_observer/docs/phase7b5c_signed_rate_error_localization|Phase 7B5c 报告]] |
| 7B5d | 匹配候选/参考的 Lorentz、ALE 与连续碰撞一因子动态控制 | `phase7b5d_dynamic_operator_controls.py` | [[eccentric_tde_observer/docs/phase7b5d_dynamic_operator_controls|Phase 7B5d 报告]] |
| 7B5e | 匹配候选/参考的强度、消光和发射率 Lorentz 分量控制 | `phase7b5e_lorentz_component_controls.py` | [[eccentric_tde_observer/docs/phase7b5e_lorentz_component_controls|Phase 7B5e 报告]] |
| 7B5f | 同一解析输入的单次强度 Lorentz 搬移、能量和 H I 率门 | `phase7b5f_single_pass_intensity_transform.py` | [[eccentric_tde_observer/docs/phase7b5f_single_pass_intensity_transform|Phase 7B5f 报告]] |
| 7B5g | P1/P0 固定点只读截面、H I 率误差增长和阈值区迁移 | `phase7b5g_fixed_point_feedback_audit.py` | [[eccentric_tde_observer/docs/phase7b5g_fixed_point_feedback_audit|Phase 7B5g 报告]] |
| 7B5h | P1/P0 单步映射复现、同输入注入与已有误差传播账本 | `phase7b5h_recurrence_decomposition.py` | [[eccentric_tde_observer/docs/phase7b5h_recurrence_decomposition|Phase 7B5h 报告]] |
| 7B5i | 细 P0、同分区 P0、log-P1 与同成本 P0 的单步率账本 | `phase7b5i_partition_representation_split.py` | [[eccentric_tde_observer/docs/phase7b5i_partition_representation_split|Phase 7B5i 报告]] |
| 7B5j | 三种预声明 P0 分区、三档组数与全截面 H I 率收敛 | `phase7b5j_prescribed_partition_audit.py` | [[eccentric_tde_observer/docs/phase7b5j_prescribed_partition_audit|Phase 7B5j 报告]] |
| 7B5k | 两种通过分区的 9632/19264 组相邻收敛、时间与返回数组占用 | `phase7b5k_high_resolution_convergence.py` | [[eccentric_tde_observer/docs/phase7b5k_high_resolution_convergence|Phase 7B5k 报告]] |
| 7B5l | 严格嵌套 P0 粗细层、守恒传递、嵌入式 H/He 排序与叶预算 | `phase7b5l_multiresolution_component_gate.py` | [[eccentric_tde_observer/docs/phase7b5l_multiresolution_component_gate|Phase 7B5l 报告]] |
| 7B5m | 预声明训练/留出划分、冻结 4814 叶网格和实际动态独立验证 | `phase7b5m_actual_multiresolution_validation.py` | [[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|Phase 7B5m 报告]] |
| 7B5n | 1--2--4 新表示预注册与验证状态可实现性失败记录 | `phase7b5n_preregister_protocol.py` | [[eccentric_tde_observer/docs/phase7b5n_preregistered_protocol|Phase 7B5n 报告]] |
| 7B5o | 全新几何病例、初始/收敛态与联合能量/H/He 独立门 | `phase7b5o_initial_converged_validation.py` | [[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o 报告]] |
| 7B5p | 冻结 4816/9632 的隔离进程单单元峰值 RSS 与时间审计 | `phase7b5p_isolated_resource_profile.py` | [[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p 报告]] |
| 7B5q | 两种冻结初值下的完整固定点单单元峰值、时间和跨初值同解门 | `phase7b5q_converged_fixed_point_resource.py` | [[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q 报告]] |
| 7B5r | 9632 组下 8/16/24 方向、8/16/32 子单元和联合单单元门 | `phase7b5r_joint_convergence.py` | [[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r 报告]] |
| 7B5s | 9632 组下 24/32/48 方向、32/64 子单元和 32×32 更细候选门 | `phase7b5s_refined_joint_convergence.py` | [[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s 报告]] |
| 7B5t | 特征分区角求积、守恒单元特征积分、解析阶数和单单元联合生产门 | `phase7b5t_characteristic_transport_gate.py` | [[eccentric_tde_observer/docs/phase7b5t_characteristic_transport_gate|Phase 7B5t 报告]] |
| 7B5u | 2048 相位完整柱内存、特征线反向和流式分块准入审计 | `phase7b5u_full_column_admission.py` | [[eccentric_tde_observer/docs/phase7b5u_full_column_admission|Phase 7B5u 报告]] |
| 7B5v | 守恒 turning-ray、精确 Doppler halo 与流式固定点严格等价性门 | `phase7b5v_streaming_turning_gate.py` | [[eccentric_tde_observer/docs/phase7b5v_streaming_turning_gate|Phase 7B5v 报告]] |
| 7B5w | 频率切片平移不变局域交叠积分与正式 stream256 复验 | `phase7b5w_translation_invariant_remap_gate.py` | [[eccentric_tde_observer/docs/phase7b5w_translation_invariant_remap_gate|Phase 7B5w 报告]] |
| 7B5x | 最大速度相位的 4096 深度最坏频率块微物理、RSS 与单次源映射实测 | `phase7b5x_full_depth_block_probe.py` | [[eccentric_tde_observer/docs/phase7b5x_full_depth_block_probe|Phase 7B5x 报告]] |
| 7B5y | 独立列大批次性能候选、精确哈希与失败回退 | `phase7b5y_remap_batch_performance.py` | [[eccentric_tde_observer/docs/phase7b5y_remap_batch_performance|Phase 7B5y 报告]] |
| 7B5z | 中间 block-Jacobi 精简源映射与完整诊断延后 | `phase7b5z_lean_source_map.py` | [[eccentric_tde_observer/docs/phase7b5z_lean_source_map|Phase 7B5z 报告]] |
| 7B6a | 两进程、76 块、临时 memmap 的完整 9632 组单次源迭代 | `phase7b6a_full_frequency_source_iteration.py` | [[eccentric_tde_observer/docs/phase7b6a_full_frequency_source_iteration|Phase 7B6a 报告]] |
| 7B6b | 无保护全局超松弛与历史单单元严格参考 | `phase7b6b_relaxed_fixed_point.py` | [[eccentric_tde_observer/docs/phase7b6b_relaxed_fixed_point|Phase 7B6b 报告]] |
| 7B6c | 整态有限性--非负性保护的单单元松弛 | `phase7b6c_guarded_relaxation.py` | [[eccentric_tde_observer/docs/phase7b6c_guarded_relaxation|Phase 7B6c 报告]] |
| 7B6d | 最坏 4096 深度块的固定成本收缩门 | `phase7b6d_full_depth_contraction.py` | [[eccentric_tde_observer/docs/phase7b6d_full_depth_contraction|Phase 7B6d 报告]] |
| 7B6e | 2.0--2.4 扩展固定权重失败门 | `phase7b6e_extended_relaxation.py` | [[eccentric_tde_observer/docs/phase7b6e_extended_relaxation|Phase 7B6e 报告]] |
| 7B6f | 两进程四次全频率收缩与恢复检查点 | `phase7b6f_full_frequency_contraction.py` | [[eccentric_tde_observer/docs/phase7b6f_full_frequency_contraction|Phase 7B6f 报告]] |
| 7B6g | 最坏全深度块向量 Aitken 门 | `phase7b6g_vector_aitken.py` | [[eccentric_tde_observer/docs/phase7b6g_vector_aitken|Phase 7B6g 报告]] |
| 7B6h | 第 5--8 次全频率向量 Aitken 续算 | `phase7b6h_full_frequency_aitken.py` | [[eccentric_tde_observer/docs/phase7b6h_full_frequency_aitken|Phase 7B6h 报告]] |
| 7B6i | 原子清单保护的长续算及第 12 次安全暂停 | `phase7b6i_converged_full_frequency.py` | [[eccentric_tde_observer/docs/phase7b6i_recoverable_convergence_pause|Phase 7B6i 记录]] |
| 7B6j | 同起点正性边界线搜索与固定 1.8 分支对照 | `phase7b6j_positivity_line_search.py` | [[eccentric_tde_observer/docs/phase7b6j_positivity_line_search|Phase 7B6j 报告]] |
| 7B6k | 最坏全深度块的低存储 Anderson(1) 严格门 | `phase7b6k_anderson1.py` | [[eccentric_tde_observer/docs/phase7b6k_anderson1|Phase 7B6k 报告]] |
| 7B6l | 最坏全深度块的 Anderson(2) 终局局域门 | `phase7b6l_anderson2.py` | [[eccentric_tde_observer/docs/phase7b6l_anderson2|Phase 7B6l 报告]] |
| 7B6m | 保存的第 13--14 次全频状态科学泛函只读审计 | `phase7b6m_science_functionals.py` | [[eccentric_tde_observer/docs/phase7b6m_science_functionals|Phase 7B6m 报告]] |
| 7B6n | 第 13--14 次状态的正式 ALE 面通量双重复核 | `phase7b6n_formal_face_flux.py` | [[eccentric_tde_observer/docs/phase7b6n_formal_face_flux|Phase 7B6n 报告]] |
| 7B6o | 从第 14 次状态到第 30 次的可恢复固定 2 全频续算 | `phase7b6o_fixed2_continuation.py` | [[eccentric_tde_observer/docs/phase7b6o_fixed2_continuation|Phase 7B6o 报告]] |
| 7B6p | 第 29--30 次状态最终正式 ALE 面通量科学与资源门 | `phase7b6p_final_formal_flux.py` | [[eccentric_tde_observer/docs/phase7b6p_final_formal_flux|Phase 7B6p 报告]] |
| 7B6q | 第 29 次正式面通量逐位复现和原架构资源复验 | `phase7b6q_resource_recheck.py` | [[eccentric_tde_observer/docs/phase7b6q_resource_recheck|Phase 7B6q 报告]] |
| 7B6r | 四逻辑进程、两并发的短寿命工作进程终局资源门 | `phase7b6r_worker_recycling.py` | [[eccentric_tde_observer/docs/phase7b6r_worker_recycling|Phase 7B6r 报告]] |
| 7B7a | 从收敛正式映射提取共动 H/He 率、净加热和四力对照 | `phase7b7a_feedback_coefficients.py` | [[eccentric_tde_observer/docs/phase7b7a_feedback_coefficients|Phase 7B7a 报告]] |
| 7B7a-r | 对超限频率块执行一块一进程逐位资源闭合 | `phase7b7ar_resource_closure.py` | [[eccentric_tde_observer/docs/phase7b7ar_resource_closure|Phase 7B7a-r 报告]] |
| 7B7b | 实际相位时长的一次冻结辐射物质响应与信赖域门 | `phase7b7b_material_response.py` | [[eccentric_tde_observer/docs/phase7b7b_material_response|Phase 7B7b 报告]] |
| 7B7c | 失败物质响应的局域时间尺度、质量深度和大数抵消诊断 | `phase7b7c_timescale_diagnosis.py` | [[eccentric_tde_observer/docs/phase7b7c_timescale_diagnosis|Phase 7B7c 报告]] |
| 7B7d | 保持完整物理步长的阻尼物质 Picard 方向 | `phase7b7d_trust_region_picard.py` | [[eccentric_tde_observer/docs/phase7b7d_trust_region_picard|Phase 7B7d 报告]] |
| 7B7e | 阻尼物质态上的一次全频辐射方向及严格一致性门 | `phase7b7e_radiation_direction.py` | [[eccentric_tde_observer/docs/phase7b7e_radiation_direction|Phase 7B7e 报告]] |
| 7B7f | 在 76 个新核心拼接后重做共动率、直接源与逆四力正式诊断 | `phase7b7f_assembled_diagnostics.py` | [[eccentric_tde_observer/docs/phase7b7f_assembled_diagnostics|Phase 7B7f 报告]] |
| 7B7f-r | 一块一进程逐位复现全局拼接源项并关闭资源门 | `phase7b7fr_resource_closure.py` | [[eccentric_tde_observer/docs/phase7b7fr_resource_closure|Phase 7B7f-r 报告]] |
| 7B7g | 全局拼接辐射态上的 H/He 原子率与加热复现 | `phase7b7g_assembled_atomic_rates.py` | [[eccentric_tde_observer/docs/phase7b7g_assembled_atomic_rates|Phase 7B7g 报告]] |
| 7B7h | 从物理旧时间层构造第二条阻尼物质 Picard 方向 | `phase7b7h_second_picard_direction.py` | [[eccentric_tde_observer/docs/phase7b7h_second_picard_direction|Phase 7B7h 报告]] |
| 7B7i | 第二物质迭代态上的一次 9632 组全频辐射映射 | `phase7b7i_second_radiation_map.py` | [[eccentric_tde_observer/docs/phase7b7i_second_radiation_map|Phase 7B7i 报告]] |
| 7B7j | 第二全局辐射态正式源项、原子率和固定点残差 | `phase7b7j_second_assembled_feedback.py` | [[eccentric_tde_observer/docs/phase7b7j_second_assembled_feedback|Phase 7B7j 报告]] |
| 7B7k | 根据实测收缩和墙钟否决朴素 Picard 续算 | `phase7b7k_nonlinear_cost_decision.py` | [[eccentric_tde_observer/docs/phase7b7k_nonlinear_cost_decision|Phase 7B7k 报告]] |
| 7B8a | 用两个已验证反馈点构造守恒、物理域受保护的逐单元割线提案 | `phase7b8a_protected_secant.py` | [[eccentric_tde_observer/docs/phase7b8a_protected_secant|Phase 7B8a 报告]] |
| 7B8b | 在割线物质提案上完成一次 9632 组全频辐射验证映射 | `phase7b8b_secant_radiation_map.py` | [[eccentric_tde_observer/docs/phase7b8b_secant_radiation_map|Phase 7B8b 报告]] |
| 7B8c | 全局拼接正式源项、H/He 率和加速真残差门 | `phase7b8c_secant_feedback.py` | [[eccentric_tde_observer/docs/phase7b8c_secant_feedback|Phase 7B8c 报告]] |
| 7B8d | 用两个完整辐射反馈端点选择受保护离散回溯物质态 | `phase7b8d_feedback_line_search.py` | [[eccentric_tde_observer/docs/phase7b8d_feedback_line_search|Phase 7B8d 报告]] |
| 7B8e | 回溽物质态的一次 9632 组全频辐射验证映射 | `phase7b8e_backtracked_radiation_map.py` | [[eccentric_tde_observer/docs/phase7b8e_backtracked_radiation_map|Phase 7B8e 报告]] |
| 7B8f | 全局正式源项与质量加权、原最难、最大单元三重门 | `phase7b8f_backtracked_feedback.py` | [[eccentric_tde_observer/docs/phase7b8f_backtracked_feedback|Phase 7B8f 报告]] |
| 7B9a | 四分量物理域编码、矩阵自由 $Jv$、GMRES 与实际残差回溯组件门 | `phase7b9a_newton_krylov_component.py` | [[eccentric_tde_observer/docs/phase7b9a_newton_krylov_component|Phase 7B9a 报告]] |
| 7B9b | 区分单映射诊断与内收敛 Newton 残差的可恢复哈希状态机 | `full_frequency_residual_evaluation.py` | [[eccentric_tde_observer/docs/phase7b9b_recoverable_full_frequency_residual|Phase 7B9b 报告]] |
| 7B9c | 用一条实际方向性割线构造稠密低秩逆 Jacobian 预条件器并关闭制造系统门 | `phase7b9c_low_rank_preconditioner_gate.py` | [[eccentric_tde_observer/docs/phase7b9c_low_rank_preconditioner|Phase 7B9c 报告]] |
| 7B9d | 审计并拒绝不随固定点收敛的旧块内账本门 | `phase7b9d_inner_gate_audit.py` | [[eccentric_tde_observer/docs/phase7b9d_inner_gate_audit|Phase 7B9d 报告]] |
| 7B9e/e2 | 用全局源变化和边界科学泛函完成固定物质基准辐射内收敛 | `phase7b9e2_science_functional_extension.py` | [[eccentric_tde_observer/docs/phase7b9e_science_functional_continuation|Phase 7B9e--7B9e2 报告]] |
| 7B9f | 最后两态正式 H/He 反馈与可恢复基准物质残差 | `phase7b9f_converged_feedback_residual.py` | [[eccentric_tde_observer/docs/phase7b9f_converged_feedback_residual|Phase 7B9f 报告]] |
| 7B9g | 以实测内层剩余变化检验严格全频 $Jv$ 的可辨识度 | `phase7b9g_jv_fidelity_decision.py` | [[eccentric_tde_observer/docs/phase7b9g_jv_fidelity_decision|Phase 7B9g 报告]] |
| 7B9i | 构造 $0.125$ 有限受保护准 Newton 物质候选 | `phase7b9i_build_finite_trial_material.py` | [[eccentric_tde_observer/docs/phase7b9i_finite_trial_material|Phase 7B9i 报告]] |
| 7B9j | 以三轮实测收缩关闭候选态 $\omega=1$ 内层续算成本门 | `phase7b9j_finite_trial_cost_decision.py` | [[eccentric_tde_observer/docs/phase7b9j_finite_trial_cost_decision|Phase 7B9j 报告]] |
| 7B9k | 用三轮全频映射严格否决仍不够快的自然频率块 Aitken | `phase7b9k_block_aitken_pilot.py` | [[eccentric_tde_observer/docs/phase7b9k_block_aitken_pilot|Phase 7B9k 报告]] |
| 7B9l | 用六个物理代表块否决成本过高且收缩不足的块内重复散射源迭代 | `phase7b9l_block_implicit_pilot.py` | [[eccentric_tde_observer/docs/phase7b9l_block_implicit_pilot|Phase 7B9l 报告]] |
| 7B9m | 以精确逐块正性和新原算子残差终止无上界单模外推 | `phase7b9m_exact_positive_mode_pilot.py` | [[eccentric_tde_observer/docs/phase7b9m_exact_positive_mode_pilot|Phase 7B9m 报告]] |
| 7B9n | 用 3/5/7 维未正则化多模子空间定位 He I 慢模和预条件需求 | `phase7b9n_multimode_krylov_pilot.py` | [[eccentric_tde_observer/docs/phase7b9n_multimode_krylov_pilot|Phase 7B9n 报告]] |
| 7B9cu--dd | 受保护 Anderson 候选、两次 fresh map、正式 H/He 反馈和有限物质步物理域决策 | `phase7b9cu_protected_anderson_tail.py` 至 `phase7b9dd_material_trial_rejection.py` | [[eccentric_tde_observer/docs/phase7b9cu_dd_fixed_radiation_and_material_gate|Phase 7B9cu--7B9dd 报告]] |
| 7B9de | 沿冻结方向构造原失败步长的一次二分物质候选并关闭廉价物理域门 | `phase7b9de_build_half_trial_material.py` | [[eccentric_tde_observer/docs/phase7b9de_half_trial_material|Phase 7B9de 报告]] |
| 7B9dt | 对最后两态按自然频率块定位慢收缩自由度 | `phase7b9dt_two_state_slow_mode_locator.py` | [[eccentric_tde_observer/docs/phase7b9dt_two_state_slow_mode_locator|Phase 7B9dt 报告]] |
| 7B9dv | 在完整 76 块边界冻结未严格收敛的固定物质辐射尾段 | `phase7b9dv_closeout.py` | [[eccentric_tde_observer/docs/phase7b9dv_closeout|Phase 7B9dv 收尾报告]] |

逐个脚本通常直接写入 `outputs/`。若只想恢复当前科学状态，不需要重新运行全部历史基准；
先运行测试和上节当前主脚本即可。

---

## 5. 输出文件怎样使用

### 5.1 文件类型

- `*_report.json`：机器可读的假设、数值、验证残差和科学边界；结论引用优先以它为准；
- `*.csv`：逐频率、方向、相位或收敛层级的数值结果，适合后续分析；
- `*.npz`：高维数组，目前主要是 Phase 4 annulus 坐标；
- `*.png`：诊断图和总图；图不能替代 JSON/CSV 中的数值与适用域；
- `docs/*.md`：阶段级物理说明；`lecture/*.md`：跨阶段讲义、文献地图和研究路线。

### 5.2 当前主文件

| 文件 | 用途 |
|---|---|
| `outputs/phase3_complete_summary.png` | optical/UV、偏振、弱场像与非灰失效门总览 |
| `outputs/phase4_complete_summary.png` | 动态大气桥与倾角--相位图谱总览 |
| `outputs/phase4_atlas_spectra.csv` | 全部 $F_{\nu},Q,U$ 图谱，是后续仪器响应的直接输入 |
| `outputs/phase4_atlas_diagnostics.csv` | 理想带通、黑体量、方向与有效性诊断 |
| `outputs/phase4_dimensionless_lightcurve.csv` | $t/P_{\rm prec}$ 无量纲光变 |
| `outputs/phase4_annulus_coordinates.npz` | $T_{\rm eff},m_{0},Q_{\rm tidal},Q_{\rm pressure},\epsilon_{\rm dyn}$ |
| `outputs/phase5a_observer_flambda_spectra.csv` | 逐方向、逐波长的 $F_{\nu}$、$F_{\lambda}$、$A_{\lambda}$ 与衰减后谱 |
| `outputs/phase5b1_linear_apsidal_report.json` | 线性本征频率、强--弱形式、自由边界、统一平移和 Eq. (48) 归一化审计 |
| `outputs/phase5b1_linear_apsidal_convergence.csv` | 四种径向范围、64--512 点、pressure only 与 pressure + GR 的完整收敛表 |
| `outputs/phase5b2_nonlinear_hamiltonian_report.json` | 非线性呼吸、Hamiltonian、线性极限、导数和下一阶段授权 |
| `outputs/phase5b2_hamiltonian_surface.csv` | $0\le e\le0.9$、$-0.75\le q\le0.75$ 的 130 个局域状态 |
| `outputs/phase5b3_nonlinear_apsidal_report.json` | 三维全局 BVP 内部门和 ZO Fig. 6/7 文献基准门 |
| `outputs/phase5b3_zo2020_fig6_comparison.csv` | published、三维非线性、三维线性与二维控制的频率和外边界偏心率 |
| `outputs/phase5b3a_published_branch_inverse_audit_report.json` | 18 点连续追踪、初值拒绝、节点拓扑和时间轴授权 |
| `outputs/phase5b3a_published_frequency_continuation.csv` | Fig. 7 数字化值与三维无节点解的逐点差异 |
| `outputs/phase5b3a_frequency_guess_robustness.csv` | 十个初始频率猜测的收敛或物理表域拒绝记录 |
| `outputs/phase5b4_strict_domain_candidate_timescale_report.json` | 高偏心方程门、候选周期、published 与 atlas 模形授权 |
| `outputs/phase5b4_candidate_timescales.csv` | 直接 Eq. (39) 和印刷 Eq. (48) 周期及 $e_{\rm out}/e_{\rm in}$ |
| `outputs/phase5b4_derivative_resolution_audit.csv` | 两档失败与最终通过的高偏心偏导留出序列 |
| `outputs/phase5b4_candidate_mode_profiles.csv` | 两个候选的 $e(a)$ 与 $q(a)$ 完整剖面 |
| `outputs/phase5b5_mode_matched_time_axis_summary.json` | 模形哈希门、候选物理时间钟与旧 atlas 拒绝结论 |
| `outputs/phase5b5_mode_matched_phase_schedule.csv` | 两条候选的 $0^\circ$--$345^\circ$ 相对天数模板；不属于旧 atlas |
| `outputs/phase5b6_candidate_source_report.json` | 两级模形指纹、候选源场、corrected 光度和首次有效域接口结果 |
| `outputs/phase5b6_candidate_source_radial_diagnostics.csv` | 两条候选的 $e,f,q,j,h,T_{\rm eff}$ 径向诊断 |
| `outputs/phase5b7_candidate_validity_convergence_report.json` | 两候选、两垂向闭合和两条加密轴的有效域收敛判决 |
| `outputs/phase5b7_candidate_validity_convergence.csv` | 径向与 $E$/三角分辨率下的 corrected 面积分数、光深和几何账本 |
| `outputs/phase5b8_candidate_source_time_mapping_report.json` | 候选本征频率、相对周期、指纹和时间轴授权账本 |
| `outputs/phase5b8_candidate_source_phase_schedule.csv` | 两条候选每 $15^{\circ}$ 的相对时间表；不含绝对历元 |
| `outputs/phase6_line_response_report.json` | 线传递、三种权重、分类敏感性、守恒和收敛总表 |
| `outputs/phase6_line_diagnostics.csv` | 三种权重的倾角--相位峰间距、峰比、质心、偏度和谷深 |
| `outputs/phase6_dynamic_spectrum.csv` | $i=60^\circ$ 的一个进动周期归一化动态线核 |
| `outputs/phase7a_static_annulus_report.json` | TLUSTY 构建、官方控制、12 个代表柱和续接边界 |
| `outputs/phase7a_representative_annuli.csv` | corrected 权重选出的真实柱、灰诊断与直接 LTE 失败记录 |
| `outputs/phase7a_rep03_continuation.csv` | 代表柱 03 固定 $T_{\rm eff},m_{0}$、只改变 $Q$ 的全部检查点 |
| `outputs/phase7b_periodic_column_report.json` | 周期背景、两态解析控制、守恒和收敛总表 |
| `outputs/phase7b_periodic_column_background.csv` | 代表柱 03 所在半长轴的一周 ZO 背景与时标 |
| `outputs/phase7b_kinetics_sensitivity.csv` | 四档无量纲响应时标的周期布居控制 |
| `outputs/phase7b2_transfer_report.json` | 真空、纯吸收、保守散射、静态极限和 ZO 高光深压力测试 |
| `outputs/phase7b2_convergence.csv` | 角、深度、频率、时间及高光深散射的分层收敛 |
| `outputs/phase7b2_transfer_controls.png` | Phase 7B2 四面板转移审计图 |
| `outputs/phase7b3_atomic_continuum_report.json` | Verner H/He 原子数据、详细平衡、静态耦合和阶段边界 |
| `outputs/phase7b3_convergence.csv` | 光致电离频率、转移角度和 ZO 垂向网格收敛 |
| `outputs/phase7b3_atomic_continuum_controls.png` | Phase 7B3 六面板原子率与静态耦合审计图 |
| `outputs/phase7b4a_collisional_kinetics_report.json` | Voronov 碰撞率、Saha 极限、固定松弛和 ZO 中面时标总表 |
| `outputs/phase7b4a_convergence.csv` | 电荷二分与 ZO 源相位网格两条收敛轴 |
| `outputs/phase7b4a_collisional_kinetics_controls.png` | Phase 7B4a 六面板碰撞动力学控制图 |
| `outputs/phase7b4b_orbit_coupled_kinetics_report.json` | 无辐射周期解、守恒、初值独立性和接受门总表 |
| `outputs/phase7b4b_periodic_kinetics.csv` | 一周动态、瞬时无辐射稳态和 LTE H/He 分数 |
| `outputs/phase7b4b_convergence.csv` | 非线性解析题、轨道时间步和源相位网格收敛 |
| `outputs/phase7b4b_orbit_coupled_kinetics.png` | Phase 7B4b 周期布居与缺失辐射诊断图 |
| `outputs/phase7b4b_orbit_coupled_kinetics_convergence.png` | Phase 7B4b 三条独立收敛轴 |
| `outputs/phase7b4c_prescribed_radiation_report.json` | 零场、热详细平衡、规定场敏感性和阶段边界总表 |
| `outputs/phase7b4c_prescribed_radiation_orbits.csv` | 全部稀释因子的逐相位光致率和 H/He 布居 |
| `outputs/phase7b4c_dilution_sensitivity.csv` | 连续 $W$ 扫描与动力学滞后诊断 |
| `outputs/phase7b4c_convergence.csv` | 光致频率、轨道时间步和源相位网格收敛 |
| `outputs/phase7b4c_prescribed_radiation_kinetics.png` | Phase 7B4c 规定场耦合四面板主图 |
| `outputs/phase7b4c_prescribed_radiation_convergence.png` | Phase 7B4c 三条独立收敛轴 |
| `outputs/phase7b4d_coupled_slab_report.json` | 固定板层反馈、固定点、守恒、验收门与阶段边界 |
| `outputs/phase7b4d_coupled_slab_depth.csv` | 逐深度 H/He 布居、电子密度和三条光致电离率 |
| `outputs/phase7b4d_coupled_slab_convergence.csv` | 频率、深度、角度和欠松弛四条独立扫描 |
| `outputs/phase7b4d_coupled_slab.png` | Phase 7B4d 衰减、布居、光深与初态收敛主图 |
| `outputs/phase7b4d_coupled_slab_convergence.png` | Phase 7B4d 收敛与透明--不透明反馈控制图 |
| `outputs/phase7b4e_continuum_emission_report.json` | Phase 7B4e 基态 Milne 发射、LTE/光子率/能量门和阶段边界 |
| `outputs/phase7b4e_emissive_slab_depth.csv` | Phase 7B4e 逐深度布居、辐射率和恒温能量项 |
| `outputs/phase7b4e_emergent_continuum.csv` | Phase 7B4e 入射、顶面向外与底面向外有限能段连续谱 |
| `outputs/phase7b4e_continuum_convergence.csv` | Phase 7B4e 频率、深度、角度、欠松弛和主配置加密 |
| `outputs/phase7b4e_continuum_emission.png` | Phase 7B4e 连续能流、布居、能量账本和初态控制主图 |
| `outputs/phase7b4e_continuum_convergence.png` | Phase 7B4e Kirchhoff、详细平衡、收敛和能量分配图 |
| `outputs/phase7b4f_temperature_balance_report.json` | Phase 7B4f 温度根、稳定性、完整耗散无根门和阶段边界 |
| `outputs/phase7b4f_temperature_profile.csv` | 零机械加热下逐深度温度、布居和能量残差 |
| `outputs/phase7b4f_isothermal_scan.csv` | 不同 ZO 耗散沉积分数的等温能量曲线 |
| `outputs/phase7b4f_temperature_convergence.csv` | 温度剖面和出射能流的频率、深度、角度直接加密 |
| `outputs/phase7b4f_temperature_balance.png` | 温度根拓扑、逐深度平衡、布居和连续谱对照 |
| `outputs/phase7b4f_temperature_convergence.png` | 直接加密、稳定性步长和无根门 |
| `outputs/phase7b4g_finite_column_report.json` | 有限柱根拓扑、逐深度稳定性、谱差分类与路线门 |
| `outputs/phase7b4g_column_topology.csv` | 沉积柱质量、根温度及温度域边界状态 |
| `outputs/phase7b4g_process_controls.csv` | 连续、Compton、线完全逃逸和联合控制 |
| `outputs/phase7b4g_emergent_continuum.csv` | 有限柱、连续基线与局域 ZO 黑体的顶部连续谱 |
| `outputs/phase7b4g_finite_column.png` | 有限柱根、微物理控制、温度剖面和能量账本 |
| `outputs/phase7b4g_convergence.png` | 直接加密、根带和归一化连续谱差异 |
| `outputs/phase7b4h_hydrostatic_gate_report.json` | 12 个代表柱的静力厚度、压力剖面、准入门和路线决策 |
| `outputs/phase7b4h_representative_hydrostatic_gate.csv` | 两种耗散律下逐代表柱的固定/压力匹配诊断 |
| `outputs/phase7b4h_convergence.csv` | 深度、频率和 opacity 迭代收敛 |
| `outputs/phase7b4h_hydrostatic_gate.png` | 静力厚度失配、压力根、剖面和扩散结构 |
| `outputs/phase7b4h_hydrostatic_convergence.png` | 厚度、压力残差和密度反转诊断收敛 |
| `outputs/phase7b4i_periodic_dynamic_report.json` | 周期动态能量、布居、守恒残差、分辨率与路线决策 |
| `outputs/phase7b4i_periodic_dynamic_phase.csv` | 两种耗散律下逐相位温度、通量、布居和能量项 |
| `outputs/phase7b4i_periodic_dynamic_profile.csv` | 主算例逐相位、逐拉格朗日深度的动态状态 |
| `outputs/phase7b4i_periodic_dynamic_convergence.csv` | 时间、质量深度和 Rosseland 频率三轴加密 |
| `outputs/phase7b4i_periodic_dynamic_column.png` | ZO 呼吸、动态温度、出射通量和基态人口 |
| `outputs/phase7b4i_energy_convergence.png` | 周期能量账本、热记忆和三轴收敛 |
| `outputs/phase7b4j_adaptive_convergence_report.json` | 自适应网格、深度/时间误差和准入决策 |
| `outputs/phase7b4j_adaptive_mass_edges.csv` | 四组自适应拉格朗日质量边界与等分残差 |
| `outputs/phase7b4j_adaptive_monitor.csv` | 轨道全局温度、opacity、He III 梯度监视函数 |
| `outputs/phase7b4j_depth_convergence.csv` | 固定/自适应深度的逐点、柱平均与前沿误差 |
| `outputs/phase7b4j_time_convergence.csv` | 128--1024 相位的温度、能流与人口误差 |
| `outputs/phase7b4j_adaptive_depth.png` | 英文四面板自适应质量网格与深度收敛图 |
| `outputs/phase7b4j_time_convergence.png` | 英文四面板高时间分辨率审计图 |
| `outputs/phase7b4k_error_estimated_convergence_report.json` | 双网格深度门和 2048 相位时间门的合并判据 |
| `outputs/phase7b4k_depth_report.json` | 双网格监视函数、嵌套深度误差和基线权重敏感性 |
| `outputs/phase7b4k_time_report.json` | 512--2048 相位的温度、能流、人口和守恒残差 |
| `outputs/phase7b4k_two_grid_monitor.csv` | 四个归一化误差分量和解析 $x^{2}$ 基线监视函数 |
| `outputs/phase7b4k_nested_mass_edges.csv` | 嵌套 8、16、32 单元质量边界与敏感性边界 |
| `outputs/phase7b4k_depth_convergence.csv` | fixed、gradient 和 two-grid 深度误差对照 |
| `outputs/phase7b4k_time_convergence.csv` | 512、1024、2048 相位时间误差 |
| `outputs/phase7b4k_two_grid_depth.png` | 英文四面板双网格误差与深度权衡图 |
| `outputs/phase7b4k_time_2048.png` | 英文四面板 2048 相位时间审计图 |
| `outputs/phase7b4l_control_report.json` | 制造前沿、父平均守恒和总比能温度反演控制 |
| `outputs/phase7b4l_subcell_report.json` | 16、32、64 有效深度的守恒、局域/积分误差与空间门 |
| `outputs/phase7b4l_complete_report.json` | Phase 7B4l 控制门和路线准入的合并判据 |
| `outputs/phase7b4l_manufactured_front.csv` | 移动 He III 制造前沿的解析、父常数和子单元值 |
| `outputs/phase7b4l_subcell_edges.csv` | 严格嵌套的父边界与保留子单元边界 |
| `outputs/phase7b4l_subcell_profiles.csv` | 三档有效深度的逐相位动态状态 |
| `outputs/phase7b4l_subcell_convergence.csv` | 表面能流、逐点、柱平均、前沿和守恒误差 |
| `outputs/phase7b4l_subcell_controls.png` | 英文四面板制造前沿与解析守恒控制图 |
| `outputs/phase7b4l_subcell_convergence.png` | 英文四面板保留子单元空间收敛图 |
| `outputs/phase7b4m_control_report.json` | 嵌入式守恒误差、网格预算和控制门 |
| `outputs/phase7b4m_complete_report.json` | 三个真实动态候选、空间门和联合参考准入判据 |
| `outputs/phase7b4m_convergence.csv` | N=56、60、62 的成本、局域/积分/前沿误差和逐点判据 |
| `outputs/phase7b4m_estimator_validation.csv` | 未加密 N=32 pilot 对有限 N=64 的独立排序验证 |
| `outputs/phase7b4m_candidate_parent_residuals.csv` | 三个加密候选的逐父单元残余误差 |
| `outputs/phase7b4m_embedded_refinement.png` | 英文四面板嵌入式误差、网格和表示控制图 |
| `outputs/phase7b4m_variable_convergence.png` | 英文四面板正式变量深度收敛图 |
| `outputs/phase7b4n_control_report.json` | dense 对三色三对角 Jacobian 数值等价与成本控制 |
| `outputs/phase7b4n_complete_report.json` | 64×1024 联合有限参考、空间/时间门和后续授权 |
| `outputs/phase7b4n_joint_convergence.csv` | N=64 的 512 对 1024 时间误差及 N=62 对 N=64 空间误差 |
| `outputs/phase7b4n_time_population_error_locations.csv` | H II/He III 最大时间差的相位和质量坐标定位 |
| `outputs/phase7b4n_energy_ledger.csv` | 三个正式算例的周期闭合与能量账本 |
| `outputs/phase7b4n_reference_phase.csv` | 64×1024 参考的逐相位积分量 |
| `outputs/phase7b4n_colored_jacobian_control.png` | 英文四面板 dense--colored 控制图 |
| `outputs/phase7b4n_joint_convergence.png` | 英文四面板联合深度--时间收敛图 |
| `outputs/phase7b4n_joint_reference_map.png` | 英文四面板 64×1024 动态温度与电离图 |
| `outputs/phase7b4o_complete_report.json` | 64×2048 有限参考、1024 对 2048 时间门和后续授权 |
| `outputs/phase7b4o_time_convergence.csv` | 512--1024--2048 高深度时间误差和有限缩减因子 |
| `outputs/phase7b4o_population_error_locations.csv` | 两次加密的 H II/He III 最大误差位置 |
| `outputs/phase7b4o_energy_ledger.csv` | 三档高深度周期解的闭合和能量账本 |
| `outputs/phase7b4o_reference_phase.csv` | 64×2048 有限参考的逐相位积分量 |
| `outputs/phase7b4o_time_convergence.png` | 英文四面板高深度时间收敛图 |
| `outputs/phase7b4o_reference_map.png` | 英文四面板 64×2048 动态温度与电离图 |
| `outputs/phase7b4p_complete_report.json` | 冻结非局域转移、局域闭合偏差、四轴门和后续路线 |
| `outputs/phase7b4p_convergence.csv` | 12 个代表相位的时间、角度、频率和深度误差 |
| `outputs/phase7b4p_extended_convergence.csv` | 71--519 频点与 4--24 方向扩展序列 |
| `outputs/phase7b4p_frozen_nonlocal_orbit.png` | 英文全轨道冻结通量、扩散时标与辐射失衡图 |
| `outputs/phase7b4p_nonlocal_spectra.png` | 英文探索性冻结谱、光深和光致率图 |
| `outputs/phase7b4p_convergence.png` | 英文四轴数值收敛图 |
| `outputs/phase7b4v_summary.json` | 完整 Lorentz--ALE 算子门、1205 组失败和后续授权边界 |
| `outputs/phase7b4v_actual_state_convergence.csv` | 三个真实一步物态从 303 到 38496 组的动态频率收敛 |
| `outputs/phase7b4v_mixed_frame_ale_controls.png` | 英文解析平衡、四力、真实残差与未设 floor 的高能尾诊断图 |
| `outputs/phase7b4v_actual_state_convergence.png` | 英文真实状态频率收敛、误差分量和成本图 |
| `outputs/phase7b4w_summary.json` | 阈值局域 P0 精度通过、效率失败和后续授权边界 |
| `outputs/phase7b4w_controls.csv` | 精确阈值、正组宽、Planck 积分恒等式与网格成本 |
| `outputs/phase7b4w_state_convergence.csv` | 三个真实一步物态在 568--18105 阈值局域组上的误差分量 |
| `outputs/phase7b4w_threshold_group_geometry.png` | 英文阈值局域有限体积几何与全局成本图 |
| `outputs/phase7b4w_actual_state_convergence.png` | 英文真实状态精度门、误差分量和一单元成本图 |
| `outputs/phase7b4x_summary.json` | 普通对数 P1 的解析控制、三状态精度失败和授权边界 |
| `outputs/phase7b4x_state_convergence.csv` | 153--2408 组普通对数 P1 的误差分量 |
| `outputs/phase7b4x_p1_frequency_convergence.png` | 英文普通 P1 精度曲线与最高预算误差拆分 |
| `outputs/phase7b4x_p1_operator_diagnostics.png` | 英文残差、账本、limiter 与成本诊断 |
| `outputs/phase7b4y_summary.json` | 阈值局域 P1 的几何/算子通过、频率失败和授权边界 |
| `outputs/phase7b4y_state_convergence.csv` | 143--2265 组阈值局域 P1 的误差分量 |
| `outputs/phase7b4y_threshold_p1_convergence.png` | 英文联合路线精度曲线与误差拆分 |
| `outputs/phase7b4y_threshold_p1_cost.png` | 英文一单元成本与可实现性 limiter 诊断 |
| `outputs/phase7b4z_summary.json` | 普通对数 P2 的解析控制、算子/三状态失败和授权边界 |
| `outputs/phase7b4z_state_convergence.csv` | 153--1604 组普通对数 P2 的误差分量 |
| `outputs/phase7b4z_p2_frequency_convergence.png` | 英文 P2 同成本精度曲线与最高预算误差拆分 |
| `outputs/phase7b4z_p2_operator_diagnostics.png` | 英文 P2 残差、账本、limiter 与成本诊断 |
| `outputs/phase7b5a_summary.json` | 对数频率守恒 P1 的解析控制、算子/三状态失败和授权边界 |
| `outputs/phase7b5a_state_convergence.csv` | 153--2408 组 log-P1 的误差分量 |
| `outputs/phase7b5a_log_p1_frequency_convergence.png` | 英文 log-P1 同预算精度曲线与最高预算误差拆分 |
| `outputs/phase7b5a_log_p1_operator_diagnostics.png` | 英文 log-P1 残差、账本、limiter 与成本诊断 |
| `outputs/phase7b5b_summary.json` | H I 率核固定网格的几何/算子通过、三档频率失败和授权边界 |
| `outputs/phase7b5b_state_convergence.csv` | 三档聚焦、153--2408 组的三状态误差分量 |
| `outputs/phase7b5b_rate_kernel_convergence.png` | 英文三状态频率收敛与 $10^{-3}$ 门 |
| `outputs/phase7b5b_rate_kernel_sensitivity.png` | 英文聚焦比例、组数分配、残差和 limiter 敏感性图 |
| `outputs/phase7b5c_summary.json` | 有符号率误差定位、参考谱投影、动态余项和授权边界 |
| `outputs/phase7b5c_signed_rate_profiles.csv` | 三状态逐能段候选/参考率、有符号差、绝对差和累计曲线 |
| `outputs/phase7b5c_signed_rate_error_localization.png` | 英文率差密度、累计误差和物理能段定位图 |
| `outputs/phase7b5c_projection_dynamic_decomposition.png` | 英文末态压缩、动态余项和可实现性参与诊断 |
| `outputs/phase7b5d_summary.json` | 五个匹配候选/参考控制、稳定误差降低和授权边界 |
| `outputs/phase7b5d_operator_controls.csv` | 三状态的受控率差、残差、账本与相对完整算子变化 |
| `outputs/phase7b5d_dynamic_operator_controls.png` | 英文一因子误差、符号响应、降低因子与残差图 |
| `outputs/phase7b5d_threshold_region_response.png` | 英文 H I 阈值带与 shoulder 响应热图 |

> [!warning] 历史图的使用边界
> `outputs/phase1e_zo_constant_e_observer.png` 是旧版探索图，当前脚本不再生成；其中高频
> 观察者曲线后来没有通过射线与源网格收敛。它只用于讲义中的失败历史，当前 Phase 1E
> 证据图是 `outputs/phase1e_zo_source_and_ray_audit.png`。

---

## 6. 代码结构

| 模块组 | 职责 |
|---|---|
| `source.py`、`zo_reference.py`、`reference_case.py` | 源契约、ZO 常偏心参考解和严格域参考点 |
| `vertical.py`、`photosphere.py`、`validity.py` | 垂向密度、灰光球与局域有效性门 |
| `geometry.py`、`observer.py`、`raytrace.py`、`adaptive.py` | 三角表面、投影、可见性、自遮挡和自适应积分 |
| `radiation.py`、`atmosphere.py`、`non_gray.py` | Planck 谱、热化、modified-blackbody 与 H/He 审计 |
| `atomic_continuum.py` | Verner H/He 基态光致电离、总辐射复合、最小稳态与正式 LTE 连续 opacity |
| `atomic_kinetics.py` | Voronov H/He 碰撞电离、详细平衡三体逆率、电荷自洽稳态与守恒松弛 |
| `orbital_kinetics.py` | 电荷自洽后向欧拉步、周期 H/He 基态动力学和无辐射轨道控制 |
| `prescribed_radiation.py` | 边分辨光致能量网格与规定 Planck 场到 H/He 基态率的接口 |
| `radiation_population_coupling.py` | 固定板层的布居依赖光致吸收、电子散射、$J_{\nu}$ 光致率和固定点迭代 |
| `continuum_emission.py`、`thermal_balance.py`、`static_atmosphere_energy.py` | 基态 Milne 连续发射、逐深度温度、有限沉积、Compton/线边界与热稳定性 |
| `hydrostatic_atmosphere.py` | ZO 约束有限 $n=3$ 柱、两种耗散律、H/He Rosseland 扩散和压力支撑审计 |
| `periodic_dynamic_atmosphere.py` | ZO 拉格朗日半柱的有限步压缩功、基态电离能、周期扩散、能量账本、共享自适应网格、三色 Jacobian 和整周期检查点 |
| `subcell_reconstruction.py` | 守恒线性子单元、H/He 人口单纯形限制、总比能温度反演和动态父单元限制 |
| `adaptive_subcell_refinement.py` | pilot 限制--再延拓缺陷、稳定误差排序和严格嵌套可变子单元网格 |
| `joint_dynamic_reference.py` | 独立时间重采样、严格嵌套空间比较、前沿状态和联合生产门 |
| `relativity.py`、`gr_transfer.py` | Doppler/引力频移和 Cunningham 式弱场直接像 |
| `polarization.py` | 临边昏暗和未分辨 Stokes $I,Q,U$ |
| `annulus_bridge.py` | 动态 ZO 柱到静态 annulus 坐标和禁外推表接口 |
| `time_series.py` | 倾角--相位图谱、理想 AB 带通、谐波和无量纲时间轴 |
| `observer_frame.py` | 红移、光度距离、$F_{\nu}\leftrightarrow F_{\lambda}$ 和前景消光 |
| `line_response.py` | 三种受控线权重、$g^4$ 窄线能流、$F_{\lambda}$ 与双峰连续诊断 |
| `phase7a.py`、`tlusty.py` | 准静态代表柱选择、TLUSTY 208 输入输出和严格失败保留 |
| `dynamic_column.py` | 规定 ZO 周期柱、耗散输入门和守恒周期率方程控制核 |
| `radiative_transfer_1d.py` | 一维频率--角度形式解、保守散射与时间依赖解析控制核 |
| `implicit_radiative_transfer_1d.py` | 移动网格隐式 ALE 辐射步、能量账本与正性批量源迭代 |
| `mixed_frame_frequency.py` | 完整 Lorentz 射线变换、阈值对齐频率组和守恒 Doppler 搬移 |
| `multigroup_continuum.py` | 组内正权积分、H/He 组平均连续系数、Milne 原子率与净加热 |
| `frequency_quadrature.py` | 阈值分段正权求积、超阈值坐标与显式有限体积频率边界 |
| `mixed_frame_ale.py` | 普通/任意物理边界的多层频率守护、完整 Lorentz 碰撞源、正性 ALE 扫掠、四力与能量账本 |
| `mixed_frame_ale_p1.py`、`mixed_frame_ale_p2.py` | 普通频率坐标上的可实现 P1/P2 Lorentz--ALE 表示 |
| `log_frequency_moments.py`、`log_multigroup_continuum.py`、`mixed_frame_ale_log_p1.py` | $Q=\nu I_{\nu}$ 的对数频率 P1、H/He Jacobian 和完整 ALE 联立 |
| `reprocessing.py` | 只计算未来再处理层的质量、光深、扩散、能量和动量约束 |

包采用 `src/` 布局；测试位于 `tests/`，脚本位于 `scripts/`。关键物理公式附近使用简洁中文
注释，具体规范见[[eccentric_tde_observer/docs/code_conventions|代码与 Markdown 规范]]；聊天中的
公式渲染见[[eccentric_tde_observer/docs/chat_output_standard|项目聊天输出规范]]。

---

## 7. 验证与拒绝原则

任何新增结果至少要保持以下控制：

- $e\to0$ 回到轴对称圆盘，方位与进动相位依赖消失；
- face-on、无遮挡、corrected ZO 2022 测度回收 Erratum Eq. (5)；
- 等温圆/椭圆环回收解析面积、投影和 Planck 谱；
- $g\to1$、$f_{\rm col}\to1$、$M/r\to0$ 回到较低层模型；
- modified-blackbody、临边昏暗和频率/波长变换分别保持相应能流；
- $\lambda F_{\lambda}=\nu F_{\nu}$，红移后 bolometric 通量满足光度距离定义；
- 源网格、射线/自适应深度、垂向网格、频率积分和相位网格分开收敛；
- 条件性线核另用解析部分遮挡夹具验证自遮挡边界上的 $g^4$ 线能流收敛；
- 纯散射无热化层、非有限值、非正物理量、超光速、视界内点、像折叠和无效发射角直接报错。

禁止用 `nan_to_num`、无物理依据的 `clip`、任意 floor 或事后重归一化掩盖无效状态。
`[A/V]`

---

## 8. 文档阅读顺序

第一次接手项目时按以下顺序阅读：

1. 本 README：确认目标、检查点、主产物和下一步；
2. [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]：理解完整因果链、公式来源和
   全部阶段图；
3. [[eccentric_tde_observer/docs/phase4_complete|Phase 4 完成报告]]：确认动态大气与观察者
   图谱边界；
4. [[eccentric_tde_observer/docs/phase5a_observer_frame_flambda|Phase 5A 报告]]：确认当前
   $F_{\lambda}$ 的观测映射和演示假设；
5. [[eccentric_tde_observer/docs/phase6_line_response|Phase 6 报告]]：确认运动学线核而非真实线谱；
6. [[eccentric_tde_observer/docs/phase7a_static_annulus|Phase 7A 报告]]：确认静态 H/He 求解器的
   控制、实际柱失败和续接边界；
7. [[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 报告]]：确认周期背景、守恒
   布居控制与尚未实现的辐射转移边界；
8. [[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 报告]]：确认转移解析极限、
   ZO 高光深压力测试及仍未闭合的物理；
9. [[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 报告]]：确认最小 H/He
   原子数据、阈值分段、静态耦合以及仍不能称为 NLTE 输出谱的边界；
10. [[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a 报告]]：确认碰撞率、
    三体详细平衡控制、固定松弛和 ZO 中面时标的适用边界；
11. [[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 报告]]：确认电荷
    自洽周期推进、初值独立性、三条收敛轴以及无辐射控制与 LTE 的物理差异；
12. [[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c 报告]]：确认
    规定场的零场回归、热详细平衡、稀释敏感性和频率/时间/源网格收敛；
13. [[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d 报告]]：确认固定板层的
    $J_{\nu}$--布居--opacity 固定点、初态独立性和四条收敛轴；
14. [[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e 报告]]：确认同截面
    Milne 发射、Kirchhoff/LTE 极限、光子率恒等式和固定温度能量账本；
15. [[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f 报告]]：确认逐深度温度、
    稳定根、完整耗散无根门和实际频率误差；
16. [[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 报告]]：确认有限
    沉积柱稳定根、Compton/线边界、连续谱差异与静态路线门；
17. [[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 报告]]：确认静态
    热根与保持 ZO 厚度的静力几何是两个不同准入门；
18. [[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 报告]]：确认周期
    动态柱的守恒基础和固定网格失败；
19. [[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase 7B4j 报告]]：确认
    自适应网格的局部/积分权衡与 1024 相位时间审计；
20. [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 报告]]：确认
    双网格误差估计不能修复空间表示，而 1024 对 2048 相位时间门已经通过；
21. [[eccentric_tde_observer/docs/phase7b4l_conservative_subcell_reconstruction|Phase 7B4l 报告]]：确认
    保守子单元改善制造前沿并保持守恒，但固定 2 子单元仍未关闭局域空间门；
22. [[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 报告]]：确认
    嵌入式排序、变量网格和有限 N=64 空间门；
23. [[eccentric_tde_observer/docs/phase7b4n_joint_depth_time_reference|Phase 7B4n 报告]]：确认
    64×1024 联合参考已完成，但高深度 512 对 1024 He III 时间门轻微失败；
24. [[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o 报告]]：确认
    64×2048 独立参考通过高深度时间门并关闭联合有限生产门；
25. [[eccentric_tde_observer/docs/phase7b4p_frozen_nonlocal_transfer|Phase 7B4p 报告]]：确认
    冻结非局域形式解守恒，但旧频率、角度、深度和准静态辐射门失败；
26. [[eccentric_tde_observer/docs/phase7b4q_threshold_quadrature|Phase 7B4q 报告]]：确认
    阈值显式求积、N128 动态参考和分离辐射子网格的通过项与开放项；
27. [[eccentric_tde_observer/docs/phase7b4r_n128_time_reference|Phase 7B4r 报告]]：确认
    N128×2048 独立参考和 N128 有限时间门通过，但动态辐射仍开放；
28. [[eccentric_tde_observer/docs/phase7b4s_implicit_ale_radiation|Phase 7B4s 报告]]：确认
    隐式 ALE 储能核和双频周期 pilot 通过，同时拒绝越过速度项与全频收敛门；
29. [[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t 报告]]：确认
    完整 Lorentz 与正性迭代组件门通过，同时保留 153 组失败和混合系 ALE 联立缺口；
30. [[eccentric_tde_observer/docs/phase7b4u_multigroup_continuum_gate|Phase 7B4u 报告]]：
    确认 604 组轻微失败、1205 组通过实际 H/He 连续系数与原子率门；
31. [[eccentric_tde_observer/docs/phase7b4v_mixed_frame_ale_gate|Phase 7B4v 报告]]：
    确认完整 Lorentz--ALE 算子门通过，但 1205 组动态原子率门失败且生产组数未选定；
32. [[eccentric_tde_observer/docs/phase7b4w_threshold_frequency_groups|Phase 7B4w 报告]]：
    确认阈值局域 P0 在 18105 组通过精度门、但因超过 4814 组上限而失败效率门；
33. [[eccentric_tde_observer/docs/phase7b4x_p1_frequency_moments|Phase 7B4x 报告]]：
    确认普通对数 P1 的解析回收与预算内动态 H I 率失败；
34. [[eccentric_tde_observer/docs/phase7b4y_threshold_p1_gate|Phase 7B4y 报告]]：
    确认阈值局域 P1 算子通过，但精度未优于普通 P1；
35. [[eccentric_tde_observer/docs/phase7b4z_p2_frequency_moments|Phase 7B4z 报告]]：
    确认 P2 改善最大速度点，却仍未关闭最大宽度变化/H I 率和全部候选算子门；
36. [[eccentric_tde_observer/docs/phase7b5a_log_frequency_p1_gate|Phase 7B5a 报告]]：
    确认真正的对数频率守恒坐标仍未关闭最大宽度变化/H I 率门；
37. [[eccentric_tde_observer/docs/phase7b5b_rate_kernel_grid_gate|Phase 7B5b 报告]]：
    确认 H I 率核网格的算子门通过，但三档聚焦均未关闭同预算动态率门；
38. [[eccentric_tde_observer/docs/phase7b5c_signed_rate_error_localization|Phase 7B5c 报告]]：
    确认移动状态的误差集中于 H I Doppler 阈值带，但三态没有统一主导区；
39. [[eccentric_tde_observer/docs/phase7b5d_dynamic_operator_controls|Phase 7B5d 报告]]：
    确认瓶颈是 Lorentz 与真实连续碰撞交互，而非 ALE 宽度或散射单项；
40. [[eccentric_tde_observer/docs/phase7b5e_lorentz_component_controls|Phase 7B5e 报告]]：
    区分有效的强度关闭响应与未闭合的消光/发射率关闭控制；
41. [[eccentric_tde_observer/docs/phase7b5f_single_pass_intensity_transform|Phase 7B5f 报告]]：
    证明单次强度 Lorentz 搬移通过并把下一门转向固定点反馈累积；
42. [[eccentric_tde_observer/docs/phase7b5g_fixed_point_feedback_audit|Phase 7B5g 报告]]：
    证明误差随碰撞固定点递推放大，并定位两个移动状态的起始检查点；
43. [[eccentric_tde_observer/docs/phase7b5h_recurrence_decomposition|Phase 7B5h 报告]]：
    证明每步同输入离散注入主导，而已有误差传播仅为次要分量；
44. [[eccentric_tde_observer/docs/phase7b5i_partition_representation_split|Phase 7B5i 报告]]：
    分离频率分区与同分区 P1--P0 项，并检验同成本 P0；
45. [[eccentric_tde_observer/docs/phase7b5j_prescribed_partition_audit|Phase 7B5j 报告]]：
    比较三种非拟合 P0 分区并证明预算内无通过方案；
46. [[eccentric_tde_observer/docs/phase7b5k_high_resolution_convergence|Phase 7B5k 报告]]：
    确认两种候选的相邻高分辨率收敛并量化单单元资源占用；
47. [[eccentric_tde_observer/docs/phase7b5l_multiresolution_component_gate|Phase 7B5l 报告]]：
    验证严格嵌套、守恒传递、确定性指标和 4816 叶预算账本；
48. [[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|Phase 7B5m 报告]]：
    检查冻结网格的训练/验证隔离，并保留预算内留出失败；
49. [[eccentric_tde_observer/docs/phase7b5n_preregistered_protocol|Phase 7B5n 报告]]：
    冻结新表示与留出协议，并记录预注册状态不存在的协议可行性失败；
50. [[eccentric_tde_observer/docs/phase7b5o_preregistered_protocol|Phase 7B5o 预注册]]：
    冻结全新几何病例及按构造存在的初始态/收敛态；
51. [[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o 报告]]：
    验证 4816 叶分层候选和 9632 master 的联合能量/H/He 门；
52. [[eccentric_tde_observer/docs/phase7b5p_preregistered_resource_protocol|Phase 7B5p 预注册]]：
    冻结状态、子进程顺序、重复数、RSS 单位和授权边界；
53. [[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p 报告]]：
    测量 4816/9632 的隔离单单元峰值与运行时间；
54. [[eccentric_tde_observer/docs/phase7b5q_preregistered_fixed_point_resource_protocol|Phase 7B5q 预注册]]：
    冻结两种初值、20 个新进程、收敛门和未授权边界；
55. [[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q 报告]]：
    给出完整固定点的单单元时间、峰值和跨初值一致性；
56. [[eccentric_tde_observer/docs/phase7b5r_preregistered_joint_convergence_protocol|Phase 7B5r 预注册]]：
    冻结 9632 新预算、角度/子网格路径、联合连续量和下游未授权边界；
57. [[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r 报告]]：
    保留生产候选的角度、子网格和联合失败及单单元资源包络；
58. [[eccentric_tde_observer/docs/phase7b5s_preregistered_refined_joint_protocol|Phase 7B5s 预注册]]：
    冻结更细角度、子网格、联合比较和 $6\,\mathrm{GiB}$ 单进程资源门；
59. [[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s 报告]]：
    保留 32×32 候选的三项科学门失败并定位辐射深度瓶颈；
60. [[eccentric_tde_observer/docs/phase7b5t_preregistered_characteristic_transport_protocol|Phase 7B5t 预注册]]：
    冻结特征分区、精确单元特征积分、解析阶数与联合门；
61. [[eccentric_tde_observer/docs/phase7b5t_characteristic_transport_gate|Phase 7B5t 报告]]：
    接受 9632 组、32 方向、16 辐射子单元的单单元生产输运配置；
62. [[eccentric_tde_observer/docs/phase7b5u_preregistered_full_column_admission|Phase 7B5u 预注册]]：
    冻结完整柱内存和特征线方向门，不允许用删点或降频率预算绕过；
63. [[eccentric_tde_observer/docs/phase7b5u_full_column_admission|Phase 7B5u 报告]]：
    定量确认整体实现超内存并定位 586 个反向相位；
64. [[eccentric_tde_observer/docs/phase7b5v_preregistered_streaming_turning_protocol|Phase 7B5v 预注册]]与
    [[eccentric_tde_observer/docs/phase7b5v_streaming_turning_gate|Phase 7B5v 报告]]：
    验证 turning-ray 与流式固定点，并保留单次映射严格失败；
65. [[eccentric_tde_observer/docs/phase7b5w_preregistered_translation_invariant_remap|Phase 7B5w 预注册]]与
    [[eccentric_tde_observer/docs/phase7b5w_translation_invariant_remap_gate|Phase 7B5w 报告]]：
    用局域交叠积分关闭频率切片平移不变门；
66. [[eccentric_tde_observer/docs/phase7b5x_preregistered_full_depth_block_probe|Phase 7B5x 预注册]]与
    [[eccentric_tde_observer/docs/phase7b5x_full_depth_block_probe|Phase 7B5x 报告]]：
    实测最坏整深度块并定位内存已可行、算子时间仍昂贵；
67. [[eccentric_tde_observer/docs/phase7b5y_remap_batch_performance|Phase 7B5y 报告]]：
    保留大批次性能失败并恢复正式实现；
68. [[eccentric_tde_observer/docs/phase7b5z_lean_source_map|Phase 7B5z 报告]]：
    延后中间迭代的重复诊断并保持强度逐位相同；
69. [[eccentric_tde_observer/docs/phase7b6a_full_frequency_source_iteration|Phase 7B6a 报告]]：
    实测 76 块完整单次源映射的时间、内存、覆盖和临时状态清理；
70. [[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|Phase 5B3b 报告]]：
    恢复完整二维非线性 Hamiltonian，并排除其作为 published 差异来源；
71. [[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c 报告]]：
    检验主文/附录符号不一致、caption 倒写和 published 边界切线；
72. [[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|Phase 5B3d 报告]]：
    审计公开代码/数据入口并保留作者请求边界；
73. [[eccentric_tde_observer/docs/zo2020_author_source_request_draft|ZO 2020 作者请求及发送记录]]：
    只请求 Fig. 6/7 代码、原始数组和实现约定；已发送，当前等待回复；
74. [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]：选择后续里程碑；
75. [[eccentric_tde_observer/lecture/项目讲义/00_document_map|文档地图]]：按阶段或论文查证细节。

本地核心论文位于同级 `markdown_papers/`，其角色和 Obsidian 双链统一由文档地图维护。

---

## 9. 对下一次工作的明确交接

### 9.1 当前尚未完成

1. **真实仪器层**：Phase 5A 尚未卷积 Swift/UVOT 等真实有效面积、零点、时间灵敏度和
   实际采样；XRT 必须等物理 X-ray 谱存在后再接入。
2. **绝对拱点进动**：Phase 5B1 已验证 $e\to0$ 线性模，Phase 5B2 已验证局域非线性
   Hamiltonian，Phase 5B3/5B3a 已完成全局 BVP 与 published 反演，Phase 5B3b/5B3c
   又排除完整二维非线性和附录印刷减号两种差异来源，并发现 published 内端切线不满足
   声明的三维自由根；Phase 5B3d 进一步确认公开入口没有求解器或原始数组，论文只承诺
   按合理请求共享；Phase 5B4 算出
   约 $14907$--$15679\ {\rm day}$ 的方程自洽候选周期，但候选 $e(a)$ 与旧常偏心 atlas
   的形状差超过 $62\%$。published 差异仍未唯一定位，论文 Eq. (48) 的印刷归一化还与
   Eqs. (9)--(12)、(39) 直接账本相差约十倍，所以不能把严格域源的
   $t/P_{\rm prec}$ 擅自换成 day。
3. **动态受辐照 NLTE 柱**：这是决定物理 X-ray 和真实局域角分布的核心缺口。Phase 7A
   已在 $\epsilon_{\rm dyn}<0.1$ 子集测试静态 H/He 环带，但 12 个实际代表柱均未通过；
   Phase 7B1 已完成规定背景和守恒率方程底座，Phase 7B2 已通过频率--角度转移解析控制，
   Phase 7B3 已加入可追溯 H/He 基态光致电离、总辐射复合和静态 opacity 耦合，Phase
   7B4a 又完成碰撞电离、详细平衡三体逆率与固定背景松弛；Phase 7B4b 已完成无辐射
   周期中面的电荷自洽轨道推进，并证明当前速率下时间滞后很小、缺失辐射过程造成的
   非 LTE 差异却很大；Phase 7B4c 已接入可关闭的规定 Planck 场并通过热详细平衡；Phase
   7B4d 又在固定 $T,\rho$ 的板层上把转移 $J_{\nu}$ 接回基态布居和 opacity；7B4e 再闭合
   同截面基态 Milne 发射和固定温度能量账本；7B4f 已求逐深度温度，并发现完整近心点
   单面耗散若沉积在当前薄层中无温度根；7B4g 随后证明有限沉积柱存在稳定静态根，并发现
   连续谱相对局域黑体有大差异；7B4h 的 ZO 约束静力柱没有通过厚度门；7B4i--7B4k 已建立
   守恒周期动态柱、梯度和双网格深度审计，并验证 1024 相位时间目标；7B4l 又实现保守子
   单元表示。7B4m 的前沿感知变量网格已关闭有限空间门；7B4n 又完成 64×1024 联合参考，
   并确认 1024 相位下 N=62 对 N=64 仍通过。7B4o 随后独立完成 64×2048，1024 对 2048
   的最大逐点人口差为 $2.887\times10^{-4}$，全部联合时间指标通过。7B4s 已进一步完成
   隐式 ALE 储能核和 N128×2048 双频周期 pilot，但它仍固定 7B4r 的温度/布居，只用
   10/60 eV 与 4 方向。7B4t 已补上完整 Lorentz 射线与守恒频率组组件，并证明 153 组
   轻微失败、303 组通过实际呼吸控制；正性批量迭代也通过 160 频率压力步。7B4u 又在
   168 个真实物态上关闭多群连续系数门：604 组轻微失败，1205 组通过。7B4v 已把完整
   Lorentz 碰撞源与 ALE 写入同一残差并通过解析平衡、四力、全局残差和能量账本门；但
   1205 组在真实移动一步状态的最大动态原子率误差为 $1.2829\times10^{-2}$。19249 组
   只相对 38496 组有限单元参考通过，代价和覆盖均不足以选为全轨道生产配置。7B4w 又
   测试阈值局域 P0：三个状态在 18105 组首次同时通过 $10^{-3}$，却超过预声明的 4814 组
   效率上限。7B4x 的普通对数 P1 和 7B4y 的阈值局域 P1 都改善了低成本误差，但在预算
   边界的最大宽度变化/H I 率误差仍分别为 $2.4547\times10^{-3}$ 和
   $3.4545\times10^{-3}$，没有生产表示。7B4z 的普通对数 P2 在同一预算下把最大速度
   状态降到 $7.5063\times10^{-4}$，但最大宽度变化/H I 率仍为
   $2.5472\times10^{-3}$，并保留非单调算子失败点，仍没有生产表示。7B5j--7B5k
   已确认 9632/19264 组有限 P0 参考；7B5l 建立的 4814 叶压缩又在 7B5m
   的独立留出末态以 $1.003468\times10^{-3}$ 严格失败。7B5n 保留了不可实现的预注册
   状态失败，7B5o 再用全新初始/收敛态验证 4816 叶 1--2--4 网格；候选 He II 最坏误差
   为 $1.000546\times10^{-3}$，而 9632 master 全部门通过。7B5p 已测得 9632 单单元
   一步映射的中位/最大进程峰值为 $190.44/191.50\,\mathrm{MiB}$；7B5q 的完整固定点
   资源包络又保留了 $209.44\,\mathrm{MiB}$ 的最高点。7B5r--7B6r 已继续关闭单单元
   角度--深度门和固定物质单相位全柱科学泛函门；7B7a--7B7a-r 又提取并通过共动 H/He
   率、四力和资源门。但 7B7b 的完整相位物质响应越过信赖域；7B7d 只接受一个阻尼物质
   方向，7B7e 完成一次辐射重映射；7B7f 已证明其旧 halo 一致性失败属于诊断时机，并在
   全局拼接态关闭科学门，7B7f-r 又关闭资源门。7B7g--7B7j 已完成全局原子率、
   第二物质方向、第二全频映射和正式反馈；但质量加权/最大固定点残差仍为
   $0.1934/0.9971$。7B7k 因实测成本不授权继续朴素 Picard。7B8a--7B8c 的受保护逐单元
   割线把质量加权残差降到 $0.1014$，却使上一最难单元残差扩大到 $1.0305$ 倍；该提案
   已按预注册规则拒绝。7B8d--7B8f 的反馈感知回溯又得到质量加权 $0.06672$，但原最难
   和全柱最大残差扩大到 $1.0475/1.0857$ 倍。7B9a 已通过四分量物理域编码、矩阵自由
   Newton--Krylov 及实际 128 单元冻结反馈控制；7B9b 又冻结可恢复全频残差状态机，并
   禁止把部分检查点或单次辐射映射当作 Newton 残差。7B9c 已得到一个只含 1 条实际
   方向性割线的低秩逆预条件器；7B9d 又拒绝了不随固定点收敛的旧块内账本门。7B9e/e2
   用全局源变化和边界科学泛函完成固定物质基准辐射内收敛，7B9f 再完成最后两态正式
   H/He 反馈和可恢复基准物质残差。7B9g 发现现有内层剩余变化是预期有限差分信号的
   $293.48$ 倍，故严格全频 $Jv$ 未执行。7B9i 的 $0.125$ 有限候选通过物理信赖域；
   7B9j 的三轮实测却证明当前 $\omega=1$ 和 12 轮预算不足，预计最早第 56 轮才通过。
   7B9k 的自然频率块 Aitken 把相邻残差比改善到 $0.858451/0.868577$，但未通过 $0.80$
   加速门，预计停止点仍为第 38 次。因此朴素续算和频率块标量松弛都已停止；下一步改测
   块内多次散射这一不同的算子层级。7B9l 又发现八次块内 Picard 的残差中位数仍为首步
   的 $0.64625$，成本却为 $4.058$ 倍，故没有投入全频映射；下一门必须直接预条件散射
   响应算子。7B9m 又证明取消经验权重上界后，大权重虽大多保持非负，却使阈值块新原
   算子残差放大最多 $35.96$ 倍。因此标量路线已经终局关闭，不把算法失败误写成候选物理
   失败。7B9n 的未预条件 7 维最小残差虽改善三个代表块，却使 He I 残差放大到
   $1.6147$，并暴露 $10^{8}$--$10^{10}$ 的 Gram 病态；下一步先做 ALI 物理预条件。
   仍没有激发态、总复合级联、收敛的全轨道全频动态
   非局域反馈或真实耗散剖面，因此没有 NLTE 输出谱。
4. **高倾角与完整 GR**：$i=80^\circ$ 的部分相位已因单值上光球角度失效而拒绝；多值光球、
   弯曲射线自遮挡、Kerr 多像、光行时和偏振平行移动仍未实现。
5. **观测人口与事件比较**：尚未接入真实误差、非探测、选择函数或宿主消光先验，也没有
   对任何单个 TDE 做参数拟合。
6. **真实原子线形成**：Phase 6 只有归一化运动学线核；NLTE 能级布居、光致电离、线自吸收、
   电子散射重分布和仪器线扩散函数仍未闭合。

### 9.2 推荐的执行顺序

Phase 7B5w 之后的工作仍必须逐小阶段验收。当前建议顺序为：

1. Phase 7B4p 已完成冻结物质态非局域形式解；形式解守恒和轨道相位轴通过，但 4 方向、
   71 频点与 N=64 深度配置未通过联合门，准静态辐射门也失败；
2. Phase 7B4q 已实现阈值显式权重和独立 N128 动态物质参考，并把动态物质网格与辐射转移
   子网格分离；每物质单元 16 对 32 子单元、160 对 304 频率节点和 16 对 24 角阶均通过；
3. Phase 7B4r 已独立完成 N128×2048 参考并关闭 1024 对 2048 有限物质时间门；
4. Phase 7B4s 已完成隐式 ALE 储能核和双频规定物质周期 pilot，但未授权正式动态谱；
5. Phase 7B4t 已通过完整 Lorentz、303 频率组实际呼吸控制和正性批量迭代组件门，但
   160 点 Gauss 求积不能直接承担守恒 Doppler 搬移，完整混合系轨道仍未授权；
6. Phase 7B4u 已证明 153、303、604 组不能同时满足真实 H/He 多群门，1205 组通过；
7. Phase 7B4v 已联立 1205 组 Lorentz 碰撞源与 ALE 输运，并通过零速度、刚体平移、同源
   呼吸、动态扩散四力和能量账本门；但 1205 组真实动态原子率门失败；
8. Phase 7B4w 已证明阈值局域 P0 需要 18105 组才通过三个真实一步状态，超过 4814 组
   效率上限，未选生产表示；
9. Phase 7B4x 已实现守恒 P1；2408 组普通对数 P1 仍在最大宽度变化状态失败，且 153 组
   冷表层残差失败点没有删除；
10. Phase 7B4y 已联合阈值局域边界与 P1；算子门通过，但 2265 组频率门失败且不优于普通
   P1；
11. Phase 7B4z 已实现普通对数 P2；最大速度状态通过，但最大宽度变化状态仍失败，且 P2
   limiter 暴露新的算子风险；
12. Phase 7B5a 已把 $y=\ln\nu$ 和 $Q=\nu I_{\nu}$ 纳入完整 Lorentz--ALE；结果与普通
   P1 实质相同；
13. Phase 7B5b 已否决未闭合的单一全局率矩捷径，并检验三档 H I 率核固定网格；全部
   网格、移动平衡和实际算子门通过，但三档最高预算仍都失败最大宽度变化/H I 率门；
14. Phase 7B5c 已固定失败候选完成有符号频段定位；移动状态的主导误差位于 H I Doppler
   阈值带，但最冷表层主导于更宽的 H I shoulder。末态压缩与饱和组不是直接主因；
15. Phase 7B5d 已完成动态子算子控制，并把误差缩小到 Lorentz--真实吸收/发射交互；
16. Phase 7B5e 已分别控制强度、消光和发射率 Lorentz 支路；只有 no intensity 控制
   数值可接受并稳定降低误差，另两个控制的失败点被保留；
17. Phase 7B5f 已证明同一输入谱的一次强度 Lorentz 平移通过，单次搬移不是动态主误差；
18. Phase 7B5g 已证明两个移动状态分别到第 2/8 次才超过最终误差的 $50\%$；
19. Phase 7B5h 已证明两个移动状态每个检查截面都由同输入单步注入主导，已有误差传播
   最多只占绝对分量和的 $4.71\%$；
20. Phase 7B5i 已加入候选分区 P0 与同自由度 P0 控制，并证明频率分区项稳定略占主导，
   但同分区 P1--P0 项不可忽略；4816 组 P0
   也没有关闭全部单步门；
21. Phase 7B5j 已固定 P0 比较普通对数、当前率核分区与 Doppler 像锚点，并证明预算内
   无分区通过；9632 组率核与 Doppler 锚点有限通过但没有
   相邻分辨率确认；
22. Phase 7B5k 已完成 19264 组相邻收敛和资源审计；两种候选均相邻通过，但原 4816 组
   效率门仍失败，不能事后改预算；
23. Phase 7B5l 已关闭守恒、闭合、无自由拟合带宽的局域多分辨率组件门；
24. Phase 7B5m 已只用训练截面冻结 4814 叶网格；独立留出集在 maximum width change、
   $n=8$ 以 $1.003468\times10^{-3}$ 严格失败，未重排网格或扩大预算；
25. Phase 7B5n 因预注册的 $n=12$ 在一个病例中不存在而关闭；没有改点、删例或报告部分
   候选误差；
26. Phase 7B5o 已用六个全新病例的初始/收敛态完成严格验证；9632 master 联合门通过，
   4816 叶候选只在 He II 以 $1.000546\times10^{-3}$ 失败，因此生产表示仍未选择；
27. Phase 7B5p 已用 10 个新进程完成单单元资源审计；9632 的中位/最大峰值为
   $190.44/191.50\,\mathrm{MiB}$，增量内存与单步时间约翻倍，但全柱峰值仍未测；
28. Phase 7B5q 已用 20 个新进程完成完整固定点包络；29/43 次迭代均收敛，两种初值
   最终强度差约 $2\times10^{-10}$，9632 最大峰值为 $209.44\,\mathrm{MiB}$；
29. 用户已明确采用 9632 组预算；Phase 7B5r 的 16/24 方向、16/32 子单元和联合门均
   失败，24×32 参考峰值为 $1046.47\,\mathrm{MiB}$，下一步只能预注册更细单单元参考；
30. Phase 7B5s 已完成更细单单元参考；32/48 方向只差 $1.221\times10^{-3}$，但
   32/64 子单元仍差 $7.626\times10^{-3}$，48×64 峰值为
   $2876.00\,\mathrm{MiB}$。下一门应先检查空间输运离散与方向边界误差，不能直接盲目
   扩到全柱或放宽阈值；
31. Phase 7B5t 已用特征分区角求积和守恒单元特征积分关闭单单元门；正式配置为
   9632 组、32 方向、每物质单元 16 个辐射子单元。下一步进入全柱资源、特征方向和
   静态/周期准入，而不是继续加密已通过的单单元；
32. Phase 7B5u 已完成全柱准入：当前整体实现至少需要 $84.668\,\mathrm{GiB}$ 活跃数组，
   且 586 个相位有掠射特征反向。下一步实现保留 9632 全局网格的流式块和守恒
   turning-ray 处理，不运行会爆内存的整体任务；
33. Phase 7B5v 已验证 turning-ray 和流式固定点，但单次映射以
   $3.93775\times10^{-12}$ 严格失败 $10^{-12}$ 门；
34. Phase 7B5w 已用局域交叠积分关闭该舍入门；stream256 与整体最终强度哈希相同，峰值
   RSS 从 1251.75 MiB 降至 392.08 MiB，下一步只进入完整深度单块资源探针；
35. Phase 7B5x 已实测 4096 深度最坏块：峰值 2863.14 MiB、总时间 10.83 s，其中
   单次源映射 9.66 s。内存门通过，但完整柱固定点先进入性能剖析，不直接长跑；
36. Phase 7B5y 的大列批次候选变慢且已回退；7B5z 的精简中间源映射保持输出哈希不变，
   最坏块算子加速 1.574 倍；
37. Phase 7B6a 已用两进程完成全部 76 块的一次全频映射，墙钟 244.88 s、每进程峰值约
   2.9 GiB；最大变化仍为 0.282899，完整固定点尚未授权；
38. Phase 5B3b 已恢复 OL 完整二维非线性 Hamiltonian；其频率相对二维线性只改变
   最多 $2.13\times10^{-3}$，却与 published 频率至少仍差 $0.2167$，故二维非线性
   不是文献差异来源；
39. Phase 5B3c 已逐字检验主文/附录的二阶径向项符号差；附录路径在宽盘仍与 published
   频率差 $1.3767$，且 published 矢量内端切线与三维自由根不相容，仍不能恢复未公开代码；
40. Phase 5B3d 已检查期刊、Crossref、arXiv 源包、GitHub 和 Zenodo；没有公开求解器或
   原始数组；唯一一封作者请求已于 2026-08-30 发出，published 代码对照仍等待回复；
41. Phase 5B4 已通过高偏心方程内部门并给出候选周期，但候选外缘偏心率只剩内缘的
   $36\%$--$37\%$，与旧常偏心 atlas 不兼容。下一步优先取得原作者数值代码；若要采用
   方程自洽候选，必须显式批准新动力学基准并从 $e(a)$ 源端重跑，不得只把旧横轴改成 day，
   也不以 published 柱值硬编码替代；
42. 当前静力失配门继续暂缓 UVOT；只有动态大气替换 Phase 4 后的新连续谱通过，才以更新后的
   atlas 为输入加入有版本和有效日期的真实 UVOT 响应及观测采样；
43. 只有裸盘在上述层级明确失败后，才讨论满足质量、能量、动量、扩散和离化约束的最小
   再处理层；
44. Phase 7B7f 已把 7B7e 的参考系/源项失败定位为 block-Jacobi 旧 halo 的诊断时机：
   全局拼接态的体积 $L_{1}$ 和柱积分差为 $7.338\times10^{-6}$、
   $5.238\times10^{-5}$。7B7f-r 三条数组逐位复现，最大进程 RSS 为 2586 MiB，
   只授权下一有界耦合续算设计，不代表已得到动态 NLTE 周期解；
45. Phase 7B7g--7B7j 已验证第二固定时间层物质--辐射方向的守恒、资源和正式源项，
   但固定点残差仍远高于 $10^{-3}$。7B7k 的恒定收缩成本外推为 70/4601 个循环，
   不是收敛定理，但已足以否决继续相同 $5\%$ 信赖域的朴素 Picard；下一阶段先做受保护
   非线性加速，不直接进入全轨道、Phase 4 或 UVOT。
46. Phase 7B8a--7B8c 已完成受保护逐单元割线、全频辐射复算和正式真残差门。全局平均
   收缩因子为 $0.5244$，但上一最难单元为 $1.0305$，严格失败 $0.99$ 门；因此该加速
   不能继续，且不能据平均改善宣称得到耦合新物质态。
47. Phase 7B8d--7B8f 的反馈感知回溯使用两个完整全频端点，预测选择 $0.75$ 步长；真实
   质量加权收缩为 $0.3449$，但原最难单元和最大单元为 $1.0475/1.0857$。端点仿射模型
   对刚性表层失效，故停止步长试探，只把块 Jacobian 或 Jacobian-free 隐式耦合保留为
   后续开放工作。
48. Phase 7B9d--7B9f 已纠正内层准入量，完成固定物质基准辐射科学泛函收敛、最后两态
   正式 H/He 反馈和可恢复基准物质残差；基准残差 $L_{2}=15.5889$，外层耦合未收敛。
49. Phase 7B9g 已证明冻结 $10^{-7}$ 有限差分步下的预期信号被约 $293.48$ 倍内层剩余
   变化淹没，故严格全频 $Jv$ 被拒绝且没有运行；只授权一次 $0.125$ 有限真残差试探。
50. Phase 7B9i--7B9j 的候选物质态通过信赖域，但前三次辐射映射只以
   $0.913614/0.920446$ 收缩。冻结第 12 轮预算不可能通过；当前 $\omega=1$ 续算停止，
   候选正式反馈和真残差仍未评价。下一门是预注册内层辐射加速，而非 Phase 4、UVOT、
   全轨道或真实线形成。
51. Phase 7B9k 的三次自然频率块 Aitken 映射保持有限、非负和资源门，且边界科学泛函
   持续改善；但第 6/5 次残差比 $0.868577$ 未通过 $0.80$，预计停止点第 38 次也超过
   第 28 次资源门。该算法被严格停止，候选物理真残差仍未评价；下一门改为代表频率块的
   块内隐式/多次散射求解成本--收缩审计。
52. Phase 7B9l 的六个代表块全部保持有限非负，八次更新成本约为一次的 $4.058$ 倍；但
   局域残差最大值/中位数仍为首步的 $0.85436/0.64625$，原最难块为 $0.64773$，严格
   失败预注册门。边界谱快收敛不能代替体内场收敛，因此全频八更新映射未获授权；下一门
   只允许真正的散射算子预条件控制。
53. Phase 7B9m 删除历史权重上界并只保留精确逐块非负边界；四个大权重候选确实仍为
   非负态，但 H I 两侧和 He I 块的新原算子残差放大 $14.3$、$16.6$ 和 $36.0$ 倍，
   中位数为 $7.8478$。因此所有标量外推分支关闭；下一步必须进入多模 ALI/块 Krylov，
   候选物理真残差仍未评价。
54. Phase 7B9n 的 3/5/7 维未正则化多模子空间通过物理域和资源门，对光学、H I 与软 X
   有效，却把 He I 新原算子残差放大到 $1.6147$；中位数 $0.3819$ 和仿射保真门也失败。
   因此未经物理预条件的 Krylov 历史未获全频授权，下一门是带解析控制的散射 Lambda
   预条件器。
55. Phase 7B9cu--7B9cw 已用受保护 Anderson(1) 和两次新的 9632 组完整映射关闭冻结物质
   候选的辐射内层门；两个连续残差为 $6.00598\times10^{-5}$ 和
   $5.96185\times10^{-5}$。Phase 7B9cy--7B9db 又关闭反馈依赖迁移与单块瞬态复现。
   最终 7B9dd 的正式 H/He 反馈稳定量全部低于 $10^{-3}$，但 $0.125$ 物质响应在两个端点
   上都使气体热能失去正值，故该有限步被拒绝且没有写出伪造残差。这不证明所有静态解
   不存在；下一门是预注册的有界小步长线搜索，Phase 4、UVOT、动态 NLTE 和真实线形成
   仍未授权。
56. Phase 7B9de 已预注册并构造同一方向的第一次二分候选 $0.0625$；最大温度、物质比能
   和布居变化为 $0.216307$、$0.0631827$ 和 $1.02511\times10^{-6}$，全部廉价物质门
   通过。He simplex 只保留两次浮点加法的 $4\epsilon_{\rm mach}$ 舍入界，没有重归一化。
   新全频辐射与反馈尚未计算；在新增两个完整工作态前必须先扩展存储，或完成具体历史
   检查点的哈希、依赖和用户批准清理。

不得用当前形式 Wien 尾生成 XRT 计数，也不得把 7B4g 固定密度双真空有限柱、7B4h 灰扩散
压力根、7B4i 局域 Planck 动态柱、7B4j 自适应解、7B4k 双网格解、7B4l 未收敛的固定
子单元解、7B4m 的 64 相位变量网格解、7B4n 的 64×1024 解、7B4o 尚保留局域
Planck--Rosseland 闭合的 64×2048 解，或 7B4p 未通过频率/深度门且没有辐射储能的冻结形式解
当成 Phase 4 替换表。7B4q 的阈值求积与分离辐射子网格虽通过冻结形式数值门，7B4r 也已
关闭 N128 有限时间门，但二者仍缺少辐射储能，不能作为 Phase 4 替换表。7B4s 虽显式
演化了双频辐射储能，仍缺速度项、全频/角度/辐射深度收敛和物质反馈，同样不能作为
Phase 4 替换表。7B4t 虽通过 Lorentz 与频率组组件控制，完整混合系源项尚未进入 ALE
联立残差，不能作为 Phase 4 替换表。7B4u 虽已选择通过静态 H/He 多群门的 1205 组，
7B4v 也已完成混合系 ALE 联立并关闭算子门，但 1205 组真实动态原子率门失败，且尚无
生产频率表示、全轨道收敛或物质反馈，同样不能作为 Phase 4 替换表。7B4w 的阈值局域
P0 虽在 18105 组通过三状态频率门，却失败预声明效率门；它同样不是 Phase 4 替换表。
7B4x/7B4y 的两种 P1 候选也都在最大宽度变化状态失败 $10^{-3}$ 精度门。7B4z 的 P2
候选同样失败该状态并保留算子失败点；三者都未选生产表示，不能作为 Phase 4 替换表。

### 9.3 开始新阶段前的检查表

- 先运行 `uv run pytest -q`，不要假定历史测试数仍有效；
- 明确新量属于 `[L]`、`[A]`、`[V]` 或 `[O]`；
- 保持 ZO 源契约，不通过观察者参数回调源温度或光度；
- 为新闭合写出物理理由、适用域、失败条件和可观测后果；
- 添加解析极限和分层收敛测试；
- 重要结果同时写 CSV、JSON 和经过目视检查的图；
- 更新对应阶段页、[[eccentric_tde_observer/lecture/项目讲义/00_document_map|文档地图]]和本 README
  的当前检查点；
- Markdown 文件使用行内 `$...$` 与独立 `$$...$$`；项目聊天使用 GPT 客户端默认数学排版；
  关键代码继续使用简洁中文注释。

---

## 10. 证据标签

- `[L]`：可在论文或标准教材中核对的定义、方程或结论；
- `[A]`：为源到观察者映射新增的闭合、数值约定或演示参数；
- `[V]`：当前测试、CSV/JSON 报告或图件实际验证的结果；
- `[O]`：尚未解决，不能写成模型预言的问题。

同一句可以使用组合标签，例如 `[L/A]` 表示关系骨架来自文献，但接入当前偏心盘属于项目
新增。任何阶段的“完成”都只表示该阶段声明的边界已关闭，不表示动态 NLTE、完整 GR 或
自由再处理层已经解决。
