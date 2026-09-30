# 82214真实输出的配对反馈窗口

2026-09-30；本协议在提交前冻结。82214两张真实map经独立审计，16门全过。full L2缺陷/原A16=0.6334860715517776；这不是耦合物质残差或严格误差界。

## 输入、预算与实现

新目录`outputs/hpc/x20-window-feedback-20260930`，拒绝覆盖。加速分支从82214 full的真实输出T(q)起跑，不使用预测p或输入q；历史分支从81769 historical map16保留的mapped_final起跑，必须逐字节等于82214基底第3号TH16。所有来源由已审归档、终态和SHA绑定，禁止误接旧80554 historical24。

固定x20、physical old、phase1367、dt=889.419892762322 s、原r20。完整trial先复制，再初始化；检查encoded/base/direction/residual/relaxation与native镜像。新入口`operations/x20_window_feedback.py`保留81769已验证的运行和停止逻辑，重新实现来源预检；旧驱动、物理核、旧结果不改。

Students/qos_stu_cpu_long，32CPU、128GiB、16worker，6小时硬限，USR1提前900秒。每支最多16张新map；accelerated8 → historical8 → accelerated16 → historical16；最多32张、4对反馈、零物质更新。累计历史龄不同；“同龄”只指本实验新增map数相同。

## 判定与停止

每个端点先检查连续两态原辐射1e-4门，随后原零位移反馈七门、正气体热能、布居合法性、NaN/Inf、频率完整归属、worker<6GiB及父进程<6GiB。任一程序、资源、原反馈门或物理域失败停止；信号保留半态及归档，不自动重交。

两支各自16−8窗口及同一窗口跨初值，均比较previous/final四个组合的完整512维向量差。L2、质量加权、最差分量分别除以冻结r20和80195冻结响应信号，门分别0.001、0.1。信号尺度复用81769声明，不更新分母，不用标量范数之差代替向量差。另保留四组跨初值率与三种加热的原门。

第8张跨初值只是测量；窗口/跨初值漂移失败仍记失败，但完成预算内另一支配对端点。最终资格要求四对原门都过、两支16−8窗口都过、16时跨初值完整向量差及率/加热门全过。资格只供独立审查；不自动换r20、不接受第21步、不宣称自洽。

`from_prior_feedback`的accelerated参考是81769 accelerated pair16，并不是新T(q)的反馈；historical参考是81769 historical pair16。原失败均保留，有限窗口相合不等于严格初值独立性证明。

## 工件和复核

每轮独立协议、端点SHA、feedback/response NPZ、七门判决、窗口比较、process receipts及不可覆盖归档。大态仅留学校，不下载Mac、不进Git。平台CLI只读监督，Codex独立复核向量、来源、资源和最终门。32张旧同规模批次81769用时约3小时，仅作资源计划参考；当前6小时为上限，不是科学结果交付承诺。
