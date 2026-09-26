# 固定物质20的当前加热主导块：两例局部Krylov试验 v1

前提：77577完整审计通过，八map漂移仍有L2/质量范数失败。热代理全局三历史仿射组合的
无约束最优仅比最新端点改善9.17%，不足原20%成本门，因此不做新全场历史组合。
当前pair10 final减pair02 previous的逐块Q变化，乘同一旧固定dt/rho/u_ref后，
质量范数最大两块为24、48；选择规则和数值冻结在
`handoff/evidence/20260926-heating-subspace-and-block-ranking.json`。

源：77577 control map10的真实input/output，分别来自保留manifest final/mapped_final。
完整10map血缘与SHA、原x20/r20/物理旧层/编码/密度/物理时间不变，输入/输出完整SHA在allocation核验。
只研究这一个固定物质状态、两个块，不把源trial改为feedback target，不初始化新全局流水线。

## 算子和预算

`pilot_step21_heating_blocks.py`复用已验证的`paired_block_krylov`原正性线搜索与原图重放检查；
局部worker保留相同mixed-frame ALE频率/角度/移动深度网格、旧时间层、速度、吸收/发射/散射、
`hybrid_step_turning_upwind`与`source_map_only=True`。先真实重放局部原map，
误差/场<=1e-12且/原缺陷<=1e-6才生成方向，不能凭函数名当作算子一致。

混合系源残差校正的GMRES restart8、最多2轮（16次）、rtol1e-5，允许未收敛方向返回但原样记录，
不宣称GMRES收敛。每例最多3次原局部map：重放、非负端点、选步后真实候选。
正性通过沿原方向求可行步长处理，不裁剪任何强度；线搜索零步保留为失败，不重启或加深。

两worker、默认4CPU/16GiB、整批2小时（来源SHA计入）；每个worker硬限30分钟。
每进程RSS<6GiB，BLAS单线程、hugepage0；独立/proc记录由native_worker_relay保存。
USR1/TERM令父进程停止并终止整组局部worker，15秒后未退出则kill，保留失败归档，不自动重提。

局部通过需：原尺度下L2和Linf缺陷均至少减半，正性/非零步、预测误差/原L2<=1e-6、
局部边界变化不增、GMRES迭代<=16、RSS<6GiB、成本<=20倍初次局部map。
所有项都保留，不能挑最好看的指标。两例局部candidate和mapped_candidate写新NPZ保存SHA，
不写9.41GiB全局候选、不跑全频map、不做正式反馈、不接受物质步。

## 科学边界和历史教训

旧74235在更早物质上block14/47曾通过；74454完整拼接却在相邻频率边缘增加最大缺陷。
7B9w/x在block62加深/重启未获益；7B9u的block73真实正性失败不可用floor或删尾绕开。
因此本次更换为当前x20和24/48是按新热变化定位，不沿用旧成功结论或旧方向，也不立即扩大76块。

局部问题固定块外频率halo，校正的halo扰动为零，不能代表全频耦合算子的逆。
局部残差减半不等热代理减半，更不等耦合大气收敛。若两例通过，再单独登记全场正性/块缝/
真实原算子与反馈验证；任一失败先审原方向、正性、重放和资源，不盲目多迭代。
所有输出均保留接受物质步20、0新map/0新反馈/0新物质接受。
