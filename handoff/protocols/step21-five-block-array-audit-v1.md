# 五块保存数组的只读复算

来源78037完整包及Mac metadata审计，固定两个640x32x4096的candidate/mapped_candidate，原77577 input/output。新run step21-five-block-array-audit-20260927，不修改任何原文件。读取前后完整SHA验证；原代码与物质身份由metadata审计衔接。默认4CPU16GiB/30min，单进程，8GiB峰值结果守卫；每次只加载一组local NPZ，原全场只读memmap。不回传NPZ或.dat。

逐频率保留全部32角4096深度，逐片先作float64差（与存储/原计算口径相同），longdouble平方和，输出每组640行raw/fresh平方和、最大绝对值、输入输出最小值。学校与原报告L2/Linf相对容差2e-11比对，Mac再次用fsum独立归约，核对JSON全部来源哈希/640行覆盖/最小值/五个原自然块Linf。检查失败停止，不重交或改阈值。source/code前后哈希一致才写完成摘要，部分文件不是完成。

0map/0反馈/0物质接受，不重解算子/half/物质ODE、不修改候选。Mac归约依赖学校受审扫描产生的统计，不声称Mac独立读取全部原数组。局部缺陷通过不允许自动全域接受。
