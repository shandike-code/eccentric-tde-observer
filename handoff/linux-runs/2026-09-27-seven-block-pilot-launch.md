# 七块局部试验78052

78052已提交，源码425a2c3。资源Students/qos_stu_cpu_long，32CPU128GiB/2worker、2h硬限；每worker32GiB/3600s、成本不超过自身原map24倍。Mac24tests0.79s/Linux24tests20.44s、compile/bash-n通过。

run `outputs/hpc/step21-seven-block-pilot-20260927`，入口 `operations/pilot_step21_seven_blocks.py/.sbatch`，协议 `step21-seven-block-pilot-v1.md`。仅核心21..27/45..51，77577同源重放，16Krylov，0全域map/反馈/接受。局部过门不自动进入全域或九块试验。

只读监督tmux `step21-seven-block-78052`，`watch_seven_blocks.py --mode joint-block-pilot --seconds 9000`，目录 `outputs/review-20260925/seven-block-watch-78052`。CLI无工具、实际模型需按回执标注，不能代替科学审计。

启动回执 `20260927-seven-block-78052-launch.json`。备份Mac pre-five-short-completion-review.bundle/automation-before-seven-block-pilot.toml，学校pre-seven-block-pilot.bundle。运行期间冻结数值源码和本协议。首map逐位重放失败就停止对应组，不调公差。末态取小包和过程回执；两份local NPZ仅学校保留，不回传Mac。

后续审计参考review_step21_five_blocks_metadata.py，改7块区间896组、32GiB守卫、新源及局部大小，不能直接套5块结论。局部fresh范数须另以默认4核只读原数组扫描和Mac小统计归约交叉，才考虑全域成本。若仍主要将限制移至外边界，转向跨核心耦合/预条件研究。旧78041完整审计已完成，不重复下载。
