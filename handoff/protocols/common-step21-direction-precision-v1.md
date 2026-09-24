# 第21步拆分方向：固定物质的辐射精度检验 v1

## 为什么继续计算

76905完成，但thermal08仅15/16门通过，最差单元不收缩；population08仅13/16门通过，noise=0.1117982162超过0.1，且L2、质量加权对原r20不收缩。population从map4到map8的响应向量漂移L2=0.0806501，大于其对新control的信号L2=0.0476478。相邻对照之间漂移L2=0.0550610。不能把这些有限差商当成已解决内层误差的Jacobian；也不能凭最后一张表决定混合权重。

## 冻结内容

保持76905的三份trial文件逐字节不变：已接受$x_{20}$的零位移对照，以及$x_{20}+d_E/256$、$x_{20}+d_P/256$。$d_E$仅含全部128层的气体热能编码，$d_P$仅含全部128层的三个电离布居编码；残差依旧计算全部四分量。物理旧层、phase1367、dt889.419892762322秒、密度、微物理、源定义、原$r_{20}$分母不变。气体热能编码不等于总比能，population温度必须按原codec随电子数解码，不能额外冻结温度。

源归档SHA=8ab3044404714d9d1c62420cbd41d1c9665c66660d6afac2f036584cbcd327ba，作业76905与Mac十端点审计为入场条件。每份源state/config/trial与已审归档逐项核SHA；原接受20声明、原r20及物理身份再次核对。复制trial先于pipeline初始化，初始化后再核exact_trial/native_identity。

## 预算和停止条件

新run `outputs/hpc/common-step21-direction-precision-20260925`，control、thermal、population依次各追加8张map，在新map4/8计算正式反馈，共最多24张map、6对反馈。每个case从76905中自身最新mapped后继起跑，绝不从其他case借种子。新control4和8分别用于两个方向同名轮次的四端点组合比较；原r20分母也始终保留。零控制不进入有限步接受。

control缺少内层合格连续态、反馈不稳或物理响应失败即停，不能带着缺失对照跑候选。任一case发生非有限、非正气体热能、全态、资源、代码或血缘失败，整个批次停止；不忽略单元。非零候选单纯noise或收缩门失败仍完成固定8张精度预算，不加map、不改幅度、不组合方向。USR1提交当前batch后停止，保留工件，不盲重试。

原inner=1e-4、boundary=1e-3、heat=1e-3、noise=0.1、16门与信赖域不变。外层永远diagnostic_only、promoted=False、accepted20/new0；即使原pair evaluator某次全部通过，也不自动接受21，不推进物理时间。`direction_budget_complete_requires_review`只是预算完成。

cpu_long32CPU/128GiB，16worker，BLAS1，NUMPY_MADVISE_HUGEPAGE=0，5小时上限。三case共27个工作/保留大态，入场32STATE_BYTES可用空间；每worker native和/proc小于6GiB，每反馈态累计worker批时间小于900秒。预计约3小时，仅是本批成本估计。

## 完成后

取小归档与receipt，独立复算SHA、逐块替换和、归层/ownership、物理旧层、trial/seed身份、能量恒等式、四残差和三范数、原门/四组合及资源。保留每个case跨轮漂移与相邻两态漂移，不把任一当严格误差界。若population信号仍未与漂移分离，则不拟合组合权重；先审数值误差/缓慢模。若方向判断稳定，再单独声明组合候选并全场重算及确认。仍不构成耦合柱、全盘$I_\nu$或真实谱线解。
