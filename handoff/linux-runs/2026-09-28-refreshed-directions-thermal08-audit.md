# 78950：热能方向首轮反馈有可分辨信号，但不能接受

2026-09-28 13:24:48实测78950仍RUNNING，已运行1:53:32；control和thermal各完成8张及正式反馈，population完成6张、正在继续到8张。32CPU、128GiB、16worker及既定48map/6反馈对预算不变。接受计数仍20，没有新的物质接受。

## 独立核验的结果

归档`thermal-map08-feedback-1790571500142230365.tar.gz`，154113037字节，SHA256为`247b4e10210debfc4c0c8771e9ee5f30dc6721be96f1d714f465a69b119a4901`。Mac接收目录`outputs/review-20260925/refreshed-directions-78950-thermal08-received`。完整审计核对4309文件、732代码声明、1216map回执和304反馈回执；原trial、x20、r20、物理旧层和共享辐射seed一致，峰worker为4045056KiB。完整入口返回0，结果及图为`handoff/evidence/20260928-refreshed-directions-thermal08-review.json/png`。

热能方向原16门通过13项，失败的是`candidate_l2_contraction_pass`、`candidate_mass_weighted_contraction_pass`、`candidate_maximum_cell_contraction_pass`。率、加热、原内层噪声及其他门通过，物质响应没有离开正气体热能域。两个热能响应端点的最低比气体热能分别为7.0074630171854e12和7.00050622176967e12 erg/g。

| 三种范数 | 热能/同期控制：四组合范围 | 热能final/原r20 | 控制final/原r20 |
|---|---:|---:|---:|
| L2 | 0.9917185538680364–0.9919677495877983 | 1.002449827263930 | 1.010820885980239 |
| 质量加权 | 0.9922531301989974–0.9926394865456662 | 1.068988239588998 | 1.077334207426094 |
| 最差单元 | 1.0029160879880001–1.0029298825514015 | 1.003178812757541 | 1.000261950714264 |

相对同期控制，前两者分别改善0.803%–0.828%和0.736%–0.775%，最差单元却增加0.292%–0.293%。相对原r20，热能两端点三个范数都大于1，解释了原三项收缩门失败。控制不是有限物质候选，不应给它套上“原16门中三个失败”的判决；它的原七门和窗口门通过。两种基准并列保存，不覆盖旧r20。

方向信号是候选与同期控制的完整128×4残差向量之差。四组合最小信号范数为0.16843041520755306、0.007027350087196368、0.06489845938331815。端点散布/最小信号比为0.041078722077083865、0.045007034852985114、0.040228442490016995，均小于0.1。因此端点可分辨性通过；第8到16张的持续性仍未测得。不能把此结果当严格误差界、精确Jacobian作用或三个范数共同下降。

附加解释只读取已审计残差数组，保存在`handoff/evidence/20260928-refreshed-thermal08-interpretation.json`：控制最差单元为零基索引2，热能为1，两个端点均如此。final最差单元的气体能编码残差平方占比分别88.761%和83.296%，HeIII/HeI编码分量占比分别8.533%和13.373%。它们属于两个不同单元，不能当同一层的前后分量变化；单元编号也不是已核验的物理深度。尚未据此确定微物理原因。

## 审计输出的真实缺陷及修复

第一次完整审计执行完数值断言，在最终`json.dumps(result, allow_nan=False)`失败：`TypeError: Object of type ndarray is not JSON serializable`。有限方向比较中的photoionization和total_recombination来自dataclass，是NumPy数组；此前新control真实E2E及旧三对端点预检没有覆盖整个有限方向报告的JSON写出。

只在`handoff/audit_tools/review_refreshed_directions.py::audit_pair`返回前显式将comparison中的数组转为列表，仍保留`allow_nan=False`，没有修改科学公式、公差或门。两个新的历史真实thermal/population回归完整执行端点审计后写入严格JSON，确认三分量率比较、16项门和152份回执均保留。38项测试通过（2.22s），随后本次thermal归档真实E2E通过。错误日志`refreshed-directions-thermal08-audit.log`、修复前源码`review_refreshed_directions-before-json-fix.py`、回归日志和第二次完整审计日志均保留在`outputs/review-20260925/`。这是Mac审计报告输出缺陷，不是学校物理计算失败，不需重跑学校map。

## 检查与下一步

[PRE-RUN CHECK]

Code: PASS
Logic: PASS
Physics: WARNING

Key Issues:
1. 归档身份、逐块回执、trial及源声明均按新有限方向路径检查；遇报告序列化错误先保全再修复，未更改正在运行的数值依赖。
2. 完整向量差独立math.fsum归约，保留四种组合及原r20/同期控制两种比较；原门核函数明确复用。
3. Mac未重解ODE或全场转移。端点散布不是严格误差界，尚缺16map持续性和布居方向证据。

Decision: RUN

事后：两次执行中的第一次有上述明确traceback；修复后的审计和回归无新warning/traceback。已核工件数组有限、gas正、全部进程回执退出0，资源门通过；父stderr为空不等于所有worker日志都无warning。图已目视，与三个范数的数值一致：热能L2/质量比控制低，但三者对r20仍在1以上。变化有可分辨的数值信号，暂不能推导具体微物理因果或模型无解。

继续原78950的population08以及三组16map反馈，不另交同类任务，不扩预算。拿到16map后核验信号跨窗口持续性，再判断是否有三范数共同下降的混合方向证据；不能现在选择新权重直接起跑。物理dt、原r20和接受20不变。

讲义新增第59节。只读CLI实际模型`deepseek-v4-flash[1m]`；草稿中把控制也说成三个收缩门失败、未注明信号数值为四组合最小值，只列final交叉比等表述，已独立纠正。草稿和提示词保存在`outputs/review-20260925/refreshed-thermal08-lecture-{cli.json,prompt.txt}`。

修改前Git备份为`outputs/review-20260925/pre-refreshed-thermal08-review-20260928.bundle`，数值源码仍冻结于`579be9bd2dad6770ac0f7db63efc8ed00189f01b`。本次提交仅含handoff审计代码/回归/小证据/报告及讲义，大场未下载或删除。
