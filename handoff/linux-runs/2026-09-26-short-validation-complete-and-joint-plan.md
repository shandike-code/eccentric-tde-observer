# 77790 完整审计与三块联合试验计划

## 完整结果

Slurm COMPLETED/0，19:08:12—20:26:50，总1:18:38。10个control map、1个half map、两轮正式反馈。科学终态 `second_control_pair_not_stable`，不是程序崩溃。

完整包 `outputs/hpc/step21-block-short-validation-20260926/archives/complete-1790425586959295416.tar.gz`，151977913bytes，SHA `e5c76bf3967d7095713b0079e6eb79c871fc10fe9f0139167fd4384d04e8ff4c`。Mac审计入口review_step21_short_feedback.py完整终态真实E2E通过：3545files、698code claims、836map/304feedback进程回执，峰4040732KiB。终态scheduler、首阶段、首反馈与本轮来源一致。完整证据见20260926-short-validation-complete-review.json/png。

两轮原七门全过、气体热能为正、未见stderr。最后global残差2.6817411772486756e-6，边界L1/bol=7.939891891894331e-7/7.938238937379649e-7。
八map四组合最大L2/质量加权/最差单元除原r20范数：[0.001284334652567993, 0.004843698741684269, 0.0006967100060468904]；门统一0.001，前两未过。
比77577相同长度窗口，三项幅度分别下降约11.80%/3.01%/15.85%；这是不同窗口的观测比较，不能把全部改善归因于短步而排除额外Picard迭代。真实首步仅L2下降0.3031%、最坏点不变。

POST-RUN：小工件完整性、端点与物质身份、原七门、有限/正热能、固定r20三范数、进程回执与内存均核验。未重解Mac物质ODE或下载重算大场。接受仍20、新增0；不推断模型无解，不给整盘完成时间。

## 决策

停止同方向微步和机械重复8map。下一试验将23..25及47..49分别作为384频率核心，精确原网格与Doppler halo不变，源仍77577原输入以隔离修正支撑范围的作用。先原映射重放，失败即不做该组Krylov；成功才有界16迭代、非负方向搜索和独立半步检验。最多两个局部试验，0全频map/反馈/接受。

新operations/joint_frequency_block.py与pilot_step21_joint_blocks.py/.sbatch；协议step21-joint-block-pilot-v1.md。不改旧源。局部过门后仍需审计，不能自动进入全频；外侧22/26/46/50可能仍被放大，须真实全频才能排除。

Mac19项测试通过(0.88s)，包括exact planner自然块重建与不同分块的真实小网格源映射一致性；编译和sbatch语法检查通过。Linux检查和提交信息另记，不把小网格通过等同真实分辨率通过。

备份outputs/review-20260925/pre-short-completion-and-joint-pilot.bundle。平台本轮结束后才增加新operations文件，保留原77790冻结数值代码。
