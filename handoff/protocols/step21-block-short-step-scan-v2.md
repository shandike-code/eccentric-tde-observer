# 只读短步扫描 v2：修复结果索引的JSON类型

继承step21-block-short-step-scan-v1.md全部物理身份、数学公式、阈值与0新map/反馈/大候选/物质接受限制。
唯一数值程序差异：把最限制点index的三个NumPy整数显式转换为Python int；不改变其数值。
声明路径改为v2源码、sbatch、序列化测试和本协议。旧v1所有字节不变。

77747 FAILED1:0在2026-09-26 17:39:58退出，运行4分46秒。
scan已返回且源SHA后验已完成；json.dumps遇到int64失败，prediction.json未提交。
没有持久化的扫描结果，因此不填可行步长/上界，也不从程序失败推断物理失败。
失败包与stderr保留，修复后新目录重新进行最多三遍只读扫描；不是自动重试旧作业。

新run outputs/hpc/step21-block-short-step-v2-20260926；4CPU16GiB，1小时硬限。
测试必须复现旧结果含witness时JSON TypeError，且新完整结果在零上界、正上界、无受限点三类可严格JSON往返。
Mac与Linux同组测试通过后才提交。父RSS<6GiB，输入/代码SHA前后核对，所有物理门仍原值。
