# 85778通过后：full/half各一次真实映射

新目录outputs/hpc/x20-85778-true-validation-20261006。85778完整11门已由Mac独立归并301片、核806代码和18直接来源及小QP证书，真实调度COMPLETED0:0。候选只取得筛查资格，预测p尚不是实际T(q)。

固定c=[-6.846213173701946,-0.3537868262980542,0.0659556218584672]。同八场84026H16/H8、82989H16、82518H16 previous→final。原锚点为84026H16清单第一行iteration15的输入和输出，不取下一行。full按已筛查的原表达式生成，half=0.5*锚点输入+0.5*full；既有写入/预测误差核复用。所有76块用同一三系数，不分块拟合，不把保存A作目标，不使用旧83075负点证书。

从84026已审归档核config/state/trial/manifest/feedback_protocol、前后字段链和正式物理旧层/base/r20。其数值工件完整，但调度终态仍未知；独立字段保留false/null，不补造COMPLETED。trial先写再init，encoded/base/direction/r20/relaxation逐位核；native相位1367、dt889.419892762322秒、映射物质及算子配置保持。accepted20不变。

32CPU128GiB、16worker、2h硬限、USR1提前300s。full/half各一张map，总2map、0反馈、0物质；每支76块，共152worker回执。父与单worker<6GiB，free>=10*STATE_BYTES，源/代码/候选种子/真实输出SHA及八源inode/mtime/size前后核。可在学校写新dat，但不下载或入Git。任何物理域、资源、来源、数值门失败保留；不自动恢复、扩预算或缩步。

真实输出通过原actual.validate/checks及prediction_error：缺陷L2/Linf和边界/原残差、半步仿射一致性、实际输出与预测p的L2/Linf误差，共原16门。half一致性误差不是缺陷，预测误差小也不是未知固定点误差界。全部通过只允许下一次有界正式反馈窗口的决策，不授予物质步或校准资格。

自动归档complete/failed/interrupted排除dat。batch-exit在Python结束后由shell写，晚于自动归档，下一轮需另取；真实scheduler-terminal由watch记录，与子进程返回分开。先核run/status/summary/validation/stderr/终态，再核归档字节SHA和每工件清单，独立复核152回执、来源血缘、trial/native和301片统计。

## PRE-RUN

Code：新入口绑定85778审计及新系数；需全部原11门、完整字段一致、真实调度及QP证书标志。跨频块写入逐位与筛查表达式一致，负路径测试覆盖错job、缺门/失败门、错系数、字段/来源、物质scope和缺调度/证书。
Logic：固定84026H16原输入输出为锚点；先构造新q，再原算子T(q)，再对比p，不能跳过真实映射。
Physics：同一固定x20背景原转移算子；不改能量、dt、r20、微物理。两个真实缺陷与预测误差分开报告，不作自洽或整盘I_nu结论。
Decision：两端相关测试、shell/源码检查通过后，只运行上述两张真实map；反馈与物质更新DO NOT RUN。
