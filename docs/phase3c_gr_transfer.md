# Phase 3C：Cunningham 式 Schwarzschild 弱场直接像传递

## 传递函数结构

Cunningham (1975) 的关键思想不是某个特定圆盘公式，而是把局域出射与到达远方观察者
的映射分开。当前实现写成

$F_{\nu}_{\rm obs} = D^-2 sum[dA_{\rm image} \, g^3 \, I_{\nu}_{\rm em}(\nu_{\rm obs}/g, \mu_{\rm em})]$

其中 $dA_{\rm image}/D^2=\mathrm d\Omega_{\rm obs}$ 是像平面立体角，
$g=\nu_{\rm obs}/\nu_{\rm em}$，且 $I_{\nu}/\nu^3$ 沿测地线不变。

## 当前弱场实现

1. `[A]` Schwarzschild lapse 精确写成 $\sqrt(1-2GM/rc^2)$；物质速度仍取 ZO 输入
   上的 Newtonian 椭圆 Kepler 速度与同源呼吸速度；
2. `[A]` 直接像发射角采用 Beloborodov 关系
   $1-\cos(\alpha)=(1-2GM/rc^2)\,(1-\cos(\psi))$；
3. `[V]` 冲量参数 $b=r\,\sin(\alpha)/\sqrt(1-2GM/rc^2)$ 将每个源顶点映到远方像平面；
   对映射后三角形求面积，得到数值 Jacobian；
4. `[A/O]` 只保留直接像，不处理多像、Kerr 自旋、时间延迟、曲线射线与盘面的再次相交；
   若出现像平面折叠或奇偶翻转，代码直接拒绝，要求升级传递模型。

这是一套 Cunningham 式可替换架构，不是完整 Kerr ray tracer。

## 极限与结果

- `[V]` $M/r \to 0$ 时，像坐标、光子方向、面积和光谱回到 Newtonian 平行射线结果；
- `[V]` 视界内点、超光速物质、背轴 caustic 和直接像折叠均有拒绝门；
- 严格参考源 $2GM/(rc^2)=2.64e-4--2.14e-3$，确属弱场；
- GR 直接像面积相对直线无遮挡投影增加 $0.021\%--0.193\%$；
- GR/直线临边谱在 $5e14 Hz$ 为 $1.0003--1.0067$，在 $1e16 Hz$ 为
  $0.9997--1.0457$。Wien 尾的小频移可被指数放大，但该高频局域谱仍受大气失效门限制；
- $i=75^\circ$ 的进动相位最大/最小通量比为：
  $2.805$ ($5e14 Hz$)、$2.416$ ($1e15 Hz$)、$1.639$ ($2e15 Hz$)；
- $33x512 \to 65x1024$ 的五个探针频率最大变化 $9.05e-4$；无遮挡情况下自适应
  深度 $0 \to 2$ 变化为机器精度零。

## 代码与产物

- 核心：`src/eccentric_tde_observer/gr_transfer.py`
- 测试：`tests/test_gr_transfer.py`
- 收敛：`outputs/phase3_transfer_convergence.csv`
- 光谱：`outputs/phase3_observer_spectra.csv`

