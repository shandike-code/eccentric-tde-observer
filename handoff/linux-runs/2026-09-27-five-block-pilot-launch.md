# 五块联合核心试验78037已启动

78037于2026-09-27 05:44:36提交并进入RUNNING/anode02。32CPU128GiB、Students/qos_stu_cpu_long、2h硬限，2个局部worker，各24GiB/3600s守卫；原成本门仍24倍本组rawmap。数值源码f2a16d6，run outputs/hpc/step21-five-block-pilot-20260927，协议step21-five-block-pilot-v1.md。Mac24tests0.87s、Linux同组24tests20.17s通过，py_compile/sbatch语法通过。

固定77577源、x20/r20/旧时间层/物理dt不变，只把核心从23..25、47..49扩至22..26、46..50。新增原map逐位重放门，未过不进该组Krylov。最多16GMRES、4次非Krylov局部映射、独立半步真实检验；保存两local NPZ，0全频map/0反馈/0新接受。扩大范围不能保证物质热漂移改善，外侧21/27/45/51仍可能放大。

PRE-RUN：新入口复用旧核且不改旧源码；索引/五块算子/逐位重放拒绝路径24项测试通过。输入trial/native身份、哈希前后在allocation中核查。内存由三块9.1GiB按5/3估计15.2GiB但存在halo和临时数组不确定性，因此采用独立新24GiB守卫，非修改旧协议。量纲、物理时间、正性规则不变。Decision RUN。

备份Mac outputs/review-20260925/pre-five-block-pilot.bundle、学校/home/scc/pb24511938/pre-five-block-pilot.bundle。启动回执handoff/evidence/20260927-five-block-78037-launch.json。

学校只读监督tmux step21-five-block-78037，watch_five_block_pilot.py --mode joint-block-pilot，输出outputs/review-20260925/five-block-watch-78037，3h观察上限；CLI无工具无提交权限，实际后端模型以回执为准。失败不重交，科学决定与独立审计由Mac负责。运行中冻结operations/src/scripts/hpc/diagnostics与声明测试/协议，仅新增文档和审计元数据。

下次查看replay、两个结果JSON/资源回执、stderr、status、终态小包，记录GMRES info与linear_audit标志，不把允许未收敛的方向叫线性解。局部NPZ每份约1.25GiB只留学校；独立审计优先小工件，确需数组时先设计有界分片/统计交叉，不自动把大场搬回Mac。局部成功仍需另行预注册全域真实映射、热反馈成本判断；不得自动进入全域或第21物质接受。
