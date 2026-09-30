# 82515真实映射审结及有界双种子反馈

82515，2026-10-01 04:31:44–05:16:46 CST，COMPLETED0:0，anode02、32CPU128GiB16worker、45分02秒。程序2689.145506807603s，父RSS1006174208B，152个worker回执最大3584528KiB，stderr空。2map、0反馈、0物质；accepted20不变。数值5013c0caef0f41793a05e61e96ba793d70017c08。

完整归档`complete-1790803000032114486.tar.gz`，3563283B，SHA256 `adb0b6c6dcc2b2b13af6dd55c99aa425fbcc30ef353f40de3462148a8cc4cfce`。独立`review_x20_global_boundary_validation.py`未修改一次真实工件E2E通过；325files/778codeclaims/37本地sourceclaims，其余绑定上游审计，trial/native、频率归属、输入输出SHA、完整统计和边界舍入均核验。原工件不改。

16门全过。真实full/half L2比0.795392556008557/0.8957443959492912，Linf比0.8150734929204012/0.9075367464602007；实际输出减预测L2比3.23708385135141e-8/1.8122849563522067e-8，Linf比3.1010074965723685e-8/1.9549829869695368e-8。half对两端平均L2/Linf为5.132908939208133e-9/4.718924451305779e-9。边界L1相对原0.9015278313978241/0.8250694946217066，bol相对原0.9819999005008802/0.9910000162642212。没有严格解误差界或反馈资格结论。

新真实输出验证了统一三系数在本次方向/幅度的预测相容性。不同于82503逐块候选失败，但两轮候选不同，不能唯一归因或证明全算子仿射。标准matplotlib对比图/CSV已保存并目视，`20261001-x20-global-true-validation-comparison.*`，同一A16归一化，无隐藏点、floor或新物理计算。讲义§113及CLI草稿/独立纠正JSON保存；实际模型deepseek-v4-flash[1m]。CLI的“一次拟合”被纠正为冻结系数后的新求值验证。

下一批新命名run `outputs/hpc/x20-global-window-feedback-20261001`，新`operations/x20_global_window_feedback.py/.sbatch`，源82515 full真实输出SHA `fc232359ad949af5959477d985e9158b5a5ab4836626eaf6d401fd176a877f81`与82273 historical T_H16 SHA `b83131bd6408b2845075a175a6609822c2599f6e61fb4ef4cf9fe11c11c68f47`。仅改变数值初值，不变x20/old/r20/phase/dt；原trial先写再init/native/source/operator配置核验。旧pair16反馈仅对照测量，不冒充新seed反馈。

理由：约20.46%的辐射数组L2收益不决定净加热和物质响应一致性；需要正式反馈测量。预算沿已验证的配对流程：加速8→历史8→加速16→历史16，最多32map4pair0物质、32CPU128G16worker6h。原七门/物理域/资源失败即停；仅漂移失败仍完成同龄对照。两16−8窗口与cross16所有完整512维差三范数/r20≤.001、/冻结80195signal≤.1，并保留全部原率/加热门。若不具资格先归因，不自动反复32map；通过也不接受21。

新独立审计入口`review_x20_global_window_feedback.py --job JOB --base BASE --out OUT --target TARGET [--terminal TERMINAL]`，支持有序部分快照与终态；硬失败要求专用失败审查。新产物E2E尚未发生。新增源码与测试不改旧声明依赖；两端pre-82515-review-20261001.bundle保全。初始40项Mac测试通过，随后补上学校真实源文件路径而非跳过身份测试，最终复验和提交记录另附。
