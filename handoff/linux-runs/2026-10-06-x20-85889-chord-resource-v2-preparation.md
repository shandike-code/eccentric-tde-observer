# 85889 六场全SHA资源预检 v2：准备审阅

本阶段补齐v1缺失的全场认证路径，保留全部旧协议和实现。准备阶段尚无新JobId或真实dat读取；旧85889预算关闭，accepted20、0新map/feedback/ODE/material、baseline_replaced=false、reference_calibration_eligible=false、strict_error_bound=false。

新增v2驱动、30分钟sbatch、40分钟只读终态观察器、当前native依赖核验器和独立生产小工件审阅入口。正常逻辑场payload读量121601261568B，归档前后607755804B；这不是物理磁盘I/O或缓存命中计量。全场前SHA在独立Slurm作业内、单片计算之前核；并未冒称已在提交之前刷新六场SHA。后续完整301片扫描仍需独立决定。

两端最终合成测试：Mac133项1.09s，学校122项4.32s；学校少11项旧来源审计测试，未混称两端全套相同。合成33×2×3，每端真实读取37440B，所有单片Gram、四组合直接矩、误差摘要、片SHA及全场SHA一致。Mac小例峰值44056576B，学校40894464B；不是生产资源证明。21个隔离代码/测试/sbatch文件与Mac大小SHA一致。

学校当前native实际两次只读审阅总19.44605639099609s、RSS309293056B：801份当前原代码与9555a78声明一致，6个runtime数据来源重新核验；两个镜像物质trial全数组dtype/shape/bytes、相位、物理dt及频组/角度/深度/76块所有权通过。Python审计hook在native配置期间拒绝任何dat打开。归档两次读取607755804B，均复现原SHA f20c313bc92af5730a16d7a9c604793873719bd710b53d0fc763813349cd120c；这里只核压缩包字节，没有重新执行旧8588成员完整科学审计。学校9555a78工作树仍clean。

真实E2E保留的失败：首次学校测试命令目录上溯多一级，未执行测试；首次live runner引用不存在的actual-binding.json，未执行native。随后三次前置检查分别捕获：固定模板不在顶层declaration（原声明实际在已认证config.sources）、旧模板子来源只有SHA没有size（从同源config补齐大小并核已有字段一致）、环境NumPy direct_url元数据被误作科学数据来源。现按原声明闭合，不生成新SHA代替旧SHA；虚拟环境元数据只记录大小SHA或不存在，并与科学输入分开。最后两次真实live结果除首次import元数据观察清单外一致，无真实dat打开；原失败日志未删。

学校CLI只读文本审阅74.636s，实际deepseek-v4-flash[1m]。其主要阻断意见因未提供helper上下文而错误：hash_pass已核预期SHA、live_check已核归档、binder已有PINS、stat含dev/inode/ctime等、sbatch与allocation已验证线程、1500秒停止至1800秒硬限仍有300秒清理时间。逐项纠正在配套lecture-review JSON中。采纳并实现单节点实际分配核，以及独立review_run只接受完整生命周期、外部来源绑定、阶段结果一致、当前native/归档证明和实际Slurm COMPLETED0:0；失败或部分目录拒绝。没有放宽科学门。

[PRE-RUN CHECK]

Code: PASS
Logic: PASS
Physics: WARNING

Key Issues:
1. 接口/负路径/两端合成E2E及真实native/归档依赖核已过，源码仍须冻结并以verify/fetch/ff-only同步学校；具体作业提交前复核exact HEAD/clean。
2. 只考虑一次4CPU16GiB、单节点、单进程、线程1、30分钟/程序1500秒/RSS小于6GiB的全SHA加首32组资源测量；六前SHA不符立即停止，禁止改片/重交/恢复。
3. 尚无生产单片资源或全场Gram，单片数值一致性不证明物理收敛；原两支窗口通过/跨16响应失败保持。

Decision: RUN（仅在源码同步及具体提交检查闭合后的一次独立资源预检；完整301片DO NOT RUN）

[POST-RUN CHECK]

目前完成的是合成与依赖审阅：无NaN/Inf/发散或容差放宽，极小数规则沿原实现；无新图。native只证明当前输入配置身份，不执行映射；全SHA与真实首片仍未运行，不能把准备阶段标记production_preflight_complete。
