# 78548反馈窗口通过：独立审计与持续性确认计划

78548于2026-09-27 20:55:50–22:17:10完成，COMPLETED0/1:21:20，anode18、32CPU128GiB/16worker。11map（10control+1half）、两对反馈，终态seven_refresh_short_validation_complete_requires_review，20接受/0新接受，r20和物理dt不变。父stderr空；调度终态来自watch保存记录，不能依赖清理后的旧scontrol。

完整包complete-1790518608710094128.tar.gz为152112504bytes，SHA36396e2b88c455d9d7f60fdc4b558f4f56de1029de47eeaf9cb04e56d76d6b86；Mac只用rsync下载小工件包，未下载dat。解包seven-refresh-short-78548-complete-received。审计review_step21_seven_refresh_short_feedback.py真实E2E通过3545files、730codeclaims、836map/304feedback回执；逐块native/common替换、9632组所有权、归层、能量恒等式、编码身份/正域、原七门、四组合独立math.fsum复算，首阶段文件逐字节匹配。原七门归约复用既有核，窗口归约独立；不在Mac重解物质ODE或大辐射场。

八map窗口四组合的最坏L2、质量加权、最大单元差/r20为0.00017667573334548305、0.000509925508195912、0.0001481333835817387，12个比值全部严格低于0.001。pair02相对78161的初值位移最大mass0.016927989839582398是另一种比较，不能拼入收缩曲线。原七门两轮全过，pair10加热变化约3.66952e-6。四端点最低气体热能7.026313085045115e12erg/g为正，所有已审数组有限；进程exit0、资源门通过，峰4041280KiB约3.854GiB。图目视通过，保留初始化位移与八map漂移的不同含义；归档无worker stderr原文，不称逐worker无warning。

当前final物质残差范数8.260386273333364/0.2820707110639354/2.7057116815426463，并不接近零。当前向量减原r20的范数0.9759560819052615/0.10214475060064551/0.1312675136309738；质量差约为原r20范数的39.00%，不是两范数之差，更不是自洽残差本身。不能因相邻漂移很小便认为旧r20精确，也不替换基准使旧候选过门。

决定先检验本次过门是否持续：新confirm_step21_stationarity.py/.sbatch与step21-stationarity-confirmation-v1.md。从78548最后mapped_final后继（sha21e17d2fc6382b35471f0e514bb52f47222ea1279e8dd36333af4dd681ef16b0）继续固定x20，最多16map、8/16各一反馈；两个逐段窗口与累计16map四组合三范数/r20均<.001。首段失败立即停，无盲续；此为一次明确有界的确认，不重新搜索辐射方向。零新物质候选/接受/基准替换；32CPU128GiB16worker4h。窗口通过也只是持续性见证，未来物质方向需基于可靠对照重新测量有限响应、噪声分离并守原接受规则。

入场source_seed核已审78548、所有原七门、三范数形状/有限/严格阈值/不替换标志、10张连续历史与后继SHA，拒绝旧job/缺门/篡改/错误后继。测试49项Mac1.10s通过，包含首段失败不继续、停止不反馈、逐段通过但累计失败；复用控制工厂测试防止从零授权模板直接构造有限模板的历史bug。真实小工件source_seed预检通过，compile/bash-n、Markdown仅新增段规范检查通过。Linux复测和实际job另记录，当前不预写提交成功。

CLI讲义草稿实际deepseek-v4-flash[1m]。纠正开头以final_minus_r20约0.976论证残差自身非零的混淆，后者应看当前R的范数；窗口报告采用四组合最坏值，而不是只报final_vs_final。讲义第57节保留三个量的定义。原稿outputs/review-20260925/seven-refresh-short-complete-lecture-draft.json。备份pre-seven-refresh-short-complete-review.bundle；学校同步前同名备份，数值旧文件不改。
