# 85889：双历史新增预算匹配验证已启动

## 本次决定与范围

85875新16−8窗口全部通过，但对保存82518A16的物质响应仍失败。依已记录独立协议，重新演化A、H两种历史并重新计算正式反馈，以检验新增预算匹配后的有限一致性。保存A不作拟合真值。85875的16map预算已关闭。

新作业85889于2026-10-06 09:15:59（北京时间）开始，在anode02、Students/qos_stu_cpu_long实际RUNNING。独立硬限6小时至15:15:59，USR1提前900秒；实际32CPU/128GiB，配置16worker。六小时是预算上限，不是ETA。

数值提交9555a78a77b9025e30405684dee2669d9e43baee；目录outputs/hpc/x20-85875-matched-feedback-20261006。入口operations/x20_85875_matched_feedback.py和同名sbatch；协议handoff/protocols/x20-85875-matched-feedback-v1.md在数值提交中冻结，提交前状态文字保留，本报告记录实际启动。

## 来源与判据

A种子是82518 accelerated/endpoints-map16/mapped_final.dat，SHA03d7c7ff5717e4871c35450e774992b79e729f919a986e93d732dd3250801fb2；H种子是85875 historical/endpoints-map16/mapped_final.dat，SHA8814597bcd42c968341a59ea17ab85b5c51c0780cbc9079ee595e952da1b0bfb。各10099884032字节，均为真实第16次映射输出，不是原反馈final输入。

两支各16张，顺序A8→H8→A16→H16；每8/16张后各一对原正式反馈，共32map、4pair、0新物质步。两支x20、原物理旧层、base/r20、phase1367、dt889.419892762322秒及原核相同。两支有共同来源历史；新增预算相同不表示累计年龄或独立随机初值相同。

保留各自16−8、同龄新H对新A、各自对旧pair16三类比较，并另存新H对旧保存A诊断。完整512向量先相减再取L2、质量及Max-cell范数；80195四组P−C逐范数最小值重新归并。保留原核严格小于0.001及0.1门，不放宽。两支新窗口、新16跨支四组合响应和五类率/加热门全部通过才给有限校准候选资格，仍需独立审阅。

原七门、物理域、内层、资源或完整性失败立即停；只有漂移失败才继续完成已定匹配端点，不增加预算。accepted20、baseline_replaced=false、0新物质步、strict_error_bound=false保持。原85821真实终态与祖先84026未知分别保留。

## PRE-RUN与实现审阅

两端clean和exactHEAD核验、完整bundle备份与verify通过；学校仅通过增量bundle verify、fetch新ref和ff-only同步。Mac初组121项测试1.40秒；学校初组90项22.73秒。最后审阅器路径修正的10项测试Mac0.89秒、学校6.57秒；这些测试范围有重叠，不相加冒充独立数量。shell和diff检查通过。

最终学校轻量prepare实际核983项小来源，26.399845370004186秒；两支trial逐位/native/算子核通过，冻结信号为[0.02929545590160747,0.0015563020846738518,0.015995237347141762]。20个dat仅核存在、大小及统计信息，没有读取大场。生产前后全部来源SHA、所有20场inode/size/mtime及HEAD/clean仍完整执行。磁盘满足24份完整场的242397216768字节下限。

Mac审阅器预检核979项小来源、801项源码git show、20场既有审计绑定。首次路径检查发现16个已存在的旧A小来源未映射，已补映射并通过回归；没有改变来源字节或断言。新32map/4pair完整E2E尚待实际冻结归档。

## 启动后的POST-RUN检查与后续

09:16:42观察真实RUNNING累计43秒，父preparing，尚无声明/child state/反馈，stderr0，学校9555a78 clean。这时尚不能声称生产SHA、任一map或反馈已完成。未出现可评估的新物理结果，数量级、漂移与物理域判定留待输出；无新图。

只读watch已启动，目录outputs/review-20260925/x20-85875-matched-watch-85889，25200秒预算、60秒间隔，PID3628021仅启动凭据。先保存真实调度终态，再调用无工具学校CLI；实际deepseek-v4-flash[1m]。首稿与独立修正见20261006-x20-85889-watch-{draft,review}-00.json。

每对及complete/failed/interrupted自动归档排除dat。终态先取watch/status/summary/stderr、实际scheduler与child退出；核路径、字节数和SHA后收件，不覆盖旧目录。batch-exit晚于归档需单独收取；Python退出不能补造Slurm成功。

审阅入口handoff/audit_tools/review_x20_85875_matched_feedback.py已绑定提交回执20261006-x20-85875-matched-submit.json。部分pair单独新收件目录/target、不传terminal；完整终态命令使用job85889、最终archive stem及20261006-x20-85889-terminal.json，输出20261006-x20-85889-final-review.json。硬失败用独立失败审阅，不强套成功模板。学校运行期间保持9555a78，不同步后续文档提交。

完整终态收件准备好后，在Mac仓库根目录执行（`<stem>`为已核验的最终归档文件名去掉`.tar.gz`）：

```bash
PYTHONPATH=.:src:scripts OPENBLAS_NUM_THREADS=1 .venv/bin/python handoff/audit_tools/review_x20_85875_matched_feedback.py --job 85889 --base <stem> --out outputs/review-20260925/x20-85875-matched-85889-received --target handoff/evidence/20261006-x20-85889-final-review.json --terminal handoff/evidence/20261006-x20-85889-terminal.json
```

收件ROOT为outputs/review-20260925，需要`<stem>.tar.gz`、`<stem>-receipt.json`、`<stem>.json`以及`85889-stderr.log`、`85889-batch-exit.json`。终态JSON需包含job_id、state、真实scontrol、完整summary和batch_exit；只有child明确退出才能用unknown execution快照，不伪造COMPLETED。
