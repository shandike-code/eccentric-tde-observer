# Phase 3B：角分辨强度、临边昏暗与线偏振

## 最小角闭合

第二阶段采用各向同性局域强度 $I_{\nu}=B_{\nu}$。Phase 3B 引入局域出射角
$\mu = n_{\rm surface} \cdot n_{\rm ray}$，并采用 Eddington 临边昏暗：

$I_{\nu}(\mu) = (3/4)\,(\mu+2/3)\,I_{\nu,\rm isotropic}$。

`[A/V]` 归一化满足
$2\,\int_{0}^1 [(3/4)(\mu+2/3)]\,\mu\,\mathrm d\mu = 1$，所以只是重分配方向，不改变局域半球
总能流。网格顶点法向由相邻三角形面积向量加权得到，不平滑或移动光球。

## Stokes 偏振闭合

Stokes $I,Q,U$ 分别表示总强度和两个线偏振分量；$+Q$ 定义为沿 observer 像平面
$u$ 轴。采用保守半无限电子散射大气的 Chandrasekhar 极化拟合：

$p(\mu)=0.1171\,(1-\mu)/(1+3.582\,\mu)$。

- `[L/A]` 它回收临边 $11.71\%$ 和正视 $0$ 的经典极限；
- `[A]` 每个表面元的电矢量取垂直于“射线—法向”子午面，再在像平面相加 $Q,U$；
- `[O]` 未包含吸收造成的偏振稀释、Faraday 旋转、磁场、GR 平行移动和 returning radiation；
- 当数值 Wien 尾给出严格 $I=0$ 时，偏振无定义，代码直接拒绝，不用 $0/0 \to 0$。

## 代码验证与严格参考源结果

- `[V]` 关闭临边昏暗和偏振时逐数组回收第二阶段 observer $F_{\nu}$；
- `[V]` 平圆盘的未分辨偏振严格等于同一 $\mu=\cos i$ 的平行平面值；
- `[V]` face-on 平圆盘偏振为零；新增角闭合相关测试全部通过；
- 严格偏心参考源在 $5e14 Hz$ 的未分辨偏振范围为
  $1.27e-5--5.95e-2$（约 $0.0013\%--5.95\%$）；
- $i=75^\circ$ 时偏振随进动相位显著变化，并有温和频率依赖。这是角闭合下可检验的
  条件预言，不是已完成的 TDE 偏振大气预言；
- 临边昏暗相对各向同性局域强度可把方向通量乘以约 $0.627--1.248$，因此它对倾角
  归一化的影响大于本参考源的弱场像弯曲。

## 代码与产物

- 核心：`src/eccentric_tde_observer/polarization.py`
- 几何法向：`src/eccentric_tde_observer/geometry.py`
- 测试：`tests/test_polarization.py`
- 光谱/Stokes：`outputs/phase3_observer_spectra.csv`
- 方位诊断：`outputs/phase3_orientation_diagnostics.csv`
