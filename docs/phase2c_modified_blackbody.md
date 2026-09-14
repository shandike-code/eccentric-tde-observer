# 阶段 2C：热化锚定的 modified-blackbody 观察者谱

本阶段把 2B 得到的热化深度闭合接入自遮挡几何和 2A 弱场频移，生成实际
$F_{\nu}(i,\Phi)$。它是裸盘连续谱的条件模型，不是任意 color factor 拟合。

## 1. [A] 局域能量守恒谱

每个表面元采用

$$
I_{\nu,\rm em}=f_{\rm col}^{-4}
B_{\nu}(f_{\rm col}T_{\rm eff}),
$$

其中 $f_{\rm col}(a,E)$ 由 2B 的局域峰频 $\tau_{\rm eff}=1$ 热化层决定。$f^-4$ 使

$$
\pi\int_{0}^\infty I_{\nu,\rm em}d\nu
=\sigma T_{\rm eff}^4
$$

逐表面元严格成立，因此没有通过事后重标定制造光度。

结合弱场频移不变量：

$$
I_{\nu,\rm obs}=g^3I_{\nu/g,\rm em}
=f_{\rm col}^{-4}B_{\nu}(gf_{\rm col}T_{\rm eff}).
$$

几何表面仍是电子散射 $\tau_{\rm es}=2/3$ 光球；热化层更深，只决定局域谱形。

## 2. [V] 实际观测光谱

计算距离 100 Mpc、$i=0,30,60,75^\circ$ 和完整 30 度步长进动相位。实际 $F_{\nu}$
保存在 CSV；图中的 $\nu F_{\nu}$ 没有任意归一化。

在完全热化的保守频段 $5e14--1e15 Hz$，相对局域黑体闭合：

- $5e14 Hz$ 的 $F_{\nu}$ 比为 $0.388--0.420$；
- $1e15 Hz$ 的 $F_{\nu}$ 比为 $0.561--0.681$。

这是能量从低频移向更高频的结果，不是总光度损失。在部分有效薄区：

- $2e15 Hz$ 比为 $0.849--1.131$；
- $5e15 Hz$ 比为 $3.07--3.73$；
- $1e16 Hz$ 的形式比为 $32.9--48.3$。

后两项已经明显依赖当前 closure 的无效外推，不能当作稳健 UV/X-ray 预言。

## 3. [V] 可证伪的相位预言

$i=75^\circ$ 的相位最大/最小通量比为：

| 频率 | 最大/最小 | 物理等级 |
|---:|---:|---|
| $5e14 Hz$ | $2.291$ | 全盘热化，条件预言 |
| $1e15 Hz$ | $2.039$ | 全盘热化，条件预言 |
| $2e15 Hz$ | $1.502$ | 96.7% 面积热化，closure-sensitive |
| $5e15 Hz$ | $1.411$ | 46.7% 面积热化，不稳健 |
| $1e16 Hz$ | $1.908$ | 18.1% 面积热化，不稳健 |

因此第二阶段最可信的可证伪量是 optical 相位色变化，而不是 X-ray 开关。

## 4. [A-fit/V] 黑体诊断

为避免在失效频域拟合，把观察者黑体诊断限制到 $5e14--1e15 Hz$：

$$
1.802\times10^4\le T_{\rm bb}\le2.032\times10^4\ {\rm K},
$$

$$
7.51\times10^{13}\le R_{\rm bb}\le2.04\times10^{14}\ {\rm cm}.
$$

拟合 RMS 仅 $0.0013--0.0018 dex$，但这个好拟合只说明窄 optical 频段接近单黑体，
不证明整个 SED 是单温。

热化阈值从 $1$ 改为 $2/3$ 时，$5e14 Hz$ 通量变化约 $16.7--17.7\%$，$1e15 Hz$
变化约 $8.9--11.3\%$。这是当前最小大气闭合的系统误差，应与数值误差分开。

## 5. [V/O] X-ray 结论

modified-blackbody 数学尾部给出的形式值为

$$
1.4\times10^{-22}\lesssim{L_{\rm X}\over L_{\rm opt}}
\lesssim1.3\times10^{-20}.
$$

但 2B 已证明在 0.3 keV 处所有表面元 $\tau_{\rm eff}<1$，所以这些值明确标为
`formal extrapolation`，不是观察预言。它们只能说明：即使把谱峰硬化外推到 X-ray，
这个严格域低 $V$ 裸盘依然极弱；真实 X-ray 需要 NLTE/Compton 大气或另一物理源，
不能由当前代码决定。

## 6. [V] 验证

- 局域 diluted blackbody 的 bolometric flux 回到 $\sigma\,T_{\rm eff}^4$；
- $f_{\rm col}=1$ 逐位回到阶段 2A 黑体积分；
- 大气垂向 $257 \to 513$ 的探针谱变化小于 $9.36e-5$；
- 射线细分 $2 \to 4$ 变化为 0；
- 源网格 $(65,1024) \to (129,2048)$ 最大变化 $2.32e-4$；
- $e=0$ 的方位残差最大 $1.81e-4$；
- 无热化层、$f_{\rm col}<1$、非有限状态全部报错，没有裁剪或 `nan_to_num`。

## 7. 产物

- `outputs/phase2c_modified_blackbody_spectra.png`
- `outputs/phase2c_modified_blackbody_spectra.csv`
- `outputs/phase2c_orientation_diagnostics.csv`
- `outputs/phase2c_numerical_convergence.csv`
- `outputs/phase2c_modified_blackbody_report.json`

运行：

```bash
uv run python scripts/phase2c_modified_blackbody_observer.py
```
