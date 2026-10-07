# 86304：认证内存配置组合的小合成验收

本阶段实现普通函数 `configure_from_bytes`，显式返回 fixed、template、context、material，不修改旧科学源码，不调用原 `_configure_worker` 的全局 lambda，也不调用 warm-seed 的 Path.resolve。配置组合小合成通过；完整 native 准备与生产资格仍未完成。

## 输入与实际操作

七个角色 fixed/template/trial/base/residual/old/master 必须全部提供不可变 bytes 及外部 path/size/SHA。固定协议绑定模板，模板绑定 old/master；新 fixed.current_material_state 与 template.second_material_iterate 指向认证 trial。模板 initial_radiation_state 仅按原顺序替换 path，其余原字段保留；单独返回的 warm_seed 完整声明才是本接口核过的路径/大小/SHA，不能把模板遗留字段冒充当前场认证。warm 路径只作词法检验，不读、不 stat、不 resolve。

ArrayLoader 解码 trial/base/old/master；标准 NPY 头核后残差为只读 frombuffer 视图。trial/base 全部数组 dtype/shape/字节相同，scalar phase/dt 对外部期待核，old/master 先验证域和形状，再调用原 exact_trial(control) 与既有 trial_and_mirrors、context_from_arrays。外部 shape、phase、duration 与实际 context 对照；core 频组连续恰好覆盖，块长 128（末块可短）。没有更换原数值表达式。

返回的仅是配置与物质/几何数组。原 map 的 input_state_sha256、diagnostic_fixed_iteration_count、spatial_scheme、source_map_only 及真正 native worker 执行属于另一范围，本轮没有生成 map 协议或调用初始化、映射、反馈。外部 claims 仍须独立科学来源清单认证；此函数不自行证明来源科学身份。

## 新验证与封装

两端各 21 项新增测试通过：Mac 0.87 秒，学校 19.74 秒。首次 Mac 21 项失败均由夹具把 codec 返回对象误当字典，改为属性访问后通过；原 tests-01 日志保留。无断言/容差放宽。旧 context25、memory21、boundary15、inputs50、resource114、supervisor18/8case 不重跑。

新的专用合成入口使用 -I -S、显式环境预载、StopGuard 安装、内存源码冻结与 seal，然后执行配置组合。supervise 默认外层 150 秒、合计输出 8MiB；子程序原 StopGuard 为 120 秒/历史峰 RSS 1GiB。实际接线只认证此专用合成入口；没有由它获得生产资源资格。源码 pack 文件在 seal 前按外部 SHA 读取，解释器启动和环境加载仍为可信范围，不是完整生命周期访问保护。原 supervisor 的 Popen/内核调度/回收延迟限制仍适用。

实际专用夹具为两相位、128 半列单元、零 control、9632 频组，生成完整 76 块规划但不分配辐射大场。七原始合成来源合计 26,742B；loader 压缩接口返回 21,027B，解压成员返回 145,744B，显式累计预约 642,554B；残差视图 payload 4,096B 另列。预约新增 trial/base tobytes 比较，但仍不含全部 ZIP 内部缓冲、Python 分配和原科学临时量，不能当总 I/O、总分配或 RSS 上界。NPY 头解析与 JSON 解码也不能套入压缩接口返回字节字段。

Mac 内部 0.9861757918 秒、峰 RSS 177,963,008B，外层 1.0533426250 秒；学校内部 5.2282360200 秒、峰 RSS 143,917,056B，外层 5.6043219190 秒。仅小例，不是 150 秒或 1GiB 的实际耗尽测试。

封锁后实际 153 原项目/新配置模块，静态 pack 190 含空 operations namespace、189 交 FrozenModules；含旧两入口较宽闭包，不是最小闭包。独立原始 NPY 审阅核 trial/base 身份、四镜像逐字节、单位层宽的全柱边界、零 beta、master 全边界、76 块以及 fixed/template 赋值。实际 loader/file/spec 来源与 pack 源码 bytes 核。学校仅逻辑 root 重定位。配置、来源 bytes、material、除 mu/weight 外 context 以及模块名跨平台同；mu/weight 各自 0–3 阶角矩绝对门 2e-14 通过，不声称全 context 逐位相同。

六种修改副本（资格提升、bool phase、块缺口、镜像 SHA、trial claim、缺原模块）被独立标准库 reviewer 拒绝。该 reviewer 不导入配置器或数值模块；不是 Mac 重执行学校 Linux。

## 保存与边界

两端完整 pre-86304-configuration-20261007.bundle 已 verify。Mac 起点 aa78d70b6484c4694fe86a541e231cd5d0d12e37；学校 fbfe81fb7ec4e9714e256ec460b483130db5c254 clean，未生产同步。freeze01/02/03/04/05 保留，最终 1738 源码全 SHA 后核；学校 170 夹具文件前后 SHA 相同。最终 Mac reviewer 另加块索引真整数与 mu/weight 字节指纹核；未部署学校，执行源码不变，两个原回执重新独立审阅通过（independent-02）。六小回执 305,271B 根据外部大小/SHA 核后独占收于 preparation-configuration-school-verified-20261007。

证据位于 outputs/review-20260925/20261007-configuration-*；Mac 专用目录 preparation-configuration-local-20261007，学校 preparation-configuration-fixture-20261007。新增配置模块、合成夹具、独立子程序、reviewer 和 test 五文件保存。旧科学输入与源码不改。

本轮真实 NPZ/native 刷新、dat stat/read/download、科学归档 payload、Slurm/map/反馈/ODE/物质均为 0。accepted20/newmaterial0、校准 strictbound=false、十倍跨支质量失败保持。

## 后续具体实施

先接续此组合入口，补带明确上限和检查点的 ZIP 内缓冲及原科学临时量范围，逐表达式列出包含/不含项，预约不能只换字段名。然后实现并小合成验证解释器启动/环境预载的实际访问保护；已有 Linux post-environment seal 不能倒溯保护启动。若最终仅允许学校 Linux，需在入口与独立审阅中明确平台范围。当前普通函数可构造配置，但固定真实准备入口、全生命周期保护和全部 loader/resource 计量仍未独立验收，因此 complete_native_context_verified、native_loader_metering_integrated、production_resource_stop_guards_integrated、actual_source_manifest_prepared、submission_ready、new_production_authorized 均保持 false。

不重跑本合成，不实际 staging 343 来源，不真实刷新 native 或归档；全部准备独立验收后另审首次真实来源预算，生产首片另立，全 301 片 DO NOT RUN。
