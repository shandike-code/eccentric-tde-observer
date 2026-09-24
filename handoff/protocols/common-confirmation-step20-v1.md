# 第20步候选同态确认

## 已知结果与固定候选

76639于2026-09-24 20:13:24完成，53:01、COMPLETED/0:0。Mac审计3087文件、304反馈与608map回执通过。pair04原15/16，仅noise0.1153912634失败；pair08原16门与四组合通过，noise0.04215081393、heat1.66844077036e-4。第4张失败保留，第8张只支持候选，不接受20。

基态$x_{19}$为76554 confirm2已接受trial；方向$r_{19}$为同端点final响应，三范数8.33020939467705/0.268477524599201/2.709653378977141。候选始终$x_{19}+r_{19}/128$，即76639的trial，不用响应目标代替它。物理旧层、phase1367、dt889.419892762322秒、密度、能量定义及原科学门不变；新control响应只比较，不替换原方向或分母。

## 顺序与停止条件

新run `outputs/hpc/common-confirmation20-20260924`，新驱动`operations/common_confirmation_step20.py/.sbatch`。

1. control为零位移$x_{19}$，从76554confirm2最新mapped后继开始，4map加1pair。5稳定门、inner与物质正域、完整态与资源门通过，且76639pair08相对新control四组合三范数全收缩，才继续。
2. confirm1从76639 `endpoints-map08/manifest.json` 的mapped_final开始，固定同一候选2map加1pair；原16门与新control四组合均通过才继续。
3. confirm2从confirm1最新mapped后继开始，再固定同一候选2map加1pair；执行同样原16门与四组合。

任何失败停止，不改变alpha/dt或临时增加map。全部通过也仅`confirmed_requires_mac_review`，counter19/new0，待Mac独立审计再接受20，不自动起第21步。每child三槽独立保存两个反馈输入及后继，不搬移或覆盖祖先端点。

## 身份与资源

prepare核已审阅小归档SHA及实际源清单、accepted19记录，明确零基态与原r19相等；候选和零基态初始化前落盘。exact_trial验证encoded/base/r/direction/alpha、T/H/He/比能/物理层，native镜像在allocation内预检，通过才declaration/maps。原模板来自76639 inputs/feedback_reference.json，核与pair08固定来源一致，删祖先retained_manifest，零control明确alpha0，不误标候选1/128。

inner1e-4、boundary1e-3、heat1e-3、noise0.1、trust温度0.5/能量0.25/布居0.05不变。禁floor/clip/nan_to_num/删失败层/后归一化，不缩物理dt。物理算子、已声明旧代码及数据冻结。

cpu_long32CPU、128GiB、16worker、BLAS1、hugepage0、4h；最多8新maps/3pairs/9新dat，入场12STATE_BYTES空闲。每worker native和/proc小于6GiB，每新反馈态累计worker批墙钟小于900秒。USR1完成当前batch后停止，watcher只读保存调度器终态，不重交。

pair08最大单元最不利收缩比0.998175824175，改善约0.18%；这不是全状态收敛。map4final到8final残差向量差三范数0.09114988951/0.005186556857/0.03789086424是有限间隔漂移，不是误差界。尚无自洽耦合柱、完整径向/相位覆盖或整盘涌现强度，也不能据此断言模型无解。
