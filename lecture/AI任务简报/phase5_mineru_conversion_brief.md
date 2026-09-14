# Phase 5 PDF 文献包与 MinerU 转换任务书

## 1. 任务边界

把 `/Users/shandike/Downloads/8.3/pdf_papers/phase5` 中的 14 份 PDF **逐字转写**为
Markdown；不是摘要、综述、翻译或改写。必须由 Claude 调用 MinerU 的网页 API 完成主体
解析，使论文中的图、表、公式和图注尽可能保留。

输出目录为 `/Users/shandike/Downloads/8.3/markdown_papers`。每篇论文写成：

- `<PDF stem>.md`；
- `<PDF stem>_images/`，保存该篇 Markdown 实际引用的图片；
- Markdown 中使用相对图片路径，例如
  `![](1703.09824_VanderPlas_Lomb_Scargle_images/figure_1.png)`。

不要覆盖 `markdown_papers` 中已有的 12 篇论文；本批文件名与旧文件不重名。

## 2. 论文清单及项目用途

| PDF | 项目用途 | 阶段 |
|---|---|---|
| `astro-ph_9905116_Hogg_distance_measures.pdf` | 光度距离、红移后的谱通量定义 | 5A |
| `0708.2259_Poole_Swift_UVOT_calibration.pdf` | UVOT 有效面积、零点和光子计数标定 | 5A |
| `1102.4717_Breeveld_updated_UVOT_calibration.pdf` | UVOT 紫外标定更新和时间灵敏度 | 5A |
| `astro-ph_9809387_Fitzpatrick_extinction.pdf` | 消光曲线的物理与参数化 | 5A |
| `1012.4804_Schlafly_Finkbeiner_reddening.pdf` | 银河系尘埃图重标定与误差边界 | 5A |
| `1703.09824_VanderPlas_Lomb_Scargle.pdf` | 不规则采样周期分析、窗口函数与假警报 | 5A |
| `1510.04879_Stone_Loeb_Lense_Thirring_TDE.pdf` | TDE 节点进动，与 ZO 拱点进动分界 | 5B |
| `2402.09689_Pasham_Lense_Thirring_TDE.pdf` | AT2020ocn 的 X-ray 时域节点进动候选 | 5B/5C |
| `2303.06523_Yao_ZTF_TDE_demographics.pdf` | 光谱完备 optical TDE 人口和选择函数 | 5C |
| `2308.13019_Guolo_Xray_selected_TDEs.pdf` | optical/X-ray 相对强度的人口分布 | 5C |
| `2206.09039_Patra_AT2019qiz_spectropolarimetry.pdf` | 低偏振和近球形散射光球约束 | 5C |
| `2207.06855_Leloudas_asymmetric_electron_scattering_photosphere.pdf` | AT2019qiz 多历元偏振与非球对称电子散射光球 | 5C |
| `2208.14465_Liodakis_AT2020mot_polarization.pdf` | 强、时变偏振的对照事件 | 5C |
| `astro-ph_9804288_Hubeny_NLTE_vertical_structure.pdf` | 自洽 NLTE 垂向大气与连续边 | 5D/5E |

已有且继续使用、不要重复转换的 PDF 包括 ZO 2020、Ogilvie--Lynch 2019、两篇
Lynch--Ogilvie 2021、Davis--Hubeny 2006、Roth et al. 2016 和 Cunningham 1975。

## 3. MinerU 转换要求

1. 对每个 PDF 单独提交 MinerU；不要把多篇论文合成一个任务。
2. 下载并展开 MinerU 的完整结果包，保留 Markdown 与其实际引用的图片。
3. 正文顺序必须保持原论文页序；保留标题、作者、摘要、章节、附录、致谢和参考文献。
4. 对转换后写入文件的 Markdown，行间公式只用 `$$...$$`，并让开始与结束的 `$$` 各自
   独占一行；行内公式只用 `$...$`；不要混用其他公式定界符，也不要把公式截图当作唯一
   内容。聊天框中的公式另遵守
   [[eccentric_tde_observer/docs/chat_output_standard|项目聊天输出规范]]。
5. 图和表必须保留编号与图注。若 MinerU 只给出整页截图，不得声称“图片提取成功”。
6. 不要把页眉、页脚、页码和双栏阅读顺序混入连续正文。
7. 不添加论文没有的科学解释；无法识别的字符用明确的 `[OCR_UNCLEAR: ...]` 标记。
8. 每完成一篇，检查 Markdown 中的每个相对图片路径确实存在。
9. 不允许用空白占位图、远程临时 URL 或 base64 代替本地图片。
10. 如果 MinerU API、登录、额度或下载失败，不使用其他 OCR 冒充 MinerU；记录失败原因后继续下一篇。

## 4. 转换报告

完成后写入
`/Users/shandike/Downloads/8.3/markdown_papers/phase5_conversion_report.md`，逐篇记录：

- PDF 文件名；
- PDF 页数；
- MinerU 任务是否成功；
- Markdown 文件名；
- 提取图片数量与 Markdown 图片引用数量；
- 是否发现 `[OCR_UNCLEAR]`；
- 公式、双栏、表格或参考文献的已知问题；
- 若失败，准确错误信息和可重试建议。

最终只报告真实完成状态；不能因为生成了 `.md` 文件就把转换质量写成通过。
