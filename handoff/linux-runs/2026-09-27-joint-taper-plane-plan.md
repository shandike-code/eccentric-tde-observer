# 两个真实方向的有界凸二维筛选

77954已证明渐消的加权预测遗漏显著核心内响应，因此不再调taper。此次使用原x、统一候选q、渐消候选z及各自真实输出，只对两个方向使用标量系数。新模块joint_taper_plane.py与scan_step21_joint_taper_plane.py/.sbatch，协议step21-joint-taper-plane-v1.md。

凸三角形alpha,beta>=0、alpha+beta<=1；完整场Gram及线性项定义真实端点缺陷的二次预测目标。二维小问题逐边解析求最优，0.99安全系数后扫描全部点，正负最大缺陷约束逐分片生成见证点，保留hex原值。任何候选都必须通过最终全场检查；不以有限抽样或优化器成功代替。

默认4CPU16GiB、1h，最多6遍统计（1Gram+最多5约束扫描），4096约束，0map/反馈/候选dat/新接受；父6GiB守卫，来源SHA读取另计。全/半预测边界严格门和非增、原最大缺陷不增、非负/有限、流式及二次型L2改善至少20%。未通过即保留失败，不调门，不宣称二维域或模型无解。通过也只授权下一步独立审计，禁止自动做真实map。

输入包含原配置/trial/状态/映射摘要的已审计字节，配置SHA与state绑定；完整大态前后SHA核，旧src/scripts/hpc不改，原x20/r20/dt不变。Mac23测试0.69s，涵盖已知二次型/凸边界、正负约束、退化Gram、非有限、逐点约束见证、流式二次一致性、未选输入、次正规尾、扫描预算、重复约束及失败不接受；编译/sbatch语法通过。Linux结果及job另记。

备份outputs/review-20260925/pre-joint-taper-plane.bundle。学校只读watcher增加joint-taper-plane，解释0map和预测身份；进度含系数及末轮全门。下一次审核Gram/slab、六通量、逐轮polygon和cuts的hex/index及实际候选检查。小包不等Mac重扫大场。
