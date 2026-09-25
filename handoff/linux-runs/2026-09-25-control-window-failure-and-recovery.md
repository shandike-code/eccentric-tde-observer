# 77264 协议构造失败：保留8张map并恢复欠下的反馈

## 故障不是物理判决

77264于17:48:24—18:33:11运行44分47秒，FAILED/1:0。
已完成8张map、active_map=None，保留了第7/8张输入及第8张输出三个端点；0对反馈执行，0新物质接受。
异常为`trial-residual acceptance authorization changed`，发生在`fresh.new_protocol`调用未修改的原授权守卫时。
原驱动错误地把禁止接受的zero-control协议当成要求有限试步授权的构造模板，尚未执行到后面的set_authorization。
这是本地新增驱动的契约错误。之前47项测试和小工件预检没有实际覆盖这条协议构造路径，不能以测试全过掩盖漏测。

失败归档`failed-1790332388257895194.tar.gz`已收至Mac并安全解包到
`outputs/review-20260925/step21-control-windows-77264-failed-received`。
审计核1228文件、685代码哈希声明、608map进程回执、8张完整map的非负强度/频率归属/全局与边界重聚合，
最高进程回执3587308KiB，小于6GiB。保留清单的三个SHA与历史最后两张对应关系正确；Mac没有重新读取大dat字节。
证据`handoff/evidence/20260925-control-windows-77264-failure-review.json`及终态JSON；大态全SHA在恢复allocation内再核。

## 修法与恢复边界

旧operations/diagnose_step21_control_windows.py、旧协议、旧失败目录和dat全部保留。
新增`operations/recover_step21_control_windows.py/.sbatch`和独立恢复协议。
采用已审77126 thermal有限模板满足通用构造器契约，先核它与零控制模板的所有原科学门、x20/r20/物理旧层相同；
构造后、写盘/执行前，明确换回control trial并禁止全部物质接受授权。不是打开旧失败控制的授权或去掉guard。
真实构造与native身份预检被移到初始化/新map之前。

新目录`outputs/hpc/step21-control-windows-recovery-20260925`。
用旧map8 mapped_final初始化新的旋转槽，只继承经过审计的8张连续history及小回执；旧旋转槽不作为新写入槽。
声明分别记录原seed与resume_seed，逐文件保留来源SHA。先补做旧pair08；原零控制7门通过后才允许map9–16及pair16。
本次最多8张新map，总实验仍为16张和两对反馈。原窗口尺度/物理门/dt不变，不接受物质步、不替换r20。
32CPU/128GiB、16worker、4小时上限、USR1提前900秒。

新增回归直接复现原授权异常，并验证修正后的最终零控制协议、门/物理身份改变拒绝、错误seed/历史拒绝、
欠反馈先于新map、欠反馈失败禁止新map以及恰好8张续算。Mac相关40 tests通过（1.08秒）。
Linux回归和真实旧端点协议构造预检必须通过后才能提交；提交记录随后补齐。
独立handoff审计器增加`--prior-failed`参数，恢复工件审计必须同时传入失败包解包目录，并核前8张的逐文件继承。
不能把继承的8张说成本次新算。完整新反馈工件的端到端验证仍待实际结果。

PRE-RUN：原构造契约已定位；新协议的零接受授权不变；原8张只读复用，欠反馈优先，剩余预算8张。RUN（先测试与预检）。
POST-RUN：失败工件完整，暂无物理反馈判决；Mac回归无warning/NaN/Inf或掩盖域错误。当前接受步数20。
备份Mac `outputs/review-20260925/pre-control-window-recovery.bundle`；学校`/home/scc/pb24511938/pre-control-window-recovery.bundle`。
