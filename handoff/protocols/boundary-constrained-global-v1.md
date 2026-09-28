# 80005约束候选的真实全域检验

前置：79878拒绝保持；80005两遍数组扫描和Mac独立Gram、系数、全频统计审计通过。固定系数a=0.4892755093069306、b=1，由80005已冻结约束最小化给出，不根据新映射结果调参。

候选z=x+a(q−x)+b(u−q)。x/T(x)为原79151，q/T(q)为79631，u/T(u)为79878。物质始终同一population候选，原r20布居投影1/256。候选在34–47块取x与q的凸组合，在20–33块取x与u的凸组合；其它输入逐位保持x。检查完整支持区，禁止对错误来源静默外推。

本次half明确定义为(x+z)/2。这是新的数值构造和新的实际map实验，不重解释79878的(q+u)/2半步。旧协议、结果和失败均不改。

先实际full/half各一张9632×32×4096、76块完整map。对原x核原11门：full L2比≤0.8，full/half Linf非增、half L2非增，真实half仿射误差/raw x L2≤1e-6，两态radiation<1e-4，边界L1及bolometric<1e-3且相对原x非增。相对q另核相同的10个收益/边界门，不虚构q-midpoint仿射门。非增裕量仍1.0000000001，合计21门全过才续反馈。

必须完整扫描所有频率，包括未修改区域和邻块；实际预测不符应作为证据记录。预测D(z)=0不是保证真实D(z)=0，也不是物理能量闭合。任何实际门失败归档后停止，不再改a/b或重跑。

通过后顺序control2→population2→control10→population10；总预算21map（population10、control10、half1）、4反馈对。沿用原79151 control自身物质及数值种子；两支辐射初值历史不同。control原七门、窗口/累计完整向量三范数漂移/r20<1e-3；population完整512维S=P−C端点散布<0.1，第10张相对第2张跨8map信号漂移<0.1。首次相对79151跳变只作修正记录。原16物质门/正气体热能完整保留；原收缩失败可作为有界诊断延续，不自动接受。响应越界、control或信号失败即停。

申请32CPU128GiB cpu_long，16单线程worker，6小时硬限，父峰6GiB及既有worker守卫。run为outputs/hpc/step21-boundary-constrained-global-20260928；入口operations/validate_boundary_constrained_global.py/.sbatch，候选/门模块boundary_constrained_global_fields.py。USR1停止继续派发并归档，不盲续交。

全过程逐位核trial/原x20/r20/physical_old/rho/phase1367/dt889.419892762322秒，输入和代码完整SHA前后核验。不会自动接受第21物质步，不生成最终大气表或观测谱。大数组留学校，只回传小归档；通过后仍须独立复核和同态确认。
