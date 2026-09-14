# Phase 4B：可观测倾角—进动相位图谱

## 1. 图谱定义

本图谱保留 Phase 3 已验证的局域 modified-blackbody、临边昏暗、Stokes 偏振和弱场直接像
传递。它不声称补上 Phase 4A 判定缺失的动态 NLTE 大气。

采样范围：

- 倾角：$0,15,30,45,60,70,75^\circ$；
- 相对相位：$\phi_{\rm obs}-\varpi = 0--345^\circ$，步长 $15^\circ$，不重复 $360^\circ$；
- 频率：$1e14--1e16 Hz$；
- 距离：$100 Mpc$；
- 图谱源网格：$33x512$，关键方位用 $65x1024$ 复算。

每个格点输出实际 $F_{\nu}$、直线 Stokes $I,Q,U$、偏振度、保守 $T_{\rm bb},R_{\rm bb}$ 和理想带通
AB 量。

## 2. 理想带通的边界

为展示如何对接观测，定义了两个单位响应的对数 top-hat：

- diagnostic optical：$4e14--8e14 Hz$；
- diagnostic near-UV：$8e14--1.5e15 Hz$。

采用光子计数 AB 平均：

$<f_{\nu}> = \int f_{\nu} R \mathrm d\nu/\nu / \int R \mathrm d\nu/\nu$。

这些不是 Swift/LSST/ZTF 的真实响应曲线，不能拿理想 AB 数字直接和目录测光拟合。接口已
支持替换为真实 response curve。

## 3. 图谱结果

- optical AB magnitude（100 Mpc）范围 $18.54--21.26$；
- ideal `NUV-optical` 颜色范围 $-0.568-- -0.382 mag$；
- 保守 $T_{\rm bb}=1.783e4--2.082e4 K$；
- 保守 $R_{\rm bb}=5.85e13--2.27e14 cm$；
- face-on 相位谐波保持在约 $1e-16$ 数值噪声；
- 调制随倾角增强，$i=75^\circ$ 的主要 optical/UV 结果与 Phase 3 高分辨率谱一致；
- 所有有效图谱方位的直线自遮挡比仍为 1。

高倾角不是无限可延伸的：$i=80^\circ$ 在相位 $90^\circ$ 首次出现活动顶点 $\mu<0$，表明
单值上光球与顶点平行平面角闭合失效。代码没有裁剪 $\mu$，最终图谱只保留所有相位都通过
的 $i\le75^\circ$。

## 4. 从相位到时间

ZO 理论可把 $\varpi(t)$ 作为输入，但当前常偏心严格参考点没有在代码中解出绝对进动周期。
因此输出光变使用无量纲时间 $t/P_{\rm prec}$：

$relative phase(t) = \phi_{\rm obs}-\varpi(t)$。

若外部理论或数据给出任意 $\varpi(t)$，周期相位图谱可直接插值；只有显式给定均匀
$P_{\rm prec}$ 时才使用线性相位。代码不从一条光变自行假设周期。

## 5. 验证

- $33x512 \to 65x1024$ 最大变化 $9.05e-4$；
- 相位点 $12 \to 24$ 的一阶谐波最大变化 $6.27e-5$；
- $e=0$ 圆盘的两个方位最大差 $1.99e-4$，低于千分之一目标；
- 常数 $f_{\nu}$ 在任意带通回到 AB 零点；
- 周期插值在节点和跨越 $2\pi$ 时通过测试。

主要产物：

- `outputs/phase4_atlas_spectra.csv`
- `outputs/phase4_atlas_diagnostics.csv`
- `outputs/phase4_atlas_harmonics.csv`
- `outputs/phase4_dimensionless_lightcurve.csv`
- `outputs/phase4_atlas_convergence.csv`

