# 五块方向完成审计，准备真实全域验证

78037 05:44:36–06:18:07，33:31，COMPLETED0，32CPU128GiB，两局部worker。原map逐位一致；两组L2剩余0.31042248106149783/0.11000966173173272，最大剩余0.40893809359075917/0.37328936572168475；独立half误差/原L2为1.363111796106177e-10/1.0036181454294057e-10。16GMRES/info2/linear_audit false保持，不是线性收敛。全步fraction=1时prediction误差0不是独立证据，half是真实另算。

组耗时1937.87/1021.03s，rawmap105.62/54.57s，均不到24rawmap；进程峰15380272/14959332KiB，低于24GiB，绝对进程墙钟1953.69/1035.14s低于3600s。所有局部门通过、stderr空、0全域map/反馈/接受。

原小包complete-1790461087073776500.tar.gz95897bytes，SHA fb8125c24c8da6ab5f1c742a54be0d87389dcad92b74d1bce6c27c92777fe4c5。Mac metadata核验与旧77577来源链、代码声明、五块Linf交叉通过。

78038默认4CPU16GiB只读复算06:52:03–06:52:57，54秒COMPLETED0；实际53.91s，峰4041310208bytes。读取前后SHA验证原input/output及两local NPZ；逐频率完整32角4096深度扫描，1280行longdouble平方和与最大/最小值输出。Mac review_step21_five_array_scan.py独立fsum通过，并逐自然块交叉旧Linf。来源归档和声明一致，未改大数组；原始与新L2同时交叉一致。Mac未读取全部大数组或重解算子/half/边界，不夸大独立性。

两个local NPZ各1342177816bytes留学校：24 SHA1451a6f4267b33feaacb8bd7cd13b3e8f7e43fa636e3131f1a45f01e196e8ee9；48 SHA355a0cdfcdc9e6811784aae23f52cb30adadda71ec429fae5a24b83aa3b3b896。扫描原小文件位于outputs/review-20260925/five-array-78038-received，原结果小包five-blocks-78037-received。没有回传大NPZ/.dat。

决定进入新协议step21-five-block-global-v1.md：同77577基准，拼接两核心覆盖十块，其余输入逐位不变；真实full/half各1map。成本门20%L2改善，最大不增、半步/边界/严格辐射/正性全过才继续map2/pair02及map10/pair10，最多11map两反馈。若首门失败两map停止，不盲延长；若质量窗口失败仍不得接受物质步。外侧21/27/45/51仍可能放大，五块局部与三块局部范数域不同，不按比值直接推算法效率。代码、状态和科学结论分开。

PRE-RUN新全域入口：同一物质身份、原频率核与76自然块不变，新增helper五块索引/候选shape640、未选次正规尾逐位保护，原6GiB父/worker门不改；原r20不换；接口和负路径测试后才提交。POST-RUN局部审计：全部有限正值、资源过门、两图/证据已核查，但没有新物质步、自洽柱或整盘I_nu。

备份pre-five-block-review.bundle与pre-five-global-validation.bundle；学校pre-five-array-audit.bundle。讲义§44解释证据范围，CLI草稿实际deepseek-v4-flash[1m]，已纠正把比值叫绝对残差、把一般源映射缺陷混作GMRES线性残差、把“不证明守恒”说成“与守恒无关”等过强说法。
