# 五块局部方向的真实全域检验

前提78037两组640组局部门通过、来源/资源/重放metadata审计通过；78038只读原数组扫描、Mac1280行fsum再次核验。school原数组复算不等Mac原算子重解。数值源77577 map10 input/output保持与三块对照相同；两组replacement来自78037，来源及扫描声明/代码/数组SHA前后核验。

新run outputs/hpc/step21-five-block-global-20260927。候选覆盖22..26及46..50共10块，未选INPUT逐位复制原场，half=(x+q)/2在所选块执行，外侧直接复制保护次正规数。不加taper/凸混合/调参；物理x20/r20/旧层/dt/网格/率核不变。

32CPU128GiB、16worker、4h上限，全域仍原76自然块，父与worker回到6GiB守卫。先真实T(q)/T(half)各1map，全部9632组参与。fullL2/原<=0.8（20%成本门），fullLinf/halfL2/halfLinf<=1.0000000001，独立half仿射/原L2<=1e-6，严格辐射<1e-4，边界L1/bol<1e-3且不高于原值*1.0000000001，正性有限。特别保留21/27/45/51外侧响应；不因局部核通过忽略其他块。

任何首阶段门失败2map后停，0反馈。全过才controlmap2/pair02，原七门与正气体能过才controlmaps3..10/pair10。最多11map（10control+1half）、两反馈，0物质接受/0物理时间推进/0r20替换。pair02对77577是初值位移；pair10对pair02八map窗口必须四组合三范数/原r20都<0.001。通过也只待Mac独立审阅，不能称耦合柱或整盘I_nu。若质量门仍不过，停止并定位，不追加同样map或改门。

trial初始化前复制并验证encoded/native身份，源/代码哈希前后验证；USR1当前batch收尾不再派worker，故障保全不重试。每阶段小包归档，不回传.dat。局部GMRES info2不改变，候选是有限修正，不是线性收敛解。备份pre-five-global-validation.bundle。
