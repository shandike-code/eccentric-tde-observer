# 22:55巡检：跨历史预测通过，启动全场实测与正性诊断

73523完成只读扫描，status=complete，未写候选、未运行新map，stderr为空。所有代数保护通过。

## 扫描的实际含义

`gamma=-0.19186292036058647`，对应候选为约0.8081370796份base与0.1918629204份old。系数L1为1，候选及预测映射负强度计数均0。

预测最大残差7.657069076118395e-5，原较好实测7.751071866695657e-5，改善约1.21%；全场未加权残差平方L2从0.00031982355降到0.00026160134。预测边界L1为7.90661515e-5，bolometric为1.90048782e-5。这个收益不大，不据此承诺反馈或物质方程显著改善。

两历史差经过一次原映射后的L2幅度比为0.9937578239，其算子改变量/输入差幅度为0.0067400191；这些只描述这一条方向，不是全空间压缩常数、迭代谱半径或物理解唯一性证明。

全局可行区间为[-3.0184248036,0]。未约束最优系数本来就位于区间内，**正性没有截断本轮选中的最优系数**。单独调查为何不允许正gamma，是为后续方向构造提供约束定位，不能解释成本轮最优值被正性卡住。

小包`cross-history-scan-73523-small.tar.gz`，19944866 bytes、580文件，SHA256 `419b183457d044e2cefd2e28dd93b1722a395634e36c9ad630c7eb2e0a856bc6`，学校家目录与Mac `outputs/review-20260919/`双端保全，Mac整包/逐文件核验。Git小证据为`handoff/evidence/20260919-cross-history-prediction.json`。

## 两项独立有界任务

1. **cpu_long 32CPU/128GiB、16worker、45min**：新增`operations/validate_cross_history_candidate.py/.sbatch`，从声明的XB、XO分块写`XB+gamma*(XB-XO)`，前后核四个原态SHA，显式携带同一trial并核native，执行一张原算子map。新目录记录candidate SHA/config/代码/资源，不修改旧run。除了实际残差与边界，还逐单元比较实际输出与`YB+gamma*(YB-YO)`，报告全场L2、最大误差和边界预测误差；预测误差L2须小于实际映射改变量L2的1%。该门只检查数值预测，本轮无正式反馈或物质接受预算，不能证明全空间线性或自洽大气。
2. **默认4CPU/16GiB、20min**：新增`operations/diagnose_cross_history_positivity.py/.sbatch`，只读统计base恰为0而old大于0的单元，分别检查候选输入和映射输出；给频块计数、最大阻碍强度、最大的8个单元的频率边界/角索引/辐射深度索引及subnormal计数。对任意正gamma，这些单元会给负值；但它们相对全局强度小也不能证明对加热无关。不得改零值或加floor，不能从一个零值反推其物理或数值成因。

所有新代码使用`NUMPY_MADVISE_HUGEPAGE=0`，原source/kernel及历史数据不变。Mac25项相关测试通过，含流式写入公式与顺序、短读不发布候选、负值/非法系数拒绝、全场预测完全一致、标量残差相同但全场不同必须被识别、正性阻碍计数与索引、原字节不变、既有同物质身份和扫描代数测试。

变更前Git备份`pre-cross-validation-885a1fd.bundle`。本轮主要检验跨历史组合的全场预测是否可靠，为后续更有效的方向设计提供证据；不把1.21%的预测改善称为已经解决慢模。完成后各自小包双端核验，再决定是否值得独立追加反馈或扩展子空间，不自动重复本轮。

代码`041c3c2`已同步学校/GitHub，Linux同组25测试通过。正式提交73581（`outputs/hpc/cross-history-map-validation-20260919`，cpu_long32CPU/128GiB/16worker）和73582（`outputs/hpc/cross-history-positivity-audit-20260919`，默认4CPU/16GiB）。提交初态均PD，独立运行无相互等待；各自预算按上文执行。旧run及原四态不变，小包排除dat、lock和可能较大的cross_candidate.partial。
