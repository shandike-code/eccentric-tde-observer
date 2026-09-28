# 78950：重新测量物质方向的启动记录

2026-09-28 11:31:15提交78950，11:31:16在anode20进入RUNNING，qos_stu_cpu_long32CPU128GiB、16worker。硬限8小时，到19:31:16；这不是预计完成时间。数值源码579be9bd2dad6770ac0f7db63efc8ed00189f01b，run为outputs/hpc/step21-refreshed-directions-20260928。

Mac101tests1.09s通过；Linux100passed、1skipped、18.20s。唯一跳过项需要Mac接收目录；学校随后用原实际输出完成独立小输入预检，三组trial精确身份、native映射身份、原接受门及零/有限授权均通过。py_compile和bash -n通过。小预检不读大seed、不做转移/物质ODE；大seed由batch完整SHA检查。

11:34:51实测RUNNING/00:03:35，根status仍preparing，control初始化、0完整map，无active_map，父stderr0字节。declaration已生成，说明prepare的完整claims/code核验已返回；源78594及其10099884032字节末后继sha87e18e8dbbeb70779712fc49f9ae9f827991619e9ddbc7e7717565708de826c7与声明一致。此时不能声称首map、任何新反馈或物质更新完成。

执行顺序control8/thermal8/population8/control16/thermal16/population16，各自最多16map，共48map6反馈对，失败依协议停止。所有方向/接受尺度仍取原r20，物理x20和旧时间层固定。信号S由候选减同期对照的完整残差向量定义，同时查端点散布及八map变化，零信号保留为未分辨。原16门和同期四组合比较都保存；本批自动接受数始终为0。

平台监督tmux为step21-refreshed-78950，运行handoff/audit_tools/watch_refreshed_directions.py，输出outputs/review-20260925/refreshed-directions-watch-78950，时限32400秒。CLI无工具，在开始、反馈里程碑、终态只读点评。首回执实际模型deepseek-v4-flash[1m]；其“预计19:31:16结束”措辞不正确，该时刻仅为调度硬限。正式记录已纠正，不把CLI意见当数据判决。

Codex定时任务USTC HHe 运行审阅与决策已恢复ACTIVE，每30分钟，提示已改为本批三组诊断与后续独立审计。健康状态不反复通知，完成/实质失败/需重连才通知；SSH失败暂停空轮询，重连先查原78950，不重交。

下一次先审最新归档，不重复下载已有中间包。完整审计需新适配3组8/16map，旧positive_plane_feedback硬编码3map不能原样用。可复用其逐块反馈、codec/能量与16门检查，但信号与漂移指标必须独立重算，不能拿生产response_measurement当独立审计。物理/原门失败保留失败，不能删断言。源78594已完整独立审计，本批当前尚无数值结果，接受20、自洽柱/整盘I_nu未完成。

证据：handoff/evidence/20260928-refreshed-directions-launch.json、20260928-refreshed-directions-preflight.json、20260928-refreshed-directions-initial-observation.json。Mac旧Git备份pre-stationarity-audit-and-refreshed-directions-20260928.bundle；学校pre-refreshed-directions-20260928.bundle；自动化旧全文automation-before-refreshed-directions-78950.toml，均在outputs/review-20260925。初始化后运行代码保持冻结，启动记录单独提交。

同步过程中一次GitHub push返回ref已在579be9b而预期13fe822的锁冲突；随后ls-remote实测远端SHA正是579be9bd2dad6770ac0f7db63efc8ed00189f01b，因此记录为目标远端已存在，没有强推或回退。
