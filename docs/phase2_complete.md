# 第二阶段完成报告：裸偏心盘的频移、热化与条件观测谱

## 1. 完成边界

第二阶段按以下四部分完成：

| 子阶段 | 内容 | 状态 |
|---|---|---|
| 2A | Kepler/ZO 速度、SR Doppler、Schwarzschild 弱场红移 | 完成 |
| 2B | 自由--自由吸收、电子散射、有效光深和热化层审计 | 完成 |
| 2C | 局域能量守恒 modified-blackbody 与多方向实际 $F_{\nu}$ | 完成 |
| 2D | 适用域遮罩、综合图、可证伪量和未解问题 | 完成 |

这里的“完成”严格限定为裸盘、连续谱、弱场观察者映射。它不表示 NLTE 大气、全 GR
或盘风已经解决。

## 2. 四类结论

### [L] 文献和 ZO 已确定

- ZO 的 $e,\varpi,\Sigma,j,H,T_{\rm eff}$ 与常偏心严格域参考解；
- Lynch--Ogilvie 的 $n=3$ 垂向密度形状和 ZO 齐次呼吸速度；
- $I_{\nu}/\nu^3$ 不变量、自由--自由吸收和电子散射的标准转移关系。

### [A] 第二阶段新增闭合

- Newtonian 椭圆轨道与 Schwarzschild lapse 的弱场混合；
- 直线正交射线，没有移动表面相对论面积修正；
- 完全电离 H/He、$g_{\rm ff}=1$、自由--自由连续吸收；
- 灰 Eddington 深度温度和 $\tau_{\rm eff}=1$ 热化约定；
- $f_{\rm col}^-4 B_{\nu}(f_{\rm col} T_{\rm eff})$ 的各向同性局域谱。

### [V] 当前代码支持

- $g=0.959--1.040$，光学频移是百分数效应，Wien 尾效应被指数放大；
- 局域谱峰全部可以热化，$f_{\rm col}=1.540--1.656$；
- 全源面可靠热化到约 $1e15 Hz$，之后逐步有效薄；
- $i=75^\circ$ 在 $5e14,1e15 Hz$ 的进动相位调制为 $2.291,2.039$；
- 保守 optical 拟合给出 $T_{\rm bb}=1.80--2.03e4 K$、
  $R_{\rm bb}=0.75--2.04e14 cm$；
- 严格域参考点在 $i\le75^\circ$ 仍没有自遮挡事件；
- 所有几何、源网格和大气垂向收敛误差均远小于当前闭合系统误差。

### [O] 不能假装已经解决

- 0.3 keV 处整个盘 $\tau_{\rm eff}<1$，所以当前模型没有物理有效的 X-ray 谱；
- 低温盘的 H/He 电离、bound-free 边、金属 opacity 和 NLTE 未解；
- Compton 能量交换、limb darkening、偏振和非灰辐射平衡未解；
- ZO 常偏心源没有绝对进动周期；
- 全 GR ray tracing、黑洞自旋和光行时未解；
- 典型 $V\ge0.1$ 高偏心源仍未通过局域垂向适用域筛选。

## 3. 对核心科学问题的阶段性回答

在不引入盘风的条件下，严格局域域的 ZO 型裸偏心盘可以产生：

- 明确、颜色相关且随进动相位变化的 optical $F_{\nu}$；
- 倾角和近心点方位相关的 $T_{\rm bb},R_{\rm bb}$；
- 可由多波段相位光变证伪的约 2 倍 optical 调制。

它目前不能提供：

- 物理自洽的 X-ray 强度或遮挡变化；
- 用裸盘同时解释 optical/UV 与 X-ray 相对强度的正面结论。

这不是“需要调一个盘风参数”的结论。更准确的结论是：裸盘 optical 映射已有条件
预言，而 X-ray 在局域大气闭合层面已经越出适用域。只有第三阶段先补足大气物理后，
才能判断是否确实需要最小再处理层。

## 4. 验证清单

- $e\to0$ 回到轴对称相位不变结果；
- $g\to1$ 回到无频移表面积分；
- $f_{\rm col}\to1$ 回到局域黑体；
- $I_{\nu}/\nu^3$ 和 bolometric $g^4$ 标度通过；
- diluted blackbody 严格保持局域 $\sigma\,T_{\rm eff}^4$；
- 纯散射/吸收不足导致没有热化层时直接拒绝；
- 网格、射线和垂向积分均收敛；
- 没有 `nan_to_num` 或无物理依据的裁剪。

关键代码的中文注释规则见 [代码规范](code_conventions.md)。

## 5. 第三阶段顺序

1. 建立或接入覆盖本项目低 $T_{\rm eff}$、$\Sigma$、偏心有效重力的非灰/NLTE annulus 表；
2. 加入角度分辨局域强度、limb darkening 和偏振；
3. 再实现 Cunningham 思路的 GR 像平面 transfer function；
4. 只有在上述裸盘模型仍定量失败后，才加入质量、能量、动量和光深受约束的最小
   再处理层。

## 6. 综合产物

- `outputs/phase2_complete_summary.png`
- `outputs/phase2_complete_report.json`
- [阶段 2A](phase2a_weakfield_frequency_shift.md)
- [阶段 2B](phase2b_atmosphere_audit.md)
- [阶段 2C](phase2c_modified_blackbody.md)

综合图运行：

```bash
uv run python scripts/phase2d_complete_summary.py
```
