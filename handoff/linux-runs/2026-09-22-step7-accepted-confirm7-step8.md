# 第七步两倍松弛接受；双确认后条件推进第八步

75185于2026-09-22 09:27:06–10:26:38在anode18完成，COMPLETED/0:0，00:59:32，32CPU/128GiB/16worker，stderr空。run outputs/hpc/step7-amplitude-20260922。零控制2map/1pair，full alpha1/128共8map/2pair，half未起；总10map/3pair，无active/pending。amplitude-probe-decision的formal_finite_step_accepted与fresh_control_corroborated均true，coupled_column_accepted=false。

## 正式接受与失败历史

首pair map3/4为11/16：三种加热、内层辐射、noise门失败。原子加热0.0014091740453402106，noise/signal0.1802687657180313；拒绝历史不改。末pair map7/8全部16门通过；内层残差6.626721387740336e-5 / 5.313404840707381e-5，三种加热约0.00049453282（门0.001），noise/signal0.05214147363040802（门0.1）。fresh control四完整组合三范数均有限[0,1)。

| 范数 | 冻结基态 | 候选末态 | 正式比 |
|---|---:|---:|---:|
| L2 | 14.062104181842878 | 13.620750375720995 | 0.9686139570284394 |
| 质量加权 | 0.5218826983215736 | 0.4993237045239229 | 0.9567738231786517 |
| 最差单元 | 3.353634586583867 | 3.3095987391468804 | 0.9868692171731677 |

本步改善3.14%、4.32%、1.31%，较此前1/256小步单步改善大，但基态不同且第七步尚未同态确认，不能由此宣称总算法效率精确翻倍。两反馈端点均0/128气体域失败；最小剩余气体热能7.993703185504795e12 / 7.980509313304955e12 erg/g。760map报告有限非负，1216过程收据正常且内存门通过；native3502.64453125MiB，/proc4039560KiB。没有新的守恒/网格验证结论。

## Mac复核和备份

最终包archives/amplitude-probe-finished-1790043981044998983.tar.gz，140780352 bytes，SHA256 e7c874d724fbe8d1d5e8fd784022130fee46acca85668beaa553246882b7b430。Mac outputs/review-20260921/75185-final.tar.gz和75185-final-received。整包及3136文件size/SHA通过；原审阅器逐pair验证encoded位移/新分母/原physical旧层、连续端点、76块partial及NPZ归属，从存储向量重算三范数吻合。末组额外核fresh四组合键及有限性、control/full native身份。两张图已目视，首组图的完整history/resources来自最终包，不是首组时刻资源快照。Mac不重求物质响应。

证据handoff/evidence/20260922-75185-{accepted,round1}.json/png、terminal.json。事前pre-step7-confirmation.bundle与automation-before-step7-confirmation.toml在outputs/review-20260921。原代码/结果及dat不改不删。

## 新批合同

operations/confirm7_then_step8.py/.sbatch从75185的full8map/2pair实际接受源配置index7；准备函数静态保留numbered_confirmation_step的源重放/血缘守卫，仅把原1/256条件替为显式ACCEPTED_ALPHA=1/128并额外核encoded displacement，声明记录accepted_alpha且恢复核对。没有运行时字符串生成/替换代码，旧模块文件不改。实际归档base/trial经过新身份检查；新入口及相关95项合成/控制流回归在Mac通过，学校复测后提交。

同allocation执行两阶段：A，旧第七步base零控制2图，第七步已接受物质态追加2图、再追加2图，总6map/3pair；保留第七步原正式分母，实际源响应位级重放、9派生门、seed/输入SHA。两确认全16门及fresh四组合三范数均通过才写transition并进入B。B，从确认4实际trial作为新base，以实际原响应R作为冻结方向，index8，新零控制2图/1pair，full1/128最多8图/2pair，未接受则half1/256最多8图/2pair。总预算24map/8pair、最多一个新增接受步，32CPU128GiB16worker，6小时硬限。约2–3小时仅本批规划；不推算最终大气日期。

原budget含completed+active/pending；pending反馈/账本先结算，USR1边界停止，故障优先与根单锁复用。确认失败即停在confirmation_not_passed；源失败/程序资源错误停止，不盲重提；ledger欠账只恢复账本。最终若第八步正式接受仍须fresh支持及Mac审阅，不自动第九步。phase1367、dt889.419892762322s、物理旧层/密度/能量定义/原16门保持，不裁剪/加floor。七个有限接受步只有前六个已完成双同态确认，代表柱和整盘I_nu仍未完成。

学校同组95项测试通过（19.82s）后提交作业75274，run outputs/hpc/confirm7-then-step8-20260922；数值代码3ec70b2efc8085d05cc499d2550ef05dcf2745a3。只读终态watcher输出outputs/review-20260922/scheduler-75274，最长8小时，不续交不取消。新run已冻结后不再改数值模块。后续跟进先看confirmation/source-gate-replay、各child initialized_identity，再看确认all16与fresh四组合；通过后同allocation条件进入next-step。
