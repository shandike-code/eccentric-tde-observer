# 78950：首轮控制反馈独立审计

12:38巡检，78950 RUNNING约1:07，control08已完成并过原七门；thermal在第5张map进行中。未改数值源码、配置、协议或运行预算，未重交。12:45复查thermal已完成7张、目标8张，父stderr仍为0字节。该次状态是正常推进，不需要用户操作。

控制归档control-map08-feedback-1790568991694893723.tar.gz，78227150字节，SHA256为ba27485f97daa1c32269675e82369cc7685eb782ff9b0228b683c98a7a162a00。Mac接收目录outputs/review-20260925/refreshed-directions-78950-control08-received。

新增独立审计handoff/audit_tools/review_refreshed_directions.py和test_refreshed_direction_review.py。审计按control/thermal/population三个child分别检查最多16张map、从同一seed开始的链、76个块的9632组唯一所有权、trial/base/r20、资源回执、逐块反馈聚合、旧物理层能量账本、codec响应及原7/16门。四组合方向信号、相对信号的端点散布、16种跨窗口信号差和同期收缩比均使用独立math.fsum范数，不调用生产response_measurement。

验证顺序：36项解析/反例测试通过（0.96s）；用旧77126真实完整包分别跑control、thermal、population三对的端点审计，各152回执。准确再现control7门通过、thermal质量/最大单元两门失败、population L2/质量两门失败，未把历史失败改成通过。随后78950控制首包真实E2E通过：2157文件、732代码声明、608map回执、152反馈回执；峰4045056KiB，约3.858GiB。

控制八map漂移四组合最坏的L2、质量、最大单元比为0.00012737689057375253、0.000490227101058053、0.00007949929277480606，均低于0.001。它们是完整残差向量差除以原r20范数。当前final残差本身的三个范数为8.260434909081946、0.2821650552621457、2.705709693586407；不能将窗口比解释为物质自洽残差。两个响应端点最低比气体热能7.023742423521707e12 erg/g，正物理域通过。

审计图已目视：当前只含control08，横虚线为原r20范数归一值1。控制的当前范数略高于原r20，并不违反零控制稳定性门；零控制不参与有限物质接受。没有新方向信号实测，本次不能说两个方向可分辨或接受21。新有限方向的完整入口尚待78950工件E2E；旧77126只验证共用端点/16门分支，合成测试只验证信号归约逻辑。

## PRE-RUN与POST-RUN

[PRE-RUN CHECK]

Code: PASS
Logic: PASS
Physics: WARNING

Key Issues:
1. 执行前审查逐块回执、16map/child预算、协议和候选身份；新审计只写handoff，不改正在运行的数值源码。
2. 先解析和篡改反例，再旧真实三组反馈，最后新控制首包E2E；四组合完整向量差独立求范数。
3. 原门核函数明确复用；Mac不重解ODE或全场转移。窗口和信号诊断不是严格误差界、Jacobain证明或物质接受。

Decision: RUN

原执行前记录在outputs/review-20260925/refreshed-direction-audit-prerun-20260928-1245.txt。测试与E2E退出0；工件数组有限、正气体热能通过，760份map/反馈回执均0且资源门通过。本地审计日志无warning/traceback，学校父stderr空；不能据此称所有worker stderr无warning。量级与固定x20慢漂移一致，图无新的数值伪影。原接受数20、物理dt与r20不变。下一次审新的thermal/population反馈，不追加控制预算。

备份outputs/review-20260925/pre-refreshed-direction-audit-20260928.bundle。审计结果为handoff/evidence/20260928-refreshed-directions-control08-review.json/png；代码、测试和小报告提交Git，大场保持学校原位。
