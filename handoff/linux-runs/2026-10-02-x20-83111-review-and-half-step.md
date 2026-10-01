# 83111边界拒绝审阅与显式半步选择

83111于Oct2 00:11:57–00:19:18完成，COMPLETED0:0，4CPU16GiB、anode02/default；程序437.618826705秒，RSS895143936字节，stderr空，数值a51dce6c3ab3c7cc508d7b2846a099f3b95d9ed2。
七文件小包83111-constrained-prediction-review.tar.gz为105971字节，SHA256=2a4624d0588d51fc74b27b4af8a479c42419dc262dd841425e2a07be6593f2ba。独立首次E2E审计通过清单、源码git show、来源、原小问题KKT、完整301片80位统计归并。证据20261002-x20-constrained-prediction-83111-review.json；Mac未重读大场。

## 保留拒绝，分清两个边界条件

|量|锚点|full|half|
|---|---:|---:|---:|
|L2比|1|0.5401123518430682|0.7122464043391885|
|Linf比|1|0.6620136935227418|0.830934607656037|
|边界L1|1.4944742777112987e-6|1.7939381225369699e-6|2.184015347699317e-7|
|边界总通量变化|1.4944649597861369e-6|1.793635388459437e-6|1.4971471756218476e-7|
|原辐射残差|3.863234968876568e-6|2.556905507146513e-6|3.209713426164524e-6|

四个候选场minima均0，full/half存储非负通过。原11门仅full_boundary_l1、full_boundary_bolometric失败：尽管绝对变化均低于0.001，full分别比锚点增大至1.2003807287、1.2001856428倍，不满足原非增条件。不能将低于绝对门当成整体通过。

边界带符号总通量变化（原核积分单位）依次+24463324.497115925、-29365152.713745523、-2450914.108259912。全局积分确实越过零点；这不是逐频全部同号或物质温度过冲的证明。half边界L1和总通量变化分别为锚点0.1461393736、0.1001794767倍，且L2比0.71225满足完整步原0.8收益门。

## 决定与限制

有了旧half的具体收益证据，显式选择原全局系数除2的新候选[-2.5857236634643006,-1.0142763365356995,0.45]，不是失败后无人审阅的自动减半。新full按anchor+sum(new_c*direction)计算，旧half按0.5*anchor+0.5*oldfull计算，浮点不保证逐位相同。因此新full/half仍须301片全场原11门；没有从旧half直接进入真实map。

新名x20-83111-half-prediction-20261002，4CPU16GiB/default/1h，前后SHA/文件身份/RSS守卫；0map/feedback/material，不写dat、不改dt/能量/r20/物质x20。不clip、不删失败单元。83111完整步拒绝不改写。新候选失败不默认再次缩步；成功并独立审阅后才新名32CPU128GiB16worker真实full/half最多2map、0反馈/物质。

## PRE-RUN / POST-RUN

Code PASS：审计源码/来源/小问题KKT和统计齐备，入口绑定精确失败机制、半步收益和原方向；27 tests passed / 0.72秒，shell语法通过。Logic PASS：全域统一缩放系数、不复用旧half通过标签、原11门不改。Physics WARNING：边界变化是筛查量，未闭合物质和整体能量；预测p不是T(q)。Key Issues：新表达式非负仍须检；新half未测；不可接受物质步。Decision RUN一次有限筛查。

POST-RUN：83111无NaN/Inf、无stderr，量级和符号变化已定位，数值改善与边界失败同时保留；没有自洽大气或整盘I_nu结论。学校验证/启动记录后补。

## 启动回执

数值提交23d8d8e953a7b03e066eb5a9216a1b171cfdcf8a；学校27 tests passed / 14.95秒，shell语法通过。Mac pre-83111-review-20261002.bundle、学校pre-83111-half-code-20261002.bundle备份，增量83111-half-code-20261002.bundle核验后fetch/ff-only；clean/exactHEAD后提交。

83131于Oct2 00:39:09开始，anode02/Students/qos_stu_default、4CPU16GiB，硬限01:39:09。20261002-x20-83131-submit.json为RUNNING/preflight。watch PID381238只作启动凭据，latest已落盘；目录outputs/review-20260925/x20-83111-half-watch-83131；PYTHONPATH、Node PATH、start_new_session齐备。CLI无工具只读、先保存scheduler-terminal。讲义128、CLI原稿/独立纠正入库，实际deepseek-v4-flash[1m]；已消除提示及原稿中新旧c混淆造成的二次减半歧义，代码实际只除2一次。
