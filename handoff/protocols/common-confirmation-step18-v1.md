# 半幅度第18步候选的同态确认

## 先决条件

76434的control 4张、half 8张全部完成，Mac核验4629文件、456反馈和912map进程回执。half第4张13/16，只加热三门失败；第8张16/16及新基态四组合通过。该结果支持试探，不自动接受18。审计来源为`20260924-common-step18-backtrack-review.json`和76434终态，真实文件须逐项与已审归档一致。

## 固定物理与身份

零控制为已接受$x_{17}$；候选始终为$x_{17}+r_{17}/128$，$r_{17}$保持76260 confirm2 final响应，不能换成新基态残差。物理旧时间层、密度、phase1367和889.419892762322秒保持不变。两种trial在初始化前落盘；编码、基态、方向、残差、alpha和温度/H/He/比能解码逐位核验，真实native镜像在allocation内预检。原信赖域温度0.5、能量0.25、布居0.05不改。

## 完整条件批次

新目录`outputs/hpc/common-confirmation18-20260924`：

1. control：从76434 control最新后继开始，4张map和一对反馈；原五个稳定性门、内层、正物质域、完整态和资源全过，且原half pair08相对新control四组合均收缩，才继续。
2. confirm1：同一half候选，从76434 half map8的mapped_final开始，2张map和一对反馈。原16门及新control四组合均过才继续。
3. confirm2：仍同一候选，从confirm1最新后继开始，2张map和一对反馈，执行同样全部门。

任何失败即停止，不临时追加map、不改alpha、不缩物理dt，不裁剪、floor、删点或后归一化。全部通过也只标`confirmed_requires_mac_review`，计数仍17、新增0；Mac独立复算后方可另建接受记录。每个child独占三槽，两个反馈输入和后继均保留，不能覆盖祖先端点。

## 资源与记录

cpu_long 32CPU、128GiB、16worker，BLAS1、hugepage0，4小时上限；最多8新map、3反馈对、9份新dat，入场要求12份dat空闲。每worker原生及/proc小于6GiB，每新反馈态累计worker批墙钟小于900秒。USR1当前batch提交后停止。冻结完整代码、协议、输入、环境、scheduler和资源回执；只下载小归档，不传dat、不删旧checkpoint。

预计约一至两小时是根据近期同类批次70至95分钟给出的调度参考，并非科学通过或整体完成时间保证。有限步确认不等于代表柱收敛，更不等于整盘角分辨强度或真实谱线。
