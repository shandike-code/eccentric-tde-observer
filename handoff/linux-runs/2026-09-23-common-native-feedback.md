# 固定候选追加8张map与新完整反馈入口

75951已于2026-09-23 17:24:44 COMPLETED/0:0，起始16:40:23，总墙钟44分21秒，32CPU/128GiB，anode02。8张map实际合计1198.327秒（约19分58秒），每张146.87—156.99秒；其余时间含301GiB历史依赖SHA、初始化、端点复制及结束校验，不归为转移核计算时间。前后声明检查成功，stderr为空。

同一冻结1/64候选下，新map1→8辐射残差4.255073056153993e-5→2.7580056431578367e-5，逐张下降。第8张边界谱L1为2.0559350569428645e-4、总通量变化2.03665335045961e-4。第4张预算检查允许第二组4张；两对端点分别在`endpoints-map04/08`独立保存，含previous/final输入及mapped_final输出，SHA与原history相符。循环槽不能覆盖它们。尚未从这些辐射指标推断加热门通过。

## Mac复核

完整小工件包`outputs/review-20260921/complete-1790155479816780056.tar.gz`，345629字节，SHA256 `aa174267398912295e607efd3c825c47937253e6071b94855393dcd17f43555d`。`review_common_precision_maps.py`核1228文件的大小/SHA、608块拥有权、非负强度、有限数值和608独立进程回执；从块记录重新汇总8个map的辐射与边界指标，均与history精确相等。trial文件与75943桥输入逐位相等，初始化身份记录通过。原生峰值3503.816MiB，独立/proc峰值3587908KiB，均小于6GiB。

证据`handoff/evidence/20260923-common-precision-75951-review.json/.png`，图已目视：三个辐射/边界指标平滑下降，没有漏点或用坐标截断制造过门。dat不传Mac，Mac核保留manifest与history的路径/大小/SHA关系；新的反馈allocation还必须实读校验dat字节。不能把这说成Mac重跑了辐射核。

## 新完整反馈实现和单块预检

数值提交`0f4ff30c7c2a9cbf09b30fb7efa2e0c6db6a9e45`，新模块`common_native_feedback.py`及两个sbatch，协议`handoff/protocols/common-native-feedback-v1.md`。每worker先用原核实际重求原子反馈和旧源，全部保存legacy工件；再从同一辐射/物质态独立算共同频域lab四力，只替换新partial的formal字段。父级沿用原态门和原16门；无旧manifest复用、无旧判决改写、无新map或物质推进。接口与拒绝路径加原桥/四力共23测试，两端通过；shell语法和Python编译通过。

75985为默认4CPU/16GiB单块预检，已COMPLETED/0:0且stderr为空。对历史已审final block24重求，原生全部字段与旧partial逐位一致；新四力全部字段与75908独立输出逐位一致。worker34.128秒（不含所有父级核验），原生3290.125MiB、独立/proc3369088KiB，双门通过。

Mac复制`outputs/review-20260921/common-native-pilot-75985-received`，核protocol、legacy、common和新partial的SHA，重复原生/共同源逐位比较、非formal不变和有限性核验，均通过。pilot JSON SHA为`510fde614eb328b23511748e95a497b3a5363743300b9abf4e34acc9d06c35b5`。证据`handoff/evidence/20260923-common-native-pilot-review.json`及75985 terminal。pilot不是新端点的反馈证据，只证明组合入口能复现既有审核结果。

## 已具备条件的下一批

完整反馈按新协议依次求map4和map8两对端点，各76+76块，总304个worker上限；32CPU/128GiB、16并发、2小时。实际每态worker批次时间必须小于900秒，原生/proc内存双6GiB。实际输入dat和实现集合前后校验；不用未读取的历史初值充当本次数据，也不更改历史声明。

任何程序/资源/态门故障停止；第一对若物质响应离开正热能域，保存账本并停止后续对；若只是反馈精度或收缩门未过，继续评估已经算好的第二对，不产生新map。即使16门通过，也不直接计第16步，仍需共同频域下的新基态四组合、信赖域和同态双确认。频率截断、耦合柱、全盘$I_{\nu}$尚未验证。
