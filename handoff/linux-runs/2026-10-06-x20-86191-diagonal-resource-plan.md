# 对角共享候选的独立资源协议设计

本轮完成x20-86191-diagonal-resource-v1.md及独立审阅。只设计一次固定首32/9632组、即1/301片的新资源预检，不授予Job预算。Mac起点552b47e7abf9b9531065a064c08640354f00ecc0 clean，学校4b02b0865ed45103770a6ecf63638c9696bd0a62 clean；未同步生产。没有新数值实现、tests、真实dat读取下载、Slurm、map、反馈、ODE或物质步。

实读旧reuse driver的authenticated_probe确认其显式调用reuse.slab_statistics，旧contract固定reuse SHA及version3，旧review检查该身份。现有资源资格不能直接移给diagonal。新协议另命名diagonal_resource.py/.sbatch、diagonal_contract.py、diagonal_receipt.py及独立review_x20_85889_chord_diagonal_resource.py；两端查未占用，实施时再查。

新version4身份只调用冻结diagonal.slab_statistics一次，必须同时固定直接导入的square辅助和所有传递执行依赖。原代码不改。旧contract.exact对dict.keys采用集合相等，因此新摘要比较另要求字典键序列严格相同；不只比较若干范数或状态true。生产历史基准继续固定86061四小JSON的大小SHA、真实终态及完整probe，本轮实际核四文件合计66216B，没有重跑旧数值审阅、读取大归档或真实场。

拟定单节点4CPU16GiB、线程1、Slurm1800秒、程序全生命周期严格小于1500秒、峰值RSS严格小于6442450944B；这是独立拟定上限，尚未授予。六全场前SHA全过后，六首片原句柄读取不可变bytes先hash，再frombuffer只读输入给新核；同片原句柄seek重读，六全场后SHA及binding/live/archive/code后核。全SHA另有句柄，不能称全程只开六个。新工作集缓存和临时数组仍须实测，调用数114不能作为RSS上界或提速证明。

正常field逻辑payload121601261568B、归档前后607755804B，小源/代码/历史另计，非设备I/O。326小来源、801历史源码、当前native/六runtime、完整trial数组及物理old/base/r20、phase1367/dt889.419892762322与几何所有权都在前后门内，并与独立历史/外部绑定比较；不能仅凭前后彼此相等认证来源。真实六SHA必须新Slurm内执行，旧86191不能代替。

两端新进程np.geterr查询实际均为divide=warn、over=warn、under=ignore、invalid=warn。新协议固定该入口策略，未来导入全部生产依赖后及运行后核验，不能静默seterr修正；辅助内部原errstate保持。call/log未认证，不允许进入该版本。此查询不是数值核测试，也不证明未来生产进程已符合策略。

外部观察器最多2400秒/每10秒只读，保存实际新job终态，独立审阅需提交回执expected_job_id、外部code/binding/terminal、完整28阶段、child0及COMPLETED0:0。旧85889/86061/86191不得冒新job。小包白名单32MiB单/64MiB总，拒dat/链接/重复/越界；先核整包及成员再独占收件。失败保留、不重交/换片/恢复或自动扩预算。

两端完整pre-diagonal-resource-plan-20261006.bundle已verify，大小及SHA/学校日志由小证据索引。标准库准备脚本首轮从/tmp导入项目contract因缺PYTHONPATH失败，尚未写协议或pins；加PYTHONPATH=.后成功，未改来源断言或数值代码。所有已读旧代码与历史小文件pins保存在20261006-diagonal-resource-plan-pins.json。

PRE-RUN：Code/Logic PASS、Physics WARNING，RUN仅文档/完整性/备份和环境策略查询。POST-RUN：无新数值结果或图，旧源码SHA不变；新协议没有生产可执行入口。学校无工具CLI只审全文协议，实际模型、耗时与逐条纠错另存cli-draft/cli-review；讲义163追加保留旧前缀。

下一项按协议实现新显式driver/contract/receipt/reviewer及两端合成封装验收，尤其补square依赖缺失/错误SHA、错版本/旧job、键序/零号、前后同时伪造runtime/native路径、信号/资源及完整review_run负路径。之后再冻结、核真实来源并作具体PRE-RUN，独立决定是否允许一次新Job。当前submission_ready/production_resource_verified/controlled_speedup_measured/full_scan_authorized=false；完整301片DO NOT RUN，旧三个Job预算关闭，accepted20及跨16响应失败/五率通过不变，HHe未完成。

全文CLI实际53.874566秒、deepseek-v4-flash[1m]。独立审阅纠正其三个历史工件（实际四个）、合成未覆盖精确比较（已有且新封装要求继续覆盖）的误读；采纳实际模块origin/冻结SHA检查及外部提交回执绑定sbatch/命令/commit/run/JobId，并核scontrol Command/WorkDir。补强已写入协议；不把终态和SHA夸大为密码学执行认证。
