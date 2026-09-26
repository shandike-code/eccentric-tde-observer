# 五块方向只读步长扫描78040

78040已提交默认4CPU16GiB/Students/qos_stu_default，1h硬限，数值ebfe87c。Mac15tests0.87s/Linux15tests19.17s与compile/bash-n通过。run outputs/hpc/step21-five-line-cost-20260927，入口operations/scan_step21_five_line_cost.py/.sbatch，协议step21-five-line-cost-scan-v1.md。

先验证78039所有受审来源与代码，最多三遍只读全点扫描，固定0.9安全步长、20%L2成本门；源与r20/物理dt不变，0map/反馈/候选写入/物质接受。预测失败不重交或放松门；预测通过仍待独立审计和另行真实验证。

Mac备份pre-five-global-review.bundle，学校pre-five-line-scan.bundle，启动回执20260927-five-line-78040-launch.json。只读监督watch_five_line.py --mode joint-line-scan，tmux step21-five-line-78040，输出outputs/review-20260925/five-line-watch-78040。已纠正该监督入口从三块复制而来的旧指标为78039真实指标；仅监督文本改动，数值源冻结。

下次优先检查此作业状态/预测/归档/stderr/terminal；不重复审计78039。审计参考review_step21_joint_line_cost.py，须改source/十块范围和新终态来源，逐301slab独立S0/DD/RD、hex见证点约束、边界和第三遍结果交叉。全点上界仍是学校受审扫描证据，Mac小统计不能冒充重扫大场。
