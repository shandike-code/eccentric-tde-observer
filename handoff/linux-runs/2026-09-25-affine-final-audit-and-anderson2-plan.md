# 76957完整审计与四态只读诊断决策

2026-09-25，SSH复核已恢复。76957于09:42:08—11:44:53运行，COMPLETED 0:0，墙钟2:02:45。
32CPU/128GiB/anode18，9张map、3对反馈均完成，无新物质步；接受计数保持20。

## 独立复核证据

完整归档 `outputs/hpc/step21-radiation-affine-validation-20260925/archives/complete-1790307865112803779.tar.gz`，227296958 bytes，SHA256 `278c312c42fac69f916ccc1c9d35fa90b2598ef567be7b920628213e62a45b07`。
Mac接收目录 `outputs/review-20260925/step21-affine-76957-complete-received`。
工具 `handoff/audit_tools/review_step21_affine_feedback.py`；完整JSON/PNG在
`handoff/evidence/20260925-step21-affine-complete-review.*`；终态在
`handoff/evidence/20260925-step21-affine-76957-terminal.json`。

逐文件核对4183项、680条冻结代码声明、456份反馈和684份map进程回执。
重算逐块原子/common反馈替换与总和、频率归属、4096→256→128归层、能量恒等式、
四编码残差、物质trust region、原始门和新控制四端点组合；全部与平台一致。
Mac未重新积分物质ODE、未下载或重积分大型辐射态。图已目视核对。

## 六端点结论

|case|最终L2|质量加权|最大单元|加热相邻变化|原门失败项|
|---|---:|---:|---:|---:|---|
|control03|8.22193430815|0.265890486697|2.70586612912|0.000172745595017|控制稳定；非物质接受|
|thermal03|8.1515759758|0.26308794642|2.71396098874|0.000176273205223|candidate_mass_weighted_contraction_pass, candidate_maximum_cell_contraction_pass|
|population03|8.22127345076|0.266530097111|2.704531458|0.000175085572793|candidate_l2_contraction_pass, candidate_mass_weighted_contraction_pass|

thermal相对原r20比为0.9974999308/1.0044959110/1.0033123358；对新控制四组合最差最大单元比1.0030029349。
population相对原r20比为1.0060287388/1.0176383842/0.9998263740；对新控制四组合最差L2为1.0000522325、质量比1.0025571453。
两个方向原门和新控制比较均失败；不更换分母接受候选。两个有限候选的原噪声门均通过。

同一control最终响应减原r20的向量L2为0.5135387635，相邻对仅0.0066071731。
population相对76931终点漂移L2为0.3283382791，本轮相邻差0.0087424250。
这些是实测跨度而非严格真误差界；不能据此证明发散、无解，也不能把漂移归因于仅仅重命名参考。

全部六端点最小气体热能7.00290793707e+12 erg/g；峰进程4044636 KiB。
map本身累计1286.364s，不含构造/哈希/反馈，不能拿它估算整个作业成本。
日志无stderr；未发现NaN/Inf、负气体能量或资源越界。曲线无新增异常尖峰，仍以物质收缩失败为结论。

## 决策与边界

停止沿相同两个物质方向追加盲目map。下一任务为三个固定case的四态Anderson深度2只读可行性检查，
复用其四个连续大态；详见 `handoff/protocols/step21-anderson2-scan-v1.md`。
用默认4CPU/16GiB、1小时硬上限；全部三case一次完成。它是顺序I/O和小矩阵诊断，没有16个独立转移worker，
为此占用32核不会自动获得8倍速度。真实候选映射若另行通过审阅，仍使用32核cpu_long。

只读扫描不写候选、0新map/0反馈，不能宣布收敛。Gram病态或正性/预测门不满足都记录失败，不改门、不裁剪。
下一次真实验证必须在独立审阅后冻结新协议；不自动重复加速，不更改x20/r20/dt。
仍未得到耦合柱或可用于整盘观测的自洽I_nu。

## 备份与验证

Mac `outputs/review-20260925/pre-affine-final-review.bundle`及同目录`automation-before-affine-final-review.toml`；
school `/home/scc/pb24511938/pre-affine-final-review.bundle`。旧数值态未改。
新增扫描测试与相关已有回归：Mac 31 passed in 0.90s；Shell语法和diff检查通过。
学校端测试与提交编号在后续启动回执中补充，不预先宣称。

## 已提交下一批

数值代码 `bc6879cdd909d03ad67bd816f936bc04deed2d4b` 三端一致。Mac重检31 passed in 0.89s，Linux 31 passed in 19.96s。
77066于12:01:11提交、12:01:12在anode05启动，默认4CPU/16GiB、1小时上限至13:01:12。
启动检查RUNNING，status preparing（正在校验源），stderr 0 bytes。
Watcher tmux `step21-a2scan-77066` 已存在；终态回执将写入
`outputs/review-20260925/scheduler-77066/scheduler-terminal.json`。
代码不会续交；中断或失败需先审现场。启动证据在
`handoff/evidence/20260925-step21-anderson2-77066-start.json`。

完整审计脚本已准备：`handoff/audit_tools/review_step21_anderson2.py`，参数为
`--archive`、`--receipt`、`--prior outputs/review-20260925/step21-affine-76957-complete-received`、`--output`。
下一次取新归档重聚合602片Gram/正性/边界/残差与选系数，核对源元数据与本次已审工件；
图须目视检验，明确Mac未读取大场。若支持真实试验，再冻结新的32核验证协议。

Claude讲义草稿出现把辐射端点称接受态、误将噪声门通过解读为排除内层误差、混淆辐射与物质方向等错误，
已逐条纠正后写入原讲义第8节；未直接采纳草稿。
新改3份Markdown格式检查通过；全库机械检查仍有6份既有讲义问题，未批量修改旧文件。
