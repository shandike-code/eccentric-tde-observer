# Phase 3A：低温 H/He LTE 非灰连续谱失效门

## 目标与定义

本阶段先不生成新的局域谱，而回答更基础的问题：给定 Zanazzi--Ogilvie（ZO）的
$\Sigma(a,E)$、$H(a,E)$ 与 $T_{\rm eff}(a,E)$，从光球到中面的柱在频率 $\nu$ 上是否有足够的
真实吸收把辐射热化。

- **LTE**（局域热力学平衡）：粒子布居只由局域密度和温度决定；
- **有效光深**：
  $\tau_{\rm eff} = \int \rho\,\sqrt(3\,\kappa_{\rm abs}\,(\kappa_{\rm abs}+\kappa_{\rm es}))\,dz$；
- **热化判据**：本阶段采用 $\tau_{\rm eff} \ge 1$；
- **非灰**：$\kappa_{\rm abs}$ 随频率变化，并显式保留 H I、He I、He II 吸收边。

## 方程与归属

1. `[L]` Rybicki--Lightman 自由—自由吸收式，保留受激辐射修正；
2. `[L/A]` H/He Saha 方程与电荷中性：

   $n_{p}\,n_{e}/n_{\rm HI} = S_{\rm H}(T)$，
   $n_{\rm HeII}\,n_{e}/n_{\rm HeI} = S_{\rm HeI}(T)$，
   $n_{\rm HeIII}\,n_{e}/n_{\rm HeII} = S_{\rm HeII}(T)$。

   配分函数被约化为基态统计权重 2，是新增近似；
3. `[L/A]` H I 与 He II 使用氢样截面
   $\sigma_{\rm bf}=\sigma_{0}\,(\nu_{0}/\nu)^3$（$\nu\ge\nu_{0}$）；He I 不是氢样原子，默认关闭，
   只提供一个可开关的阈值截面敏感性计算；
4. `[A]` 垂向温度仍使用第二阶段的灰 Eddington $T(\tau_{\rm es})$。这只为不透明度提供受控
   温度剖面，不等于求解非灰辐射平衡；
5. `[V]` 电荷中性相对残差最大 $2.1e-16$；吸收边、真空端点和输入拒绝域有独立测试。

## 严格参考源结果

- $1e15 Hz$：全源面积达到 $\tau_{\rm eff}\ge1$；
- H I 边下方约 $3.285e15 Hz$：热化面积最低为 $0.5767$，面积中位光深 $1.279$；
- H I 边上方光深跃升，He II 边也产生强跃升；
- 形式 LTE 计算在 $0.3 keV$ 得到全域热化和很大光深，但这**不能**升级为 X-ray 预测。
  Roth et al. (2016) 指出 He II 吸收强烈依赖辐照离化态；LTE 很可能高估被强高能辐照气体
  中的束缚态布居；
- He I 近似开关不改变当前参考源的热化面积曲线，说明这里的主要跃升由 H I/He II 控制，
  不能据此断言真实 He I 不重要。

收敛审计：垂向 $65 \to 129$ 点的面积中位光深最大变化 $2.14e-5$；源网格
$17x128 \to 33x256$ 最大变化 $4.15\%$。后者高于最终 observer 谱的千分之一目标，因此
非灰光深曲线目前是**域审计**，不是精密大气表。

## 为什么仍未得到 NLTE 大气

- `[L]` Davis & Hubeny (2006) 的 annulus 表格需要 $\Sigma, T_{\rm eff}, Q$，并求解 NLTE、
  金属束缚—自由与 Compton 化；其论文表格从 $log T_{\rm eff}=5.0$ 起，而本参考源约为
  $8e3--3.9e4 K$，不能直接插值外推；
- `[O]` 偏心盘所需的有效垂向重力 $Q(a,E)$ 尚未从 ZO 呼吸解完整映射到低温 annulus 表；
- `[O]` 外部高能辐照、金属线空白、复合发射和完整统计平衡尚未求解。

因此 Phase 3A 的可用结论是“哪些频段对布居闭合敏感”，而不是新的 $I_{\nu}$。

## 代码与产物

- 核心：`src/eccentric_tde_observer/non_gray.py`
- 测试：`tests/test_non_gray.py`
- 运行：`uv run python scripts/phase3_complete.py --output-dir outputs`
- 数据：`outputs/phase3_non_gray_thermalization.csv`、
  `outputs/phase3_non_gray_convergence.csv`

