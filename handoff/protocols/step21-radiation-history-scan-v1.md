# 第21步：固定物质辐射慢模只读可行性诊断 v1

76931的24张map/6对反馈已独立复算，两个方向均未接受。原噪声门的分母混有基态漂移；候选与新control的共同漂移又大幅抵消，因此既不能仅凭原门通过宣称可靠Jacobian，也不能把两份漂移范数和当作差分的实际误差。有限混合筛查的最小最大预测比仅0.9998143，裕量约0.019%，不支持直接接受或盲目批量试物质权重。

本任务只读76931三个case各自的最后连续三态：`endpoints-map08/{previous,final,mapped_final}.dat`，即$a,b,c$，已记录$b=T(a),c=T(b)$。三份trial不变，物理旧层、原r20、物理dt和全部反馈门不变。核独立归档、state/config/trial/retained manifest及实际大态SHA。源必须八张完整、无active_map，不混case，不换种子。

复用历史 `phase7b9bx_slow_mode_anderson.py` 的代数：一个全局系数$s$给出候选$b+(s-1)(b-a)$与预测映射$c+(s-1)(c-b)$。只计算Gram、差分可辨度、全场正性上界和边界量，不写候选、不调用新映射、不评估新物质响应。系数范围[1,96]，由所有单元非负性限制；不做逐单元clip/floor。代数门是下一步真实映射验证的入场筛查，不能代替原物理门。历史2026-09-19仿射验证曾成功，但不把旧结果外推为当前状态已通过。

为了默认4CPU/16GiB下有界内存，用普通文件只读频率slab代替长期驻留memmap，仅替换本诊断进程的读入适配器，保留旧代数运算顺序，结束后恢复函数。小数组测试须逐项与旧memmap代数相同；native峰RSS小于6GiB。每case扫描chunk16、指标chunk128，读前后核大态SHA；全部三个case只读扫描，最长30分钟。SIGUSR1/TERM停止并保留失败小工件，不写任何强度态。

输出 `outputs/hpc/step21-radiation-history-scan-20260925/{declaration,prediction,status}.json`及小归档；三个case均保留预测和实际旧残差。状态`complete_requires_review`不表示新解。map预算0、候选写入预算0、接受20/new0。若可行，必须另声明新目录中的真实映射及完整反馈验证；如果不可行，不改门、不自动增加map。
