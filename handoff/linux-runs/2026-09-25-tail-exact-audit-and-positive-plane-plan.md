# 77094精确符号审阅与带正性约束的二维系数搜索

2026-09-25。77094在anode04以4CPU/16GiB运行13:08:36—13:13:41，5:05，COMPLETED 0:0，stderr空。
0新map/候选dat/反馈/物质接受，接受计数保持20。Mac复核完成，图已查看。

## 精确证据与边界

归档 `complete-1790313220749040604.tar.gz`，97308bytes，SHA256
`93c4845e618872f0dc9d36e36e82f619b2d4da583bcd5abc7364186f055b216f`。
Mac目录 `outputs/review-20260925/`；school源run `outputs/hpc/step21-affine-tail-diagnostic-20260925/archives/`。
工具 `handoff/audit_tools/review_step21_affine_tail.py` 真实端到端通过：3文件、682代码声明、
60个有理数见证独立精确重算，逐点float64 hex复现，全部结果与声明一致。
`handoff/evidence/20260925-step21-tail-review.json/png`与终态JSON保留。

Linux longdouble尾数63位；峰RSS539602944bytes。每个候选都有10个严格负有理数见证，合计60个。
这足以否定六个既有候选，不能仅通过提高其组合运算精度救回。并不是全部网格点都用有理数穷举。

|case|eta|float64负点数|longdouble负点数|精确负见证|零基态障碍见证|
|---|---:|---:|---:|---:|---:|
|control|0.125|567894|567894|10|0|
|thermal|0.5|468990|468992|10|0|
|thermal|0.25|446158|446160|10|0|
|thermal|0.125|398836|409898|10|0|
|population|0.25|517202|517204|10|0|
|population|0.125|496046|496050|10|0|

较宽精度下负值并未消失，thermal eta=.125反而多出11062个负点。这里的计数没有细分新增负点在原float64中为零还是正数，
只能说更宽精度显露了原来未标记为负的点；不能笼统说原负数均由最后一次组合舍入制造。符号来源仍需区分“现有四态字节的外推”与
“这些字节在更早求解时怎样产生”；本诊断只证明前者，不反推历史误差来源。

没有零基态负斜率见证，因此不能宣布所有正eta都不可行。仅在已检查尾部，由longdouble得到的
必要上界约为control0.00248276155、thermal0.0159076213、population0.00562022269。
它们不是全场充分条件，也不是已验证的新阻尼候选；不在旧协议补扫这些eta。

## 下一步的必要改变

既有方法先求无约束最小值，再沿同一条射线缩小。新方案直接在(u,v)平面加入逐点正性半平面，
允许改变方向。使用已审Gram，初始约束来自上述精确见证，所有旧物质、辐射源、原r20和dt保持不变。
约束用每个字段实际参与的三个强度正规化，不能由全场大尺度抹掉弱尾约束。

`operations/scan_step21_positive_plane.py/.sbatch` 与
`handoff/protocols/step21-positive-plane-v1.md`：三case各最多6轮全频扫描；每片每字段最多增加2条
最严重的归一化违反约束，但所有负点照常计数、下一轮全场再查。每次求解不超过4096条约束。
二维多边形上解析寻找内部/各边的二次目标极小值，系数L1<=191；统一朝原点退回1%，
最终仍逐点按原float64运算检查非负与原门，不能把全局系数退回说成逐单元裁剪。

资源默认4CPU/16GiB、1小时硬上限，单进程RSS<6GiB。不写候选、不算新map、不提交反馈。
预测合格才考虑另行冻结32核真实验证；预算内没有合格项就如实记录，不证明全约束问题无解或已求全局最优。
Mac审计入口 `handoff/audit_tools/review_step21_positive_plane.py` 已准备，输入新归档与77066/77094归档。
其小矩阵重放复用同一优化器，必须明确这个验证边界；它不是第二个独立优化算法或大型场重积分。

## 验证与备份

Mac最终相关50 tests passed in 0.80s，包含每轮结果在下一轮中断前已保存的验证。首次测试发现：在极小活动尺度下，把无关第四态也除以该尺度会溢出；
已改为只除实际参与约束的三态。另一个合成测试在预先固定1%退回后未满足严格1e-4门，
修正测试输入的扰动幅度并用解析式核验剩余误差，科学门与退回系数未更改。重跑无警告。

Mac `outputs/review-20260925/pre-tail-result-review.bundle` 与 `automation-before-tail-result-review.toml`；
school `/home/scc/pb24511938/pre-tail-result-review.bundle`。旧数值文件一律未改。
本报告不声称获得耦合柱或整盘自洽强度；阶段仍是固定物质辐射求解的数值改进。

## 下一批已提交

数值代码 `24b7a57c023fbee1ab69c4f711c0d83ce6a791f2`，Mac/学校/GitHub一致；学校50 tests passed in 20.40s。
Git推送曾报ref锁的旧预期不匹配，但ls-remote确认目标已是同一提交，未强推、未重写历史。
77102于14:00:14提交、14:00:15在anode04启动，默认4CPU/16GiB、上限15:00:15。
启动快照RUNNING，status preparing，stderr空；每轮进展将写到case-progress.json。
watcher tmux `step21-positive-77102`，终态将写入
`outputs/review-20260925/scheduler-77102/scheduler-terminal.json`。
完整启动记录 `handoff/evidence/20260925-positive-plane-77102-start.json`。

结束后审计入口 `handoff/audit_tools/review_step21_positive_plane.py`，参数
`--archive <new> --receipt <new> --scan-archive outputs/review-20260925/complete-1790309530157168659.tar.gz --tail-archive outputs/review-20260925/complete-1790313220749040604.tar.gz --output handoff/evidence/20260925-positive-plane-review`。
审计工具尚待真实新归档端到端执行；不预先声称已验证新候选。
