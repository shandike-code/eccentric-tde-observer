# 77817 联合块结果审计与全频验证计划

20:34:12—20:57:11，22分59秒，Slurm COMPLETED/0。两个联合核心分别覆盖23..25、47..49。原物质x20、r20、旧时间层与dt不变。未做全频map或反馈，新物质接受0。

## 完整性与独立证据

小包95223bytes，SHA `fd35de4ffb1e077610acfd4f6258b70b943a7e4f871d9d608181ee793f40ad98`。Mac已校验13个小文件、700代码声明、两个进程回执。两个局部NPZ各805306904bytes均已下载，SHA分别`2d2e2ca95c603ff9eb6affd35b09cdcbf8420e3bcd50062c6564ad2c89146515`、`9e308a84b77564a420881c0dac6a915e499ce82e1f7f05d37aff3c5c54b21c4f`。按384个频率切片longdouble平方和再fsum，独立复算候选实际缺陷L2/Linf及最小值；原始Linf与三个自然块既有报告交叉核对。

真实审计入口handoff/audit_tools/review_step21_joint_blocks.py端到端通过，输出20260926-joint-block-pilot-review.json/png，图已目视检查。没有在Mac重解算子、半步、旧L2或边界积分；这些依赖学校受审执行和来源哈希，不扩大独立复核范围。

## 数值结果和物理边界

23..25核心：L2比0.23716858193481952，Linf比0.3394235052772779，半步仿射误差/原L2=1.1047486872108308e-10；47..49核心：0.10421169787230458、0.40479873962526924、7.726272185851105e-11。重放原map两组均逐位一致。候选有限且严格正；边界变化不增。真实进程峰9559904/9102456KiB，均低于16GiB；各1302.28/536.60秒，约19.1/19.3个联合块单map，过预先24倍成本门。两组全部局部门过。

两组GMRES均16次、info2、linear_audit_passed=false。这不是线性方程已经求解；证据只是这个不完全方向在原算子下改善了局部缺陷。端点预测误差0源于fullfraction1，不能独立佐证线性；额外half才提供独立样本。

POST-RUN：两worker无stderr，有限/正性/哈希/进程资源/半步检查通过；0全频耦合与物质接受。大核心23..25和小核心24范数覆盖域不同，不能直接比较两者比值来断言哪种算法更快。外侧22/26/46/50可能继续被放大。

## 下一批

operations/validate_step21_joint_blocks.py/.sbatch与joint_block_global_fields.py，新run step21-joint-block-global-20260926。固定77577原x，覆盖6个自然块，其余逐位复制；全域仍使用原76块算子。先full/half各1map，原全域缺陷/边界/半步门全过才条件继续两轮反馈，最多11map、2pair；失败停，无自动重试，不改物理dt/r20。细节见step21-joint-block-global-v1.md。

Mac36测试1.11s通过，覆盖384核心切片写回、重叠拒绝、未选次正规尾不变、邻频耦合与半步、预算/信号/物质接受禁止；Linux检查和job号另记。原数据和源码保全，备份pre-joint-global-validation.bundle。
