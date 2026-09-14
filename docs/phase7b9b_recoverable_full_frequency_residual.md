# Phase 7B9b：可恢复全频残差接口与保真度门

上游：[[phase7b9a_newton_krylov_component|Phase 7B9a Newton--Krylov 组件门]]

## 必须先区分的两种量

对给定物质态 $\boldsymbol{u}$，一次辐射映射得到的 $J^{(1)}$ 仍依赖初始辐射场，最多定义
方向性诊断：

$$
\boldsymbol{R}^{(1)}_{\rm diag}(\boldsymbol{u})
=
{\rm encode}\!\left[
\mathcal{P}(\boldsymbol{u};J^{(1)})
\right]-\boldsymbol{u}.
$$

只有先在固定物质态上满足辐射内残差门，得到 $J^{\ast}(\boldsymbol{u})$，才能定义消去
辐射后的 Newton 物质残差：

$$
\boldsymbol{R}_{\rm N}(\boldsymbol{u})
=
{\rm encode}\!\left[
\mathcal{P}(\boldsymbol{u};J^{\ast}(\boldsymbol{u}))
\right]-\boldsymbol{u}.
$$

7B9b 把二者分别冻结为 `one_map_diagnostic` 和 `inner_converged_radiation`。即使单次映射
偶然给出很小的物质残差，其文件也不能被 Newton 求解器加载。`[A/V]`

## 文件级状态机

正式阶段只能沿下列顺序推进：

$$
{\rm planned}
\rightarrow
{\rm radiation\_{\rm running}}
\rightarrow
{\rm radiation\_{\rm complete}}
\rightarrow
{\rm feedback\_{\rm complete}}
\rightarrow
\begin{cases}
{\rm diagnostic\_{\rm complete}},\\
{\rm complete}.
\end{cases}
$$

物理域或数值失败是独立终态。输入协议、编码态、解码物质态、物理旧时间层和初始辐射
检查点均带 SHA-256；请求本身也有规范化哈希，运行中不能改变。`[V]`

每个频率块记录原始 `float64` 字节切片哈希。恢复时重新检查已经完成的切片；只有全部块
连续覆盖完整频率网格、全检查点尺寸正确且整体哈希冻结后，才允许正式反馈读取。预分配但
只写了一部分的 `.dat` 文件绝不是物理辐射态。`[V]`

## Newton 准入门

一个文件只有同时满足以下条件才可由 `load_newton_residual()` 返回：

1. 请求保真度为 `inner_converged_radiation`；
2. 全部频率块完成且未被修改；
3. 辐射内迭代明确收敛，残差不超过冻结阈值；
4. 辐射科学泛函门通过；
5. 正式源项一致性与守恒门通过；
6. 编码残差长度为冻结未知量数，且所有分量有限。

接口没有 `nan_to_num`、数值裁剪、温度或布居 floor，也没有失败点删除。小于电离能、无法
留下正热能的候选以物理域失败终态保存。`[V]`

## 已完成测试

![Phase 7B9b recoverable residual interface](../outputs/phase7b9b_recoverable_residual_interface.png)

图 (a) 给出只允许单向推进的可恢复状态机，并强调部分块不是物理反馈态；图 (b) 把保真度
固定在请求中，不能根据结果好看与否事后升级；图 (c) 的六项独立控制全部通过；图 (d)
显示单次方向性残差下界约 $0.19\,\mathrm{h}$，若照 7B9a 的 30 次 $Jv$ 已至少为
$5.69\,\mathrm{h}$，且尚未包含辐射内迭代。`[V/O]`

7B9b 的组件测试覆盖：

- 部分检查点可恢复，但不能交给反馈；
- 已登记频率块发生字节变化时恢复失败；
- 单次映射残差只能以诊断终态保存；
- 内收敛辐射、正式反馈和有限残差全部通过后可恢复加载；
- 辐射残差超门、源项门失败和非有限残差均被拒绝；
- 物理域失败保持为不可逆终态；
- 请求清单被修改时哈希校验失败。`[V]`

正式生产布局也已只读核对：$9632$ 频率组、$32$ 方向、$4096$ 深度和 $76$ 个频率块对应
$10{,}099{,}884{,}032$ 字节原始 `float64` 检查点，与 Phase 7B8e 现有文件严格一致。
接口控制墙钟为 $0.029\,\mathrm{s}$。`[V]`

## 当前边界与下一门

7B9b 完成的是昂贵残差的生产级账本和恢复语义，不是一次新的 $9632\times32\times4096$
内收敛计算。按 7B9a 的 $682.70\,\mathrm{s}$ 单次方向性成本，未经预条件的 512 维 GMRES
不能直接准入。下一门应先冻结块预条件或低维非局域方向基；它只能加速完整残差，不能替代
完整残差。通过成本门后，才运行首个正式全频 $Jv$。`[V/O]`
