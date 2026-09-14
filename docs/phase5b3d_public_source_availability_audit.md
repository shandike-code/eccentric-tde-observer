# Phase 5B3d：ZO 2020 published 数值实现的公开来源审计

> [L/V/O] 截至 2026-08-30，本阶段没有在期刊元数据、arXiv v2 源包、Crossref、GitHub
> 或 Zenodo 找到生成 ZO 2020 Fig. 6/7 的公开求解器或原始本征值数据。论文正式声明底层
> 数据可向通讯作者合理请求。没有发送外部请求，没有修改 ZO 正式动力学源模型，也不能
> 授权 $\Phi\mapsto t$。

> [!update] 后续状态
> 上述“没有发送”只描述 Phase 5B3d 审计当时的边界。用户后来明确授权，唯一一封 Fig. 6/7
> 数值材料请求已于 2026-08-30 发出；当前等待作者回复，时间轴仍未授权。[V/O]

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3]] ·
[[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a]] ·
[[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|Phase 5B3b]] ·
[[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c]] ·
[[eccentric_tde_observer/docs/zo2020_author_source_request_draft|作者数据请求及发送记录]]

## 1. 为什么还需要这一阶段

Phase 5B3--5B3c 已经分别检查三维无节点分支、初值和分支延续、完整二维非线性、主文与
附录的符号差异，以及 Fig. 6 矢量曲线的端点切线。[V] 这些内部审计都没有恢复 published
$\widetilde{\omega}$ 与 $e(a)$，但也不能证明原作者私有实现采用了什么数值路径。[O]

因此本阶段只回答一个更窄的问题：现有公开入口是否已经提供足以直接复算 Fig. 6/7 的代码
或原始数据。它不是新的方程变体搜索，也不根据 published 曲线反拟合边界条件。[A]

## 2. 可重跑的来源

机器审计脚本为 `scripts/phase5b3d_public_source_availability_audit.py`，正式产物为
`outputs/phase5b3d_public_source_availability_report.json`。每个网络响应和 arXiv 源包都
记录 SHA-256，以区分“本次确实检查的内容”与以后可能变化的外部页面。[V]

| 入口 | 本次检查 | 结果 |
|---|---|---|
| [MNRAS 正式文章](https://academic.oup.com/mnras/article/499/4/5562/5922725) | Data Availability 与公开仓库链接 | 声明数据可合理请求；正文没有 GitHub/Zenodo 链接 |
| [Crossref DOI 记录](https://api.crossref.org/works/10.1093/mnras/staa3127) | relation 与注册链接 | relation 为空；只有论文 PDF 链接，没有 dataset 链接 |
| [arXiv v2 源包](https://export.arxiv.org/e-print/2009.06636v2) | tar 成员逐项分类 | 28 个文件；7 个论文源、17 个 PDF 图、4 个其他文件、0 个数值代码文件 |
| [GitHub repository search](https://github.com/search?q=%222009.06636%22+OR+%22staa3127%22&type=repositories) | arXiv ID、DOI 尾码和完整标题 | 0 个仓库 |
| [Zenodo API](https://zenodo.org/api/records?q=2009.06636&size=10) | arXiv ID | 0 条记录 |

这里“数值代码文件”按 Python、Matlab、Mathematica、Fortran、C/C++、Julia、R、shell、
Makefile/CMake 和 notebook 后缀分类。TeX、BibTeX、MNRAS class、审稿意见和 PDF 矢量图
不被误记为求解器。[V]

## 3. arXiv 源包具体包含什么

与动力学基准最相关的公开文件是 Fig. 6/7 的 PDF 矢量图：

- `Figures/EccDiskSolsPlot_12_19_2019_fig1.pdf`；
- `Figures/einPlot_12_19_2019_fig1.pdf`；
- `Figures/eAdFreqPlot_12_13_2019_fig1.pdf`。

它们允许项目数字化 published 曲线，这正是 Phase 5B3--5B3c 已使用的文献证据；但源包
没有生成这些曲线的 ODE/BVP 程序、原始数组、求解器设置或环境锁文件。[L/V]

## 4. 能得出和不能得出的结论

**能得出。** [V] 在本阶段明确审计的五类公开入口中，没有发现 published 求解器或原始
Fig. 6/7 数据；公开来源路线已经推进到论文自己指定的“向通讯作者合理请求”边界。

**不能得出。** [O] 搜索未命中不证明私有代码已经丢失，也不证明 published 结果错误。
它更不能把当前方程自洽候选自动升级为正式 ZO benchmark。外部数据返回前，现有的
`phase5b4_candidate_timescales.csv` 仍只能称为 equation-self-consistent candidate。

## 5. 下一步边界

本阶段当时只准备了
[[eccentric_tde_observer/docs/zo2020_author_source_request_draft|只针对 Fig. 6/7 的英文请求]]；
后续已按用户授权发送，当前等待回复。[V/O]

若作者提供代码或原始数组，下一阶段应：

1. 原样归档文件、许可证、时间戳和哈希，不先改写；
2. 在隔离环境复现 Fig. 6/7；
3. 对照方程、变量、符号、边界条件、初值和求解器；
4. 只有 published benchmark、模形兼容和严格有效域同时通过，才生成真实 day 轴。

若作者无法提供，则仍需用户明确批准“方程自洽但非 published benchmark”的新动力学基准，
并用新的 $e(a)$ 从源端重建有效域、连续谱、观察者 atlas 与 Phase 6 线核。不能只把候选
$\widetilde{\omega}$ 贴到旧常偏心 atlas。[A/O]

## 6. 复现

```bash
uv run python scripts/phase5b3d_public_source_availability_audit.py --force
uv run pytest -q tests/test_phase5b3d_public_source_availability_audit.py
```

本阶段收尾后的现场完整回归为 `621 passed in 60.66s`。[V]

- `[L]`：论文 Data Availability、DOI/arXiv 元数据和公开 Fig. 6/7 源图；
- `[V]`：网络响应哈希、源包成员分类和零公开仓库/数据记录；
- `[O]`：原作者私有实现、published 分支差异的唯一原因和正式时间映射。
