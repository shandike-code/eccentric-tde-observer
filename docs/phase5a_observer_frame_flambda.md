# Phase 5A：观察者系 F-lambda 光谱

## 1. 这一小阶段解决什么

第四阶段输出的是参考距离 100 Mpc 处、按观察者方向分辨的 $F_{\nu}$。Phase 5A 首先把它
变成带有红移、光度距离和前景消光的 $F_{\lambda}$；这不是把横轴从 Hz 改成 Å。

定义源静止系频率为 $\nu_{\rm em}$，观察频率为 $\nu_{\rm obs}=\nu_{\rm em}/(1+z)$，光度距离为 $D_{\rm L}$。
Hogg 的谱通量关系给出：[L]

$$
F_{\nu,\mathrm{obs}}(\nu_{\mathrm{obs}})=
(1+z)\left({D_{\mathrm{ref}}\over D_{\rm L}}\right)^2
F_{\nu,\mathrm{ref}}[(1+z)\nu_{\mathrm{obs}}] .
$$

$F_{\lambda}$ 按每 Å 定义时，[L/V]

$$
F_{\lambda,[\mathrm{\AA}^{-1}]}=
F_{\nu} {c\over\lambda_{\mathrm{cm}}^2}\,10^{-8},
\qquad
\lambda_{\mathrm{\AA}}F_{\lambda,[\mathrm{\AA}^{-1}]}=\nu F_{\nu} .
$$

## 2. 本次新增闭合

- `[L]` 平直 Lambda-CDM 光度距离采用 Hogg 的距离积分；默认演示参数为
  $H0=70 km s^-1 Mpc^-1$、$\Omega_{m}=0.3$。
- `[L/A]` 银河系消光使用 Fitzpatrick 1998 Appendix A：2700 Å 以下采用 FM UV 函数，
  以上采用论文表 3/4 的 IR/optical 锚点。论文给出三次样条构造；代码明确采用自然
  端点条件。这一端点条件是数值闭合，而不是 ZO 源模型的一部分。
- `[A]` 第一张图选 $z=0.05$、$E(B-V)=0.03$、$R_{\rm V}=3.1$，只为展示观察者映射，
  不对应也不拟合任何 TDE。
- `[A]` 宿主消光暂设为零；没有独立宿主先验时不把它用作调色自由度。

## 3. 代码验证

- `[V]` $\lambda F_{\lambda} = \nu F_{\nu}$；
- `[V]` 频率积分和波长积分回收同一有限带宽能流；
- `[V]` 红移后积分严格回收 $(D_{\rm ref}/D_{\rm L})^2$ 的 bolometric 比例；
- `[V]` $z=0$ 且 $D_{\rm L}=D_{\rm ref}$ 时 $F_{\nu}$ 恒等；
- `[V]` $E(B-V)=0$ 时衰减算子恒等；
- `[V]` $R_{\rm V}=3.1$ 回收 Fitzpatrick 表 3 的 optical/IR 锚点；
- `[V]` 2700 Å 两侧的 UV 函数与光学样条连续；
- `[V]` 非有限值、负通量、非单调频率和消光曲线适用域外请求直接报错，不裁剪。

## 4. 输出和边界

- `outputs/phase5a_observer_flambda_spectra.png`：第一张真实 $F_{\lambda}-\lambda$ 图；
- `outputs/phase5a_observer_flambda_spectra.csv`：逐方向、逐波长的 $F_{\nu}$、$F_{\lambda}$、
  $A_{\lambda}$ 和消光后 $F_{\lambda}$；
- `outputs/phase5a_observer_flambda_report.json`：假设和守恒残差。

`[O]` 这一步还没有卷积 Swift/UVOT 真实有效面积，也没有引入事件级宿主消光或真实采样。
它仍使用第四阶段的条件裸盘谱，因此不能从形式高频尾声称 X-ray 预言。
