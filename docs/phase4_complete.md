# 第四阶段与项目建模阶段完成报告

## 1. 最终阶段解决了什么

Phase 4 没有把“最终阶段”误写成全 GRRMHD 或伪 NLTE。它完成了两个剩余的可封闭问题：

1. **动态大气接口**：从 ZO 呼吸解严格构造 $T_{\rm eff},m_{0},Q_{\rm pressure}$，给未来角分辨
   NLTE 表一个禁外推接口，同时用时间尺度判据指出静态表在哪些轨道相位失效；
2. **观测图谱**：把有效裸盘模型整理成倾角、进动相位、频率和无量纲时间分辨的实际
   $F_{\nu}$、Stokes、AB 诊断量、$T_{\rm bb},R_{\rm bb}$ 与谐波表。

这使源到观察者软件链本身完成，但不会把缺失的微观物理改名为“已完成”。

## 2. 四类结论

### `[L]` 文献确定

- ZO/Ogilvie--Lynch 的动态偏心轨道、呼吸解和 $\Sigma,H,T_{\rm eff}$；
- Davis--Hubeny 的静态环带输入 $T_{\rm eff},m_{0}=\Sigma/2,Q$ 及其已发表表格边界；
- $I_{\nu}/\nu^3$、Stokes、AB 光子计数平均与辐射转移基础关系。

### `[A]` 本项目新增

- 把 $Q_{\rm pressure}=Q_{\rm tidal}+\ddot{H}/H$ 作为瞬时静态表的共动重力坐标；
- 用 $|\mathrm d\ln H/\mathrm dt|/\sqrt{Q_{\rm pressure}}$ 作为准静态失效指标；
- 两个理想 optical/near-UV top-hat 仅用于展示观测映射；
- 时间输出以 $t/P_{\rm prec}$ 表示，不指定绝对周期。

### `[V]` 代码支持

- 现有 Davis--Hubeny 2006 表覆盖当前源面积为零；
- 仅 $12.9\%$ 面积满足严格的准静态比例 $<0.1$；
- optical/UV 倾角—相位图谱、条件偏振、AB 量、$T_{\rm bb},R_{\rm bb}$ 和谐波均已输出；
- 图谱源网格误差 $<9.1e-4$，相位谐波误差 $<6.3e-5$；
- $i=80^\circ$ 并非全相位有效，拒绝而不裁剪。

### `[O]` 仍未解决

- 覆盖低 $T_{\rm eff}$、极低 $Q$、动态呼吸和外部辐照的时间依赖 NLTE 大气；
- 谱形成层的 Compton 能量交换、金属原子和真实角偏振；
- 绝对 $\varpi(t)$、压力与 GR 共同决定的全局进动历史；
- 高倾角多值光球、曲线射线自遮挡和 Kerr 多像；
- 物理有效的 X-ray 种子谱，因此也没有可信 $L_{\rm X}/L_{\rm opt}$；
- 任何实际再处理层仍必须满足 Phase 3D 的守恒约束。

## 3. 最终科学判断

当前项目已经能够发布为：

> “以 ZO 解析偏心盘为源，在明确的 LTE/modified-blackbody、角分布和弱场直接像条件下，
>  对 optical/UV $F_{\nu}(i,\phi_{\rm obs}-\varpi)$、颜色、黑体量、偏振和进动相位调制作可证伪预测。”

当前项目不能发布为：

> “裸偏心盘已经自洽解释了 TDE 的 optical/UV 与 X-ray 相对强度。”

决定性原因不只是缺一张 opacity 表，而是大部分轨道相位并不满足静态 annulus 的响应时间
条件。下一物理里程碑是动态、受辐照的低温 NLTE 柱，或先用观测证明静态有效相位已经足以
解释目标现象。

## 4. 产物与运行

- 总图：`outputs/phase4_complete_summary.png`
- 总报告：`outputs/phase4_complete_report.json`
- annulus 坐标：`outputs/phase4_annulus_coordinates.npz`
- 观察者谱图谱：`outputs/phase4_atlas_spectra.csv`
- 无量纲光变：`outputs/phase4_dimensionless_lightcurve.csv`

```bash
uv run pytest -q
uv run python scripts/phase4_final_atlas.py --output-dir outputs
```
