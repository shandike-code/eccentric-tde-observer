# 项目阶段性收尾：2026-09-02

入口：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/00_document_map|文档地图]]

## 1. 收尾判定

本轮工作在一个完整 76 块辐射映射结束后停止，没有 active partial iteration，也没有后台
Phase 7 进程。`[V]` 停止原因不是宣称达到原定 $10^{-4}$ 全态残差，而是用户决定不再为
慢尾投入重型计算，并要求客观保留未收敛状态。`[A-user-stop]`

截至该停止点：

- `[V]` corrected ZO 2022 Erratum 面积已经成为正式源面积；旧测度只作为 pre-Erratum
  历史对照；
- `[V]` 连续谱的几何、投影、自遮挡、弱场频移、观察者系 Jacobian 和能量账本已分层验证；
- `[V/O]` Phase 6 已完成条件性的运动学线核，不是绝对 Halpha/Hbeta/He II 光谱；
- `[A/V]` 两条方程自洽候选源通过当前有效域收敛门，并有指纹绑定的相对进动时间钟；
- `[V/O]` Phase 7 在单柱、单相位、固定物质态上建立了高分辨 H/He 基态连续转移，但
  终点没有通过严格全态残差门，也没有产生正式 feedback pair；
- `[O]` modified-blackbody 尚未被生产级局域大气表替换，后续分支保持 `not_ready`。

## 2. 三张关键收尾图

### 2.1 候选源的相对时间钟

![Phase 5B8 candidate-source apsidal time mapping](../outputs/phase5b8_candidate_source_time_mapping.png)

左面板给出候选相位到相对时间的线性映射；右面板给出十年相位漂移。
$e_{\rm in}=0.60$ 与 $0.65$ 的候选周期为 $40.81395$ 年与 $42.92803$ 年。该结果只对
完全匹配的 $(a,e,q)$ 指纹有效；没有绝对 $t_{0}$、$\Phi_{0}$ 或 MJD，旧常偏心 atlas
不能使用该时间轴。详见
[[eccentric_tde_observer/docs/phase5b8_candidate_source_time_mapping|Phase 5B8]]。`[A/V/O]`

### 2.2 固定物质辐射慢模的位置

![Phase 7B9dt two-state slow-mode locator](../outputs/phase7b9dt_two_state_slow_mode_locator.png)

左面板区分逐块最大绝对变化和状态尺度；右面板显示局域块残差。控制正式全局残差分子的点
位于约 $9.10\,\mathrm{eV}$，全局尺度点则位于约 $13.64\,\mathrm{eV}$。这只定位慢模
自由度，不证明某一原子过程是原因，也不授权删除高残差块。详见
[[eccentric_tde_observer/docs/phase7b9dt_two_state_slow_mode_locator|Phase 7B9dt]]。`[V/O]`

### 2.3 未严格收敛的干净边界收尾

![Phase 7B9dv clean-boundary closeout](../outputs/phase7b9dv_closeout.png)

上面板显示 49 个唯一状态的原算子残差从 $8.22621\times10^{-4}$ 降到
$2.10413\times10^{-4}$，仍高于目标线；中面板显示收缩率进入约 $0.992$ 的低收益
慢尾；下面板显示边界谱和 bolometric 变化已降至 $4.4010\times10^{-6}$ 与
$2.8378\times10^{-6}$。因此应同时保留“边界量稳定”和“内部全态未严格收敛”两项
事实。详见 [[eccentric_tde_observer/docs/phase7b9dv_closeout|Phase 7B9dv]]。`[V/O]`

## 3. 对当前模型的客观评价

当前项目最成熟的部分是 corrected ZO 源到观察者的**条件性前向映射**。在声明局域发射闭合
之后，它可以稳定回答几何、倾角、相位、频移、自遮挡和运动学线核怎样影响观测量。它不是
一个已经闭合所有微物理的真实 TDE 光谱生成器。

主要优点：

1. `[V]` Erratum 面积、能量定义、$F_{\nu}$、$F_{\lambda}$ 与等效光度严格区分；
2. `[V]` 失败点和数值门完整保留，没有使用 `nan_to_num`、任意 clip、floor、删点或事后
   重归一化掩盖问题；
3. `[V]` 圆盘/偏心盘、解析圆环、频率 Jacobian、$g^{4}$ 线能流和收敛均有测试；
4. `[A/V]` 候选源、旧常偏心控制和 published benchmark 的身份分开，不把方程自洽候选
   冒充已发表复现；
5. `[V/O]` Phase 7 把 modified-blackbody 的替代问题推进到具体数值瓶颈，而没有用一个
   未收敛局域谱提前替换观察者结果。

主要弊端：

1. `[A/O]` 正式连续谱仍依赖 blackbody/modified-blackbody；它能守恒局域总能量，却不
   保证真实边缘、颜色修正、角分布或 Wien 尾；
2. `[O]` Phase 7 只覆盖一个代表 annulus、一个轨道相位和固定物质态，不能代表完整
   $(a,E)$ 源；
3. `[O]` 当前 H/He 模型只有基态连续过程，没有激发态、bound-bound NLTE、金属
   line blanketing、完整 Compton 重分布或收敛物质反馈；
4. `[V/O]` 全态残差为 $2.10\times10^{-4}$，正式连续两态收敛和 feedback pair 均缺失；
5. `[O]` 没有生产级 $I_{\nu}(a,E,\mu)$ 表，所以 Phase 4/5A 没有重跑，UVOT 计数率和
   事件级观测采样也没有实现；
6. `[O]` Phase 6 的双峰仅说明旋转几何允许这种线形。真实线还缺 NLTE 能级布居、线
   opacity、自吸收、光致电离、电子散射重分布和仪器线扩散函数；
7. `[O]` 候选时间钟只有相对历元，且 published Fig. 6/7 与印刷 Eq. (48) 的归一化问题
   仍未关闭。

## 4. 当前允许和禁止的结论

允许：corrected ZO 裸盘几何在受控局域发射假设下给出可证伪的连续谱方向效应和条件性
运动学线核；圆盘与偏心盘都可产生双峰，偏心性更应由红蓝不对称、质心、线翼及其相位关联
检验。`[V/O]`

禁止：把当前 modified-blackbody 称为已验证大气谱；把 Phase 7 单柱称为全盘动态 NLTE；
把归一化线核称为真实 Halpha 光度；把候选相对进动周期贴到旧 atlas 或具体 MJD；由一次
物质候选失败断言静态解不存在。`[O]`

后续只有在完整候选源定义域上得到收敛、角分辨、频率分辨的局域强度，并完成材料反馈与
网格收敛后，才应选择
[[eccentric_tde_observer/docs/phase7_post_convergence_branch_contract|Phase 7 后续分支]]。
在那之前，`not_ready` 是最准确的科学结论。

## 5. 验证与存储

- 收尾相关定向测试：$54$ passed；
- 最终完整测试：$1131$ passed；
- 当前检查点递归库存：$10048$ 个常规文件、$23$ 个完整辐射态；所有完整态均为 active
  或 referenced，未删除任何检查点；
- 7B9du manifest 的 `running` 表示仍可恢复，`active_iteration=null` 且系统中没有
  Phase 7B9du 后台进程。

检查点是否清理必须另做依赖与哈希审计并再次取得用户批准；本次收尾没有把“停止计算”等同于
“允许删除”。详见 [[eccentric_tde_observer/docs/phase7_checkpoint_inventory|检查点库存]]。
