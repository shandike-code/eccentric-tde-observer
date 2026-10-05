# 85856新边界约束方向：原11门全场筛查

本协议仅决定一次有限筛查，不把小QP通过自动升级为全场正性或真实映射资格。85856已真实COMPLETED0:0并独立归并301片全部Gram、八场边界谱与极值。四对为85821H16、85821H8、84026H16、82989H16的previous→final；H16取iteration15，H8取iteration7，不取final→mapped_final。字段顺序、原归档源清单和几何链均固定。85821已验证真实终态/1216map/304feedback；84026终态未知仍false/null。

固定同一x20、物理旧层/base/r20、phase1367/dt889.419892762322。新联合小问题使用同四对dt*净原子加热/rho质量Gram与辐射Gram，各自按锚点缺陷平方无量纲化后等权。没有拟合保存A或借用旧83075符号约束。纯cap方向full边界失败，原证书保留，不运行该方向。

本次只筛查带边界约束的全局系数[-6.619870493208708,-0.5801295067912914,0.06364926467589747]，是原精确解统一乘0.9再存binary64。full直接使用这组三系数，half按原核0.5*锚点+0.5*full构造，不能再把full误除2。小边界约束保留可变分母，锚点最大通量分支内raw精确KKT通过，新增L1支持平面0；actual binary64 full/half小边界复核通过，但不是全场非负证书。小辐射/加热比full 0.43799316541672384/0.08338477598222536、half 0.689145484426514/0.5335825034022765，均不是正式反馈门或物质残差。

新目录outputs/hpc/x20-85856-boundary-prediction-20261006，复用不修改的operations.x20_window_fields.measure_candidates，一次9632×32×4096的301片扫描。原11门不变：full L2比≤0.8，half L2非增，full/half Linf非增，full/half内部辐射残差<1e-4，full/half边界L1及总通量相对变化<1e-3且相对锚点非增，以及四候选场全场非负。原非增舍入容限1.0000000001不变。所有负点，包括次正规值，保留在分片最小值统计；若非负失败，其余门保持未求值，不能冒充通过。非有限场报错停止。

4CPU16GiB/1h硬限，USR1提前120s，父RSS<6GiB。0map/反馈/物质，不写dat、无自动缩步/恢复/续交。入口从学校实际小来源重建两Gram并独立验证证书，不重求QP。原物理旧层用live_path映射学校旧文件并核原SHA；所有来源/代码/八场SHA前后检查，源码包括实际加载的handoff辅助模块。新记录八场inode/size/mtime前后清单和clean/HEAD前后证据。

提交前需要两端clean/exactHEAD、完整bundle备份与ff-only同步，接口读审、两端测试、学校小来源重建与证书验证、shell/diff检查均通过。学校运行中冻结数值HEAD。batch-exit只证明Python子进程退出，watch先保存真实scheduler-terminal再调用无工具CLI；实际modelUsage须核。child退出三轮仍无调度证据则保留UNKNOWN，不造COMPLETED。

终态没有自动归档；先取declaration/prediction/summary/status/batch-exit/scheduler-terminal/execution-terminal/stdout/stderr九小文件清单，核逐文件与整包大小SHA，0dat。Mac新审阅器须绑定本次job/数值commit、新八场及系数，80位归并301片全部统计/原11门，并核来源、代码git show、资源、字段身份和clean。失败定位后单独决定，不自动缩步。全部原11门通过并独立审閱后，才另行决定原16门full/half真实映射最多2map；预测p不是T(q)，不能自动接受21或宣称整盘I_nu完成。
