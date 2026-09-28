# 79296局部收益通过元数据审计，进入原数组复核

79296于19:03:34–19:26:46运行，COMPLETED0:0，墙钟23:12，anode18/32CPU128GiB，两个局部worker。作业记录已被squeue清理；终态来自学校只读watch持久化的scheduler-terminal.json，不把Invalid job id当失败。父、两个worker的stderr均空。

完整小包complete-1790594806309787304.tar.gz，99636bytes，SHA256 `ac5a216be7b8fb908e7d34d3591eb63fd4ff69f96507da786c36fc3e0e717831`。Mac接收late-population-79296-received。13文件、736源码声明核验，实际源79151 population的trial/config/state、最后map输入输出和连续历史、核心选择、独立半步回执、原九门与过程RSS通过。图已目视。此次没有下载两份1.879GB的local NPZ，没有在Mac独立重算大数组或转移算子。

| 核心 | 实际L2比 | 实际Linf比 | 半步仿射误差/raw L2 | 局部墙钟 | worker峰MiB |
|---|---:|---:|---:|---:|---:|
| 34–40 | 0.0163661204 | 0.0597530161 | 3.77976659e-9 | 1275.48s | 20729.38 |
| 41–47 | 0.0843063766 | 0.2305517824 | 4.42137738e-9 | 1247.81s | 20445.14 |

两组原map重放逐位一致；候选与mapped最低值均正，边界绝对变化下降，时间成本低于24次自身原map，进程资源回执通过。全步非负系数与线搜索fraction均1，因此报告的预测误差0本身只是端点重合，独立half误差才提供额外仿射检验。

两个GMRES均16迭代、info2、linear_audit_passed=false。未达到线性求解器自身收敛标准，但产出的有限方向在实际局部原算子下满足预声明收益；两种判决不冲突。局部halo固定，不能据此宣称全域Linf、加热稳定性、物质收缩或整盘I_nu通过。原20次接受和全部历史失败保持。

新审计入口handoff/audit_tools/review_late_population_metadata.py，证据20260928-late-population-metadata-review.json/png和20260928-late-population-79296-terminal.json。账本核心选择以独立fsum重算，保持37/44；旧数值脚本和协议没有修改。

下一步按原协议用默认4CPU16GiB、30分钟、8GiB峰值守卫，直接扫描全部1792频率×32角×4096深度的已存数组。新入口operations/scan_late_population_arrays.py/.sbatch，新目录step21-late-population-array-audit-20260928。前后完整SHA，float64作差/longdouble逐频平方和，Mac另用fsum归约；不重解half或真实算子，不写新大场。测试/学校作业与终态另记。

扫描通过后才能另行声明全域full/half实际映射；必须保持本次population trial，不能借旧control工厂悄悄替回x20或0.0625。全域及后续方向持续性还需要当前可信control，局部收益不自动构成P−C信号的稳定性。若扫描失败，保留证据并区分归约/身份/实现问题，不改容差过门。

备份pre-population-pilot-review-20260928.bundle、automation-before-population-pilot-review-20260928.toml。保存原数组在学校，Mac仅接收小统计；本轮未删除任何检查点。
