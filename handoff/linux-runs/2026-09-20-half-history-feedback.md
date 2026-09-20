# 74046真实映射通过：转入同一物质的两态正式反馈

## 实测结果与限制

74046已`complete`、new_maps=1，五项验证检查全部true；队列为空、stderr空。实际分配cpu_long32CPU/128GiB、16worker。真实map墙钟144.780876秒，每worker峰值RSS3501.941406MiB。此墙钟仅为map，不包含输入SHA、候选写入、初始化和全场误差扫描，不能当总作业时间。

真实最大归一残差3.107577053675214e-5，与预测标量相同；边界L1为6.12799346376955e-5，bolometric为3.344206522507043e-6。更关键的是完整真实输出与仿射预测的误差L2为6.763750759e-14，相对场L2为1.605958085e-16，相对实际映射残差L2为1.393483515e-11，远低于预先声明的1%门。这验证的是这一组输入上的混合，不证明全局算子仿射、唯一性或完整耦合收敛。

候选SHA `b2aa8053fb1d456860333692f280616d5baacdf2af150b583b4160b2e65468fa`；真实输出state1 SHA `6df7d78d391c915757cc0f1c06c44516530d1d4df9830cf10847bb9ce349e2f0`，每态10,099,884,032 bytes。新反馈运行使用这个真实输出作为初猜；它需要在新运行中再次经过实际map得到自己的残差，不继承候选输入的收敛证据。

完整trial与73929逐字段一致，alpha=0.001953125、phase1367、dt=889.419892762322秒；SHA仍为`07a3700d8767f5bd7addf7b2932d3b44742e803e2aed52c83e2e86b82ce07b86`。初始化前后native物质镜像与物理phase/dt检查通过。没有新的H/He反馈，没有接受物质步。

## 下一步契约

新入口`operations/prepare_half_history_feedback.py`与`operations/half_history_feedback.sbatch`，新目录`outputs/hpc/half-history-feedback-20260920`。32CPU/128GiB、16worker，60分钟上限；最多2张新map、每2张1轮正式反馈、最多1对，不自动扩预算。复用冻结的`diagnostics/interval_diagnostic.py`；本轮旧src/scripts/hpc/diagnostics及已被旧run钉住的operations不改。

新种子守卫要求74046五项完整验证门全部通过，并重新检查全场误差小于defect L2的1%、实际最大残差/边界/RSS的数值；结果必须指向source当前slot中的最新真实输出，拒绝部分态、旧结果或未算全场的标量预测。源依赖、种子大态在allocation验SHA。trial先复制再初始化，前后核全部字段、seed、空历史、native状态，避免默认迁移成0.0625候选。

正式判决仍包括严格辐射1e-4、H/He率/加热、内层噪声、目标物理域与三种物质残差收缩。观察到单个门通过不替代其余门。即使物质步接受，也只接受一个有限步；若失败，先说明具体失败门与逐层目标气体热能，再选择有限下一步，不机械续跑。

## 保全与复核

`half-history-validation-74046-small.tar.gz`在学校家目录与Mac `outputs/review-20260920/`双端保存，19,875,233 bytes、721文件，SHA256 `dc8e3123a9301040f875a524b0d67b9b85593cbe256b97e0b5604e4db82ef60a`；整包及全部逐文件SHA已核。Mac解包`half-history-validation-74046-received`，旧dat保留，不下载。Git小证据保留validation_result与state。源map未产新图，无图像质量结论。

新守卫测试覆盖缺失/多余/失败门、只比较标量、旧输出、半态、改物理dt、已有反馈、数值误差超门/非有限、改误差容限、内存假通过；真实74046包通过新seed守卫和完整trial比较。正式提交前在学校复跑同一组测试。
