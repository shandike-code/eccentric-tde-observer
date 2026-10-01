# 83104完整Gram审阅与新的约束方向

83104在Oct1 23:43:40–23:53:31完成，COMPLETED0:0，4CPU16GiB、anode02/default，程序587.960901914秒、RSS966549504字节、stderr空；数值79b2118c6501708d0d6efcfbef7e7b8cfcaec4e0。小包83104-constrained-basis-review.tar.gz为555537字节，SHA256=e471fc6a459d96fc73a4fef575274cba5c3a9eb7c1d421bcf6670287c093d7c8。

Mac首次独立E2E通过：7文件逐项SHA/大小、789源码git show、来源、原8场previous→final血缘、301片80位全部16项归并、八场边界谱与极值、资源及0map/feedback/material声明。证据20261002-x20-constrained-basis-83104-review.json。Mac未重读大场。

完整Gram在t=0、.125、.25复现83080平方L2，实测相对差分别0、9.108340995353701e-15、-1.6244680547835596e-14。不同浮点表达式没有强行要求逐位相等，也没有把三点差叫作严格误差界。无约束纯辐射Gram最优L2比0.32374889，但其仿射权重绝对值和80.4538远超17，不能直接采用。Hessian条件数诊断约26092.7，所有方向保留，无截断/正则化。

## 新小问题及证据边界

预先明确改用两种锚点归一化平方缺陷等权目标：辐射数组L2与加热质量L2各除自身锚点平方，目标无量纲。它没有把有单位的强度和erg/g直接相加，没有把保存A当拟合终点。三方向仍为82989H8、82518H16、82273H16相对82989H16；物质x20、物理旧层、dt和r20均不变。

83075四类负点给出9种不同源四元组，精确正比例归一化后新增7条不同线性必要非负约束；与cap17的14面共21面。去重四元组不等于独立坐标总数，原full/half坐标重叠关系不变。未检查零点/其它片的精确约束，不能称全场证书。

精确有理活跃面枚举在第160组找到解；独立检查行列式、可行性、非负乘子、互补条件及梯度平衡。原系数[-5.746052585476224,-2.2539474145237763,1]，活跃约束为cap与已知点非负。取统一0.9安全因子后实际binary64系数[-5.171447326928601,-2.028552673071399,0.9]；再用有理数验证这些已舍入系数满足全部已知约束。预测辐射L2比0.5401123518430703、加热质量缺陷比0.40479055616108056。记录全部精确Gram/约束/系数/乘子/来源SHA于20261002-x20-83104-constrained-candidate.json。

## 执行决定及检查

新名x20-83104-constrained-prediction-20261002，只提交一次4CPU16GiB/default/1h完整301片原11门full/half筛查，0map/反馈/物质，不写dat；原83063与83080拒绝保留。运行前重建源小问题并核KKT，运行前后核所有源码、来源、大场SHA及inode/size/mtime，RSS<6GiB。失败不自动缩步；通过仍须独立归并后再新名32核真实full/half最多2map，不将预测p当T(q)。

[PRE-RUN CHECK]
Code PASS：源码与来源、4x4形状、非有限拒绝、精确KKT、已舍入系数可行性、防错测试通过。Logic PASS：等权无量纲目标只选择方向，原11门不变。Physics WARNING：数组缺陷、加热质量缺陷和真实物质反馈为不同量；局部非负约束仅必要条件。Key Issues：全场未检；不覆盖真解误差；不接物质更新。Decision RUN一次有限筛查。

[POST-RUN CHECK]
83104无stderr/NaN/Inf，矩阵未修补，和原实测量级一致；新小问题精确证书通过，20 tests passed / 1.02秒，shell语法通过。不是自洽大气或整盘I_nu。学校测试和作业号由后续启动回执补充。

## 启动记录

数值提交a51dce6c3ab3c7cc508d7b2846a099f3b95d9ed2。学校20 tests passed / 14.57秒，另实际读取学校小产物重建Gram/约束、核验系数通过；shell语法通过。备份Mac pre-83104-review-20261002.bundle、学校pre-83104-constrained-code-20261002.bundle，增量83104-constrained-code-20261002.bundle，verify+fetch+ff-only，clean/exactHEAD后提交。

83111于Oct2 00:11:57开始，anode02、Students/qos_stu_default、4CPU16GiB，硬限01:11:57。启动快照20261002-x20-83111-submit.json为RUNNING/preflight。watch PID33414仅启动凭据，目录outputs/review-20260925/x20-83104-prediction-watch-83111，latest已落盘；PYTHONPATH、Node PATH及start_new_session配齐。终态先存scheduler-terminal，再无工具CLI监督。讲义127与CLI原稿、独立审阅保留；实际模型deepseek-v4-flash[1m]。本记录不修改数值依赖。
