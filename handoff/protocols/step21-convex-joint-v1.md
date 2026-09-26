# 78031已审凸候选的真实全频验证

原77577 map10 x，77843 full-candidate q，77927 full-candidate z。78031四轮全点筛选及Mac独立活跃集/归约通过，固定alpha=.2232383685126496、beta=.2344820251208071；u=(1-alpha-beta)x+alpha q+beta z。完整原场逐32组读取，所选6块同固定标量，核外逐位复制x并验证q/z不变；半候选h=.5x+.5u，核外仍逐位复制。输入有限非负，不clip/floor。

run outputs/hpc/step21-convex-joint-20260927。32CPU128GiB、16worker、4h，原76自然块，原6GiB父/worker守卫。先真实T(u)、T(h)各1map；301分片及全76块检查full L2/旧L2<=.8、full Linf/half L2/half Linf<=1.0000000001，halfaffinity/旧L2<=1e-6；strict radiation<1e-4、两边界<1e-3且不增。新增实际full L2比/Linf比对78031最终预测的绝对差均<=1e-6（固定旧尺度，不用于放松Linf门）。原全域弱尾不得省略。

任一门失败停于2map，不做反馈；全部过才control map2/pair02，原七门/正物理域过才maps3..10/pair10。总最多11map/2反馈，0新物质接受/基态替换/物理时间推进。pair10对pair02八map漂移按原r20四组合三范数均<.001才窗口稳定。通过也待独立审计，不宣称耦合大气或全盘I_nu。

trial初始化前复制且encoded/native身份逐项检查，六来源及扫描声明/最终系数hash前后核验；源码冻结，USR1当前batch收尾，不重试。备份pre-plane-review-and-validation.bundle。旧数据/核/协议不变。所有阶段打小包；预测成功不能替代本次真实map。
