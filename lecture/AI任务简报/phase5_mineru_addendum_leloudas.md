# Claude–MinerU 补充任务：Leloudas et al. 2022

请只处理这一份 PDF：

`/Users/shandike/Downloads/8.3/pdf_papers/phase5/2207.06855_Leloudas_asymmetric_electron_scattering_photosphere.pdf`

必须调用 MinerU 网页 API 完成主体解析，不得用本地 OCR 或其他解析器冒充。输出到：

- `/Users/shandike/Downloads/8.3/markdown_papers/2207.06855_Leloudas_asymmetric_electron_scattering_photosphere.md`
- `/Users/shandike/Downloads/8.3/markdown_papers/2207.06855_Leloudas_asymmetric_electron_scattering_photosphere_images/`

要求与 [[eccentric_tde_observer/lecture/AI任务简报/phase5_mineru_conversion_brief|Phase 5 PDF 文献包与 MinerU 转换任务书]] 完全相同：保留标题、作者、摘要、正文、方法、附录/补充材料、致谢、参考文献、公式、表格、图和图注；图片必须为本地相对路径；不添加论文外解释。无法识别处用 `[OCR_UNCLEAR: ...]`。

请不要读取或输出任何本地转换脚本的源代码、API token 或环境认证信息。可以调用既有 MinerU 技能和转换命令，但终端输出只能包含任务状态、输出路径、页数、图片引用数和已知转换问题。

完成后只在终端给出简短验收摘要；不要修改其他 13 篇 Markdown，也不要重写总转换报告，Codex 会独立验收并更新它。
