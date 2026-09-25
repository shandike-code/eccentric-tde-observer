# 77126 完整审计与固定基态长窗口方案

## 实测结论

77126 于 2026-09-25 14:49:28—17:10:01 运行，耗时 02:20:33，COMPLETED/0:0。
32 CPU/128 GiB、anode04、16 worker，stderr 空。9 张 map、3 对反馈全部完成。
Mac 完整审计核验 4183 文件、684 条代码哈希声明、456 条反馈进程与 684 条 map 进程回执。
峰值进程 RSS 为 4040888 KiB，低于 6 GiB；map 墙钟合计 1562.29105 秒，不把整个作业时间当作 map 时间。

核验涵盖 trial/x20/r20/旧物理层身份、块替换与汇总、9632 组频率唯一归属、4096→256→128 归层、
能量恒等式、四分量响应、trust region、原接受门与同期 control 的四种端点比较。
Mac 没有重新积分物质 ODE 或大型辐射场。跨 CPU 解码尺度仍为既定 8eps，没有放宽科学门。

| 候选 | 对原 r20 的 L2 比 | 质量加权比 | 最大单元比 | 判决 |
|---|---:|---:|---:|---|
| thermal | 0.9976885430825692 | 1.0069708627632765 | 1.0032371883703342 | mass/max 失败 |
| population | 1.0053503342839636 | 1.0179333338279413 | 0.999761113538636 | L2/mass 失败 |

两者均只过原 16 门中的 14 门。population 对同期 control 四种组合的最坏质量加权比为
1.002016292109144，仍失败；thermal 同期最坏最大单元比 1.002955822555633，仍失败。
population 加热变化 0.00014880708520449216、内层噪声比 0.008733567174505786，均过门；
最低比气体热能 6.969810473858291e12 erg/g，物理域有效。
因此本次拒绝由残差收缩条件决定，不由负气体热能决定。接受步数 20，新接受数 0。

control 原零位移 7 门通过。其最终响应与原 r20 的向量差 L2 为 0.5271576467146694，
相邻响应差只有 0.005617021305032154。76957→77126 同物质响应变化 L2 分别为
control 0.041431071081119764、thermal 0.055299378635572854、population 0.05718939160663656。
这些是固定物理时间下已观察到的数值迭代变化，不是真误差界；同期 control 也不保证消除内层偏差。

## 工件与复核入口

完整包 `complete-1790327365825177293.tar.gz`，227894104 bytes，SHA256
`12757b3dccf1bd314d98959f9e0b956f7a05b180f4c40f4a669fa29b598a486b`。
Mac 位于 `outputs/review-20260925/`，解包目录 `step21-positive-validation-77126-complete-received`；
学校位于 `outputs/hpc/step21-positive-plane-validation-20260925/archives/`。
审计工具 `handoff/audit_tools/review_step21_positive_plane_feedback.py`，证据
`handoff/evidence/20260925-positive-validation-complete-review.json/png`，终态证据
`handoff/evidence/20260925-positive-validation-77126-terminal.json`。图已查看。

## 方向诊断与为什么不立即混合试步

新小工具采用有限响应模型

$$
R(a,b)=C+a(T-C)+b(P-C).
$$

C/T/P 分别是同轮 control/thermal/population 的完整物质残差向量。
它不是已收敛 Jacobian，也不是辐射仿射外推。三种平方范数在原点的方向导数，
按每轮全部 8 种端点组合检查共同下降区间；最大单元保留全部并列活跃单元条件。
正权重方向的 thermal 比例区间为 76957 的 (0.1638091,0.5727629)、77126 的 (0.1402440,0.6362330)。
局部存在共同下降方向，只说明有限响应模型在同期 control 附近存在下降方向，不说明能越过原 r20 门。

随后按预注册网格 thermal 权重 0:0.125:2、population 权重 0:0.25:12，共 833 点，
同时检查两轮共 16 种端点组合、全 128×4 分量，以及原 r20 和同期 control 的三种范数。
预测全部通过点为 0。最好点 (1.375,0) 的最坏比仍为 1.0047689764828511。
这既不是真实候选的反馈计算，也不是网格外或非线性模型无解的证明，不据此接受或排除全部混合方向。

工具/测试位于 `handoff/audit_tools/`，协议 `handoff/protocols/step21-material-direction-cone-v1.md`；
证据前缀 `20260925-material-direction-cone-review` 与 `20260925-material-mixture-screen-review`，均有 JSON/CSV/PNG。
两图已查看，无 NaN/Inf 或掩盖失败点。未写真实候选、未算新 map。

## 下一批已写好的边界

`operations/diagnose_step21_control_windows.py/.sbatch` 只续算固定 x20 的 control。
用 77126/control 最后 mapped_final 辐射态起跑，保留原 r20、旧物理层、phase1367、dt889.419892762322秒。
最多 16 张新 map，在 8/16 后各计算完整反馈对；所有物理门不变，禁止基准替换与物质 promotion。
每窗口四种端点组合均计算完整残差向量差的 L2/mass/max，再除以固定 r20 对应范数。
12 个比值都严格小于 0.001 才记该窗口一致；两窗口都过也不等于严格误差有界。
第一窗口不过仍允许第二个已声明窗口，以测量漂移趋势；物理/原反馈/资源/身份失败立即停止归档。

资源为 32 CPU/128 GiB、16 worker、4 小时硬上限，USR1 提前 900 秒。
新目录 `outputs/hpc/step21-control-windows-20260925`，历史 dat 不改不删。
测试覆盖完整向量差、跨端点最差条件、缺端点拒绝、预算/停止和基准冻结，连同复用依赖共 47 项 Mac 通过。
Linux 测试、真实小工件预检与实际提交号在后续启动记录中补齐，不把计划写成已启动。

## 备份与讲义校正

Mac `outputs/review-20260925/pre-positive-final-audit.bundle` 与 `automation-before-positive-final-audit.toml`；
学校 `/home/scc/pb24511938/pre-positive-final-audit.bundle`。
Claude 草稿已独立校正：02:20:33 是耗时；684 是哈希声明；同期质量加权比 1.0020163 是失败，
不能与通过的加热/噪声门并写成“全部通过”；有限网格失败不等于全域无解。
讲义追加第 15 节，旧各时刻记录保留，不回写旧判决。
