# 第19步候选同态确认

76509在16:21:42 COMPLETED/0:0（59:47）。第4张原15/16，仅noise0.1071235708大于0.1；第8张原16门与对76469confirm2的四组合全过，noise0.03920005285、heat1.681014159964e-4。Mac审计3087文件、304反馈与608map进程回执复现结果，支持候选但不接受19。

## 固定物质和路径

基态为已接受$x_{18}$，残差方向$r_{18}$仍取76469 confirm2 final，候选固定$x_{18}+r_{18}/128$。phase1367、物理旧时间层、密度、889.419892762322秒和能量定义不变；新control响应仅作比较，不替换原方向和门分母。新目录`outputs/hpc/common-confirmation19-20260924`，代码`operations/common_confirmation_step19.py/.sbatch`。

1. control从76469confirm2最新mapped后继开始，零位移4map加一对反馈。稳定性五门、内层、正物质域、完整态和资源均过，且76509 pair08对这份新control四组合三范数全收缩才继续。
2. confirm1从76509 endpoints-map08的mapped_final开始，同一候选2map加一对反馈。原16门及新control四组合均过才继续。
3. confirm2从confirm1最新后继开始，物质不变，再2map加一对反馈；执行同样全部门。

任一步失败即停，不临时加map、不改alpha、不缩物理dt；全过也只confirmed_requires_mac_review，仍18/new0，待Mac独立审核才能接受19。三child各自三槽保存两输入及后继，不搬移旧端点。

## 身份和资源

起跑时核76509审计归档及实际源字节、已接受x18、固定r18。两种trial在初始化前写好，encoded/base/residual/direction/alpha及T/H/He/比能解码、native镜像在allocation内校验。新协议移除祖先retained_manifest标签，control明确alpha0，不误标1/128。物理算子与原门不变；trust温度0.5、能量0.25、布居0.05，inner1e-4、boundary1e-3、heat1e-3、noise0.1。不允许clip/floor/nan_to_num/删失败层/后归一化。

cpu_long32CPU、128GiB、16worker、BLAS1、hugepage0，4h上限；最多8map/3pairs/9新dat，入场12STATE_BYTES空闲。每worker原生和/proc小于6GiB，新反馈态累计批墙钟小于900秒。USR1当前batch提交后停；只读watcher记录Slurm终态，代码、协议、配置、环境、来源与回执全部保存。旧dat与旧代码不改不删。

上一批两final残差向量差0.095470724907/0.005729440918/0.036330431719只是有限间隔漂移，不是误差界。最差单元收缩小，不能由本次通过推断整体已经或必将收敛；尚无整盘强度与真实谱线。
