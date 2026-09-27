# 78411全域验证：仅full Linf门失败，转受限数值步长

78411于2026-09-27 16:47:06–17:22:02运行，COMPLETED0/34:56，2map（control1/half1）、0feedback、新物质接受0。终态true_map_not_validated，按预声明正确停止。重连后scontrol记录已清理，采用watch保留的scheduler-terminal.json，不能用空队列推测成败。

完整包complete-1790500919145982132.tar.gz，2477350bytes，SHA256 b53bff70d113204634d5a05f6d333096a4a118665bf69f6413b8e2d3387af53e；Mac目录outputs/review-20260925/seven-refresh-global-78411-received。新review_step21_seven_refresh_global.py核对325files、727代码声明、152进程回执，源/试验物质/候选/配置身份及全76块，301片独立fsum，另外把原基场每自然块最大值与78161 map10回执交叉。最大worker观测峰3582348KiB，父2159955968bytes，均在守卫内；父stderr空。没有NaN/Inf、负值或资源故障证据，图已目视。

|量|Full|Half|
|---|---:|---:|
|L2/本轮原全域L2|0.4051087204631033|0.6898723005012385|
|Linf/本轮原全域Linf|1.12406396024695|0.7133740072401477|

原全域L2为9.87060594321821e-5，M为5.3079172952774645e-8。half仿射误差/原L2=3.9008639563499157e-10、最大误差/原M=9.150906961298376e-10。11门中仅full_linf_nonincrease失败，其余包括20%成本、半步、严格辐射、边界均通过。最大缺陷增大12.4064%，不能以L2改善59.4891%抵消。

最坏full片first_group2656、32组、block20、selected_input=false，绝对最大5.966438535592866e-8。这里仅定位到片，不冒称已知片内精确频率/角度/深度点。核外输入逐位不变而输出受相邻核影响，这是局部条件求解与全域映射不同的具体证据。不能因此推断所有方向无解，half已有实际可行性旁证。

决定：默认4CPU16GiB有界只读步长扫描，源为78161实际map10输入输出与78411全步候选/真实输出；r=y-x、d=(T(q)-q)-r，求所有点|r+t*d|<=M的共同上界U。固定t=.9 min(-RD/DD,U,1)，保留20%预测及流式L2成本门，候选和half边界、非负有限、辐射上界等原门。物理dt不变，不继承78130旧系数，不扩大9/11块，也不直接选已看过的half就跳过新协议。

代码scan_step21_seven_refresh_line.py/.sbatch，协议step21-seven-refresh-line-scan-v1.md，run outputs/hpc/step21-seven-refresh-line-20260927，最多3遍/1h/父6GiB。0新map/feedback/大候选/物质接受，通过只待独立预测审计和真实验证。Mac16tests/0.92s、compile/bash-n通过，Linux复测和启动job另记；备份pre-seven-refresh-global-review.bundle，旧源与原科学核不改。

只读CLI终报实际deepseek-v4-flash[1m]。它把strict_error_bound=false称“严格误差界未达”，应精确说本实验没有建立严格真解误差界，非某个已计算误差门失败；失败是明确的full Linf门。其“立即停止”只是复述，驱动早已自行正常停下，没有执行额外取消。仍20次接受、第21未接受，本次没有新的热响应漂移可报告。
