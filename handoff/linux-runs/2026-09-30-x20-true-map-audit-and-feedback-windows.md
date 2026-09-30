# 81679真实映射审计与81769配对反馈窗口

## 结论

81679于2026-09-30 09:49:17 CST正常完成，Slurm COMPLETED/0:0，墙钟40:32。两张真实map通过全部原门；独立归约确认full全场L2缺陷比0.7646030652102698，达到本次≤0.8的目标。尚无新的H/He反馈、物质步或严格辐射误差界。

下一作业81769已于10:30:11在anode06运行，32CPU/128GiB/16workers，6h硬限。入口 `operations/x20_accelerated_feedback_windows.py/.sbatch`，代码6d15f3f827bdb144fe253a3ff78d2921db7964ab，协议 `handoff/protocols/x20-accelerated-feedback-windows-v1.md`。只推进固定x20的两个数值初值，不改变r20或接受第21步。

## 81679证据与POST-RUN CHECK

小归档 `complete-1790732954355330907.tar.gz`，3372907 bytes，SHA256 `5fbcaa1171ca1da38947fb933c6a88dd45e18fdfc47a142d2b02a4f41766662e`。Mac解包 `outputs/review-20260925/x20-expanded-81679-received`。328小工件、758代码声明、789来源声明及152 worker回执全部校验；301个32频组分片覆盖全部9632组。Mac独立重做小统计量归约、门和血缘检查，没有下载大态、重做全场原映射或native核。

|量|full真实值|half真实值|
|---|---:|---:|
|全场L2缺陷/原缺陷|0.7646030652102698|0.8809454916579785|
|全场Linf缺陷/原缺陷|0.8080673187346159|0.9040336595311778|
|边界谱L1变化/原变化|0.9737280336774233|0.8359503447575778|
|bolometric变化/原变化|0.6324335521986655|0.18378333966774588|
|原全局辐射残差|4.424841481386891e-7|4.950381984957344e-7|

半步仿射差L2/Linf除以原缺陷尺度为2.1243019538891948e-9与2.2941768715625023e-9，均≤1e-6。全部11项预测门及12项真实门通过；full L2门≤0.8，而half仅要求非增，不把half的0.881误判为不合格。

父进程stderr为空；小统计量无NaN/Inf，逐块状态与非负/有限回执有效。父进程峰值932028416 bytes，最大worker峰值3585224 KiB，均低于各自6GiB上限。full/half原map本身约152/141秒，其余墙钟包含读写、哈希、准备与全场扫描，不能只用map核的时间估整个任务。

full/half最差自身归一化块均为block74，约0.14324/0.14332，未被删除。很小的全局归一化残差不等于每个频块的自身相对变化很小。新的正式反馈和完整物质响应窗口正用于检验这些变化是否影响物质结论。

图 `handoff/evidence/20260930-x20-expanded-validation-review.png` 已目视核验；CSV与作图源码齐备。L2图中预测与真实点几乎重合，只代表本候选的有限试验；不连成收敛曲线或外推渐近收缩率。图没有显示物理强度被归一化，只显示以冻结缺陷尺度构造的诊断比值。

## 81769设计与运行前检验

accelerated种子是81679 full的真实输出SHA `a9aaf15de922d5f6e98588c26faab8e6ec95a0c4ef35813aaecdecd3225e332f`，historical为80554 historical24保留输出SHA `c558b84cd3d00ca45855afed9d47303b6452723eebfce2623eb1eb555241266e`。不是从未经真实映射验证的外推预测起跑。两者有共同血缘，不称独立物理样本。

顺序 accelerated8 → historical8 → accelerated16 → historical16；最多32张新map、4个反馈对、0物质步。原七门/物理域/程序/资源故障立即停止。窗口漂移或跨初值差异未过则如实记录，但不截断另一支同龄点。最终需两支16−8四端点组合及16时跨支四端点完整512维残差之差，在L2、质量加权、最差单元三尺度上同时满足：/原r20<0.001与/冻结80195响应信号<0.1；还需四组跨反馈原率/加热门全过。通过只给待独立复核的有限窗口资格，不换基准，不宣布耦合收敛。

PRE-RUN：Code PASS（Mac48passed；学校42passed6skip，仅Mac工件测试跳过）；Logic PASS（两种算子配置只差路径、初值及map预算；trial字节/编码/native/物理时步逐项验证）；Physics WARNING（辐射收益到物质响应稳定的联系尚需实测）。Decision RUN。复用了已验证的原map、正式零位移反馈和停止链，不改冻结物理核。

实施时发现新驱动拷贝中的KiB护栏常数笔误，运行前改回6×1024²；新增临界值测试。补充了历史只能恰好多一张且active_map清空、实际反馈对计数、资格必须要求全部原七门的约束。修复均在6d15f3f之前完成，没有在作业运行中修改冻结代码。原审计第一次JSON序列化遇到numpy bool，改为Python bool；首个篡改测试选到了零slab，改用最大非零原缺陷slab。它们是记录/测试缺陷，不改数值门，失败输出保留。

## 监督、备份与后续入口

平台只读watch：`handoff/audit_tools/watch_x20_accelerated_feedback_windows.py`，输出 `outputs/review-20260925/x20-accelerated-feedback-watch-81769`；每60秒读小JSON及scontrol、新阶段/反馈里程碑调用无工具CLI，终态先保存。启动PID461126仅是启动记录，不代表未来存活。非交互PATH必须含 `/home/scc/pb24511938/opt/node-v22.18.0-linux-x64/bin`。首份CLI回执实际模型deepseek-v4-flash[1m]，无工具、无科学判定权。

Mac备份 `pre-expanded-completion-20260930.bundle` 与automation-before-expanded-completion；学校 `pre-accelerated-feedback-20260930.bundle`。增量包 `accelerated-feedback-20260930.bundle` 已校验并快进合并。GitHub push曾返回引用锁预期旧SHA不符，随后GitHub API确认远端已是6d15f3f；未强推或重置。

依80554实测40maps3pairs共3:10:15，本批先估3—4h，I/O/校验/反馈成本可能改变。这个区间只是本批墙钟粗估，6h是停止上限，均不是全盘I_nu完成时间。结束先保存scontrol终态、日志、status和summary，再下载小archive、清单、SHA回执，独立审核频率归属、每张map、4对反馈及完整向量窗口。中断保留部分态，但此新驱动拒绝重用已有根目录；恢复必须先审计，不盲重交同名run。

accepted_outer_steps仍20（同一物理步内的非线性更新次数），phase1367、dt889.419892762322s和原r20未变。80195与80554原失败结论保留，尚未得到耦合柱、完整局域大气表或可用于整盘观测的I_nu。

10:38启动检查：Slurm仍RUNNING，stderr空，accelerated的native材料/phase/dt精确一致证明已写出。主驱动尚在初始化前的冻结来源校验；继承配置列有23013项来源声明，其中58份不同大态，总声明大小586351094275 bytes。sstat此时读量约425GB、MaxRSS179444KiB，CPU累计7:56，说明正在处理来源校验，不能将尚无map当作worker已运行或已完成。未因此跳过哈希或修改运行中的声明；后续应以实际首张map及反馈时间更新耗时估计。
