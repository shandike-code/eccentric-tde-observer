# Obsidian 双链与讲义文档规范

## 1. Vault 与作用域

本项目的 Obsidian vault 根目录约定为：

`/Users/shandike/Downloads/8.3`

本次知识结构只纳入：

- `eccentric_tde_observer/README.md`；
- `eccentric_tde_observer/docs/*.md`；
- `eccentric_tde_observer/lecture/*.md`；
- `markdown_papers/*.md`；
- 与本项目直接相关的 `deep-research-report/deep-research-report.md`。

同级的其他观测处理项目、虚拟环境、许可证和 pytest cache 不属于本理论建模讲义。

## 2. 链接格式

统一使用从 vault 根目录出发、不带 `.md` 后缀的完整路径和中文别名：

```markdown
[[eccentric_tde_observer/docs/phase3_complete|第三阶段完成说明]]
[[markdown_papers/2009.06636v2|Zanazzi 与 Ogilvie 2020]]
```

不用只有文件名的短链，避免未来出现同名文件时歧义。图片和 CSV/JSON/NPZ 不是 Obsidian
笔记，使用相对 Markdown 路径或代码块中的路径。

## 3. 页面角色

- **讲义页**：解释概念和因果链，必须给出前置知识、输入、输出、适用域和失败症状；
- **阶段页**：记录某阶段的方程、实现、验证、数值结论和边界；
- **论文原文页**：本地转换的论文全文，作为只读叶节点；不为了双链而改写原文；
- **索引页**：保证每个纳入作用域的 Markdown 至少有一条入链，并说明它在项目中的角色；
- **研究路线页**：区分可立即执行、需要外部数据/软件、长期开放问题。

## 4. 证据标签

每个实质性结论使用以下标签之一：

- `[L]`：可在链接论文或标准教材中核对；
- `[A]`：本项目新增闭合或诊断定义；
- `[V]`：由当前代码、测试或输出文件验证；
- `[O]`：未解决，不得写成模型预言。

同一句同时依赖文献和新闭合时写成 `[L/A]`。代码跑出的数字必须给出对应阶段页或报告路径。

## 5. 公式、单位和变量

- vault 文件和项目聊天都需要数学定界符才能正确渲染；聊天回复的发送前检查见
  [[eccentric_tde_observer/docs/chat_output_standard|项目聊天输出规范]]。本节另外约束写入
  Obsidian vault 的文件格式。
- Markdown 正文内的小公式和变量统一写成 `$...$`；独立的大公式统一写成上下各自独占一行的
  `$$...$$` 公式块；
- 希腊字母使用带反斜杠的 LaTeX 命令，例如 `$\Sigma$`、`$\tau$`、`$\kappa$`、`$\nu$`；
  不能在数学环境内写 `$Sigma$`、`$tau$`、`$kappa$` 或 `$nu$`；
- 整体下标用大括号分组，描述性下标用直立体，例如 `$T_{\rm eff}$`、`$z_{\rm ph}$`、
  `$F_{\nu,\rm obs}$`；不写 `$T_eff$`、`$T_{eff}$` 或 `$F_nu_obs$`；
- 不使用反斜杠圆括号或反斜杠方括号作为公式定界符，也不在同一 vault 中混用多套语法；
- 大公式块前后各留一个空行；`aligned`、`cases`、矩阵和多行推导只能放在 `$$` 内；
- 代码围栏中的美元符号按代码字面量处理，不参与数学渲染；正文中的货币美元符号写成
  `\$`；
- 公式出现前先定义变量；
- 所有有量纲量第一次出现时给 cgs 单位；
- 明确区分 $a$、局域 $r$、$E$、$\varpi$、observer azimuth；
- 明确区分真实 $F_{\nu}$、各向同性等效 $L_{\nu}$ 和双面本征光度；
- 明确区分 $\Sigma$ 与 Davis--Hubeny 的 $m_{0}=\Sigma/2$；
- 明确区分 $Q_{\rm tidal}$ 与动态柱的 $Q_{\rm pressure}$；
- 形式 Wien 尾、理想带通和真实仪器响应不得混称。

## 6. 导航要求

- 总入口为 [[eccentric_tde_observer/lecture/项目讲义/README|项目讲义入口]]；
- 全文件覆盖检查见 [[eccentric_tde_observer/lecture/项目讲义/00_document_map|Markdown 文档地图]]；
- 讲义正文必须从宏观问题到源模型、闭合、转移、验证、结果和开放问题顺序展开；
- 论文原文保持只读，通过文档地图和讲义正文产生反向链接。
