# 86304当前辐射端点来源与证据缺口（2026-10-07）

## 结论与范围

本次小JSON核验将86304当前六个辐射端点明确绑定到已审映射链。每支从85889的mapped_final启动；新P→F是第7张映射，新F→M是第8张。正式pair08反馈使用P/F，未对M做本轮物质响应，也没有T(M)。本次没有读取或stat真实dat，没有刷新六场SHA，没有新Slurm、map、反馈、ODE或物质步；不是完整86304审阅重跑。

实际校验323份JSON读取记录，包括两份固定SHA清单、两份原终态审计、端点/配置/状态/反馈协议、声明/种子/summary及304张第7/8张频块回执。每个指定JSON先核大小SHA，再解析，结束前复核。304回执的每次映射9632核心组连续、无重无漏，输入SHA及配置SHA分别绑定该历史行和state。trial只核清单及state指向同一已审SHA，未重新加载数组；原全数组及native验证来自原最终审阅，不冒称本次复算。

## 当前对象

各场10099884032字节，配置shape为9632×32×4096。下列SHA为已认证小manifest中的声明，本轮没有重新读取大场核SHA。

|支|端点|SHA256|
|---|---|---|
|accelerated|previous|`a934ab2420789bdd11642507ecdea73c7912e7df6cc9a4701ca7fdadc99e3bdc`|
|accelerated|final|`bc12757f0601fa901f04e6672088d5c7b865283781fd1debe611dee735ef69b8`|
|accelerated|mapped_final|`b1477a001886ed9a408e6e01baab4c4d2f1154a73a04d81d5a98bd1773991f72`|
|historical|previous|`d75e2bff1afaab2f069d89749d391b73ec8de5cd4be0d5c171cef03efd4b75e7`|
|historical|final|`ae93ac67bdd73469636ddc5e66ae40792e2ee81f976d56f3e5562cd3d3ac2245`|
|historical|mapped_final|`2c1ebffb2e13f170dc0dafdfaf379dfd21760b77c2fbe4c9b87dcbc4e2cacf6d`|

路径为 `outputs/hpc/x20-85889-relaxed-feedback-20261007/{branch}/endpoints-map08/{endpoint}.dat`。旧85889的A/H mapped_final分别以3f6c898f…与6e10ec89…开头，完整声明见小审计；它们等于新seed-claims、declaration.seeds、config.warm_seed，且等于新history首张输入SHA。它们不是新P/F/M，也不是旧F。

两支新配置仅run/warm_seed/sources不同。各支旧新配置除这三项外只有maximum_maps由16改8；这里记录配置比较，不把来源清单变化忽略成源码全同。另核当前retain_pair、retained_pair、relaxed driver三文件与fbfe81fb原提交逐字节同。旧/新trial SHA相同只是既有数组审计的来源绑定。

## 已有量与缺失量

第7/8张原归一化辐射residual：A为1.836419190016832e-7 / 1.8285791605181406e-7；H为9.032781639585246e-7 / 8.994307432793613e-7。原pipeline聚合为所有块最大absolute change除所有块最大radiation scale；不是L2缺陷、物质r20或未知固定点距离。

4304条归档工件记录中没有以gram/chord/basis命名的条目。文件名排查本身不能证明数学缺失；关键是实际304块回执schema只保存最大变化、强度尺度、边界积分、极值和执行信息，反馈保存频率积分后的物质量，均丢失完整频率×角度×深度的联合方向信息。它们不能一般地确定跨支差与各自真实缺陷的全场交叉内积。8响应方向诊断发生在512维编码物质空间，也不能补出辐射内积。

旧86290只统计85889六场首32频组；新六SHA均为86304对象，不能把旧首片统计/资源验收移植成新数值结果，也不能把首片当全301片。

## 下一项可检验问题

对新P/F的四组合，定义d=H−A、rA=T(A)−A、rH=T(H)−H、e=rH−rA、dprime=T(H)−T(A)。问题是：本次实际有限映射是否使四组合的无权全网格差范数均下降，缺陷差对d的有符号投影是多少？每组合分别报告比值及方向，不预设通过。这不需要T(H−A)或T(M)。若比值小于1，只是这四次有限比较的事实；不是持续收缩、谱半径、严格误差界、真解或ETA。

另立 `handoff/protocols/x20-86304-radiation-source-validation-v1.md` 限定下一准备阶段。先实现新身份绑定与独立负路径验证，再提出当次具体资源预算和独立生产协议；本文件不给予dat读取或新Job预算。旧所有预算关闭，全301片DO NOT RUN，不追加8/16map，不再放宽或接受21。

## POST-RUN CHECK

Code PASS：标准库JSON核验通过、指定源前后SHA同，未导入生产数值模块。Logic PASS：旧M→新种子→连续8张→P/F/M→正式反馈来源闭合。Physics WARNING：仅源关系与量定义核查，无新全场统计或物理演化。原十倍探索质量门失败、accepted20/newmaterial0、校准/基线/严格误差界false保持。

未修改生产代码，无需重复36项方向tests或65项生产tests。两端完整pre-86304-radiation-sources-20261007.bundle已verify；学校fbfe81fb clean未同步。完整逐项证据和一次性脚本保存在outputs/review-20260925/20261007-86304-radiation-source-check.{json,py,log}，小索引见handoff/evidence/20261007-86304-radiation-sources-review.json。

学校CLI10.9826秒、实际deepseek-v4-flash[1m]仅依据短事实起草。草稿误把辐射端点定义为交叉内积、把物质响应混为T输出并把待测比值说成已知，均独立纠正；原稿和review保存，讲义172追加旧前缀不变。
