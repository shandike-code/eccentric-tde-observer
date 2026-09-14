# 第五阶段预备文献包：来源、用途与验收

本页是下一步“模型到真实观测量”工作的文献入口。它只回答三件事：文件从哪里来、将在
哪一环使用、转换质量达到什么程度。它不把论文观点提前写成本项目已经验证的结论。

## 1. 文件状态

- [V] 已下载 14 份 PDF，共 416 页；14 项 SHA-256 复算全部通过。校验清单见
  [SHA256SUMS](../../pdf_papers/phase5/SHA256SUMS)。
- [V] Claude 已调用 MinerU 网页 API，逐篇生成 14 份 Markdown 和 313 张正文实际引用的
  本地图像；详细记录见 [[markdown_papers/phase5_conversion_report|Phase 5 MinerU 转换报告]]。
- [V] Codex 独立检查图片路径、空文件、公式定界符、HTML 表格标签，并回到源 PDF 修复了
  Guolo et al. Table 7 的末段截断。
- [A] 下表的“项目用途”是研究路线中的用途分配，不等于论文已经证明裸偏心盘模型成立。

## 2. 逐篇入口

| 文献与公开来源 | 本地源 PDF | 本地 Markdown | 项目中的具体用途 |
|---|---|---|---|
| [Hogg 1999, arXiv:astro-ph/9905116](https://arxiv.org/abs/astro-ph/9905116) | [PDF](../../pdf_papers/phase5/astro-ph_9905116_Hogg_distance_measures.pdf) | [[markdown_papers/astro-ph_9905116_Hogg_distance_measures|Distance measures in cosmology]] | 5A：定义 $D_{\rm L}$、红移频率和观测者谱通量；防止混淆 $F_{\nu}$、$L_{\nu}$ 与 $\nu F_{\nu}$。 |
| [Poole et al. 2008, arXiv:0708.2259](https://arxiv.org/abs/0708.2259) | [PDF](../../pdf_papers/phase5/0708.2259_Poole_Swift_UVOT_calibration.pdf) | [[markdown_papers/0708.2259_Poole_Swift_UVOT_calibration|Swift/UVOT photometric calibration]] | 5A：把理论 $F_{\nu}$ 卷积为 UVOT 光子计数、零点和有效波长。 |
| [Breeveld et al. 2011, arXiv:1102.4717](https://arxiv.org/abs/1102.4717) | [PDF](../../pdf_papers/phase5/1102.4717_Breeveld_updated_UVOT_calibration.pdf) | [[markdown_papers/1102.4717_Breeveld_updated_UVOT_calibration|Updated UVOT calibration]] | 5A：补入紫外有效面积修订和长期灵敏度变化。 |
| [Fitzpatrick 1998, arXiv:astro-ph/9809387](https://arxiv.org/abs/astro-ph/9809387) | [PDF](../../pdf_papers/phase5/astro-ph_9809387_Fitzpatrick_extinction.pdf) | [[markdown_papers/astro-ph_9809387_Fitzpatrick_extinction|Interstellar extinction correction]] | 5A：将银河消光写成明确的前景观测算子，并传播消光曲线不确定度。 |
| [Schlafly & Finkbeiner 2011, arXiv:1012.4804](https://arxiv.org/abs/1012.4804) | [PDF](../../pdf_papers/phase5/1012.4804_Schlafly_Finkbeiner_reddening.pdf) | [[markdown_papers/1012.4804_Schlafly_Finkbeiner_reddening|Dust-map recalibration]] | 5A：约束银河系 $E(B-V)$ 的重标定；它不替代宿主星系消光模型。 |
| [VanderPlas 2017, arXiv:1703.09824](https://arxiv.org/abs/1703.09824) | [PDF](../../pdf_papers/phase5/1703.09824_VanderPlas_Lomb_Scargle.pdf) | [[markdown_papers/1703.09824_VanderPlas_Lomb_Scargle|Understanding the Lomb–Scargle periodogram]] | 5A：在不规则采样下检验进动周期；显式处理窗口函数、混叠与假警报。 |
| [Stone & Loeb 2016, arXiv:1510.04879](https://arxiv.org/abs/1510.04879) | [PDF](../../pdf_papers/phase5/1510.04879_Stone_Loeb_Lense_Thirring_TDE.pdf) | [[markdown_papers/1510.04879_Stone_Loeb_Lense_Thirring_TDE|Lense–Thirring precession in TDEs]] | 5B：区分节点进动与 ZO 模型已有的盘内拱点进动，建立可比较时标。 |
| [Pasham et al. 2024, arXiv:2402.09689](https://arxiv.org/abs/2402.09689) | [PDF](../../pdf_papers/phase5/2402.09689_Pasham_Lense_Thirring_TDE.pdf) | [[markdown_papers/2402.09689_Pasham_Lense_Thirring_TDE|AT2020ocn X-ray variability]] | 5B/5C：真实 X-ray 时序中进动候选信号的案例和采样要求；不是当前裸盘的拟合目标。 |
| [Yao et al. 2023, arXiv:2303.06523](https://arxiv.org/abs/2303.06523) | [PDF](../../pdf_papers/phase5/2303.06523_Yao_ZTF_TDE_demographics.pdf) | [[markdown_papers/2303.06523_Yao_ZTF_TDE_demographics|ZTF TDE demographics]] | 5C：定义 optical 选择样本、选择函数与宿主量，防止把单事件当成人口结论。 |
| [Guolo et al. 2023, arXiv:2308.13019](https://arxiv.org/abs/2308.13019) | [PDF](../../pdf_papers/phase5/2308.13019_Guolo_Xray_selected_TDEs.pdf) | [[markdown_papers/2308.13019_Guolo_Xray_selected_TDEs|X-ray properties of optically selected TDEs]] | 5C：为 $L_{\rm X}/L_{\rm opt}$、X-ray 温度和状态变化提供人口级比较量。Table 7 末段已另做 PDF 审计。 |
| [Patra et al. 2022, arXiv:2206.09039](https://arxiv.org/abs/2206.09039) | [PDF](../../pdf_papers/phase5/2206.09039_Patra_AT2019qiz_spectropolarimetry.pdf) | [[markdown_papers/2206.09039_Patra_AT2019qiz_spectropolarimetry|AT2019qiz spectropolarimetry]] | 5C：低偏振事件对散射光球形状的约束。自动下载期刊版受站点拦截，本地采用公开 arXiv submitted version。 |
| [Leloudas et al. 2022, arXiv:2207.06855](https://arxiv.org/abs/2207.06855) | [PDF](../../pdf_papers/phase5/2207.06855_Leloudas_asymmetric_electron_scattering_photosphere.pdf) | [[markdown_papers/2207.06855_Leloudas_asymmetric_electron_scattering_photosphere|Asymmetric electron-scattering photosphere]] | 5C：AT2018dyb、AT2019azh、AT2019dsg 的光谱偏振、谱线去偏振和时间演化；作为裸盘与扩展散射光球的区分诊断。 |
| [Liodakis et al. 2022, arXiv:2208.14465](https://arxiv.org/abs/2208.14465) | [PDF](../../pdf_papers/phase5/2208.14465_Liodakis_AT2020mot_polarization.pdf) | [[markdown_papers/2208.14465_Liodakis_AT2020mot_polarization|AT2020mot polarization]] | 5C：强且随时间变化偏振的对照案例，用来检验裸盘角分布而非反推自由盘风。 |
| [Hubeny & Hubeny 1998, arXiv:astro-ph/9804288](https://arxiv.org/abs/astro-ph/9804288) | [PDF](../../pdf_papers/phase5/astro-ph_9804288_Hubeny_NLTE_vertical_structure.pdf) | [[markdown_papers/astro-ph_9804288_Hubeny_NLTE_vertical_structure|NLTE disk vertical structure]] | 5D/5E：从当前动态柱—annulus 接口走向自洽 NLTE 垂向大气和连续边。 |

## 3. 使用边界

1. [V] Markdown 是可搜索、可双链的阅读副本，不是逐字符权威数据源。
2. [A] 进入代码的滤波响应、表格数字、消光系数或观测样本值，必须回到 PDF 或机器可读官方数据核对。
3. [O] 这批文献尚未解决 ZO 动态柱如何唯一映射到 NLTE 大气，也没有证明某个观测周期必然是拱点或节点进动。
4. [O] 真实 UVOT 响应曲线、Swift/XRT 响应矩阵和事件级时序数据仍需在实现对应观测算子时单独取得并做版本记录。
