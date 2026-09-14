# 项目聊天输出规范：中文说明与客户端原生数学排版

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/code_conventions|代码与 Markdown 规范]] ·
[[eccentric_tde_observer/docs/obsidian_linking_standard|Obsidian 双链与讲义文档规范]]

## 1. 适用范围

本规范适用于围绕本项目的 Codex、Claude 或其他助手聊天回复。聊天框使用客户端提供的
原生数学排版，不要求助手在可见回复中刻意展示美元符号定界符。若一个公式用普通文字和
Unicode 符号已经足够清楚，优先采用这种写法；较长推导则使用客户端默认的公式块。

项目 Markdown 文件仍必须使用 `$...$` 和 `$$...$$`，并同时受
[[eccentric_tde_observer/docs/code_conventions|代码与 Markdown 规范]]和
[[eccentric_tde_observer/docs/obsidian_linking_standard|Obsidian 规范]]约束。

## 2. 聊天与文件必须分开处理

- 聊天回复使用 GPT 客户端默认排版，不把 `$...$`、`$$...$$` 当作需要向用户强调或展示的
  输出规范；
- 聊天中的短量优先写成清楚的自然文本，例如“有效温度 T_eff”“频移因子 g”；必要时用
  Unicode 符号，例如 Σ、μ、ν 和 Φ；
- 长公式使用客户端默认的独立公式显示方式，不用代码围栏，也不把 LaTeX 源码直接裸露给
  用户；
- 写入仓库的 Markdown 与聊天不同：文件内仍严格使用 `$...$`、`$$...$$`，否则 Obsidian
  不能稳定渲染。

## 3. 符号、上下标与单位

- 聊天中优先用已正确显示的希腊字母，不输出裸露的 `\Sigma`、`\mu`、`\nu` 或 `\Phi`；
- 聊天里若用纯文本下标，采用可读名称，例如 `T_eff`、`F_nu,obs`，不伪装成已经渲染的
  LaTeX；
- 项目 Markdown 中的希腊字母、整体下标、直立描述性上下标和单位仍按
  [[eccentric_tde_observer/docs/code_conventions|代码规范]]严格书写；
- 同一回复内符号保持一致，并在首次出现时给出中文含义。

## 4. 说明公式的顺序

1. 先用中文说明公式回答的问题；
2. 再用客户端原生排版给出公式；
3. 随后解释新出现的符号、单位、物理作用和适用域；
4. 复杂推导分步写，不把多个等号、积分和条件挤进一句普通文本；
5. 区分 `[L]`、`[V]`、`[A]` 和 `[O]`，不得用排版完整掩盖物理尚未闭合。

## 5. 正误示例

错误写法会把 LaTeX 源码直接暴露在聊天中：

```text
I_line(T_eff, m_0, Q, F_nu^incident, mu_incident, ...)
F_line = D^-2 integral_visible g^4 I_line dA_image
```

聊天中的正确呈现应由客户端直接渲染局域线强度表，而不是强调定界符本身。下面的公式仅因
本页是项目 Markdown 文件，才按文件规范使用美元符号：

$$
\mathcal I_{\rm line}
\left(
T_{\rm eff},m_{0},Q,F_{\nu}^{\rm incident},
\mu_{\rm incident},\ldots
\right).
$$

再写观察者积分：

$$
F_{\rm line}
=\frac{1}{D^{2}}
\int_{\rm visible}
g^{4}\mathcal I_{\rm line}\,\mathrm dA_{\rm image}.
$$

## 6. 发送前检查

- 是否向用户暴露了裸反斜杠 LaTeX 命令；
- 短公式能否用自然文本或 Unicode 更清楚地表达；
- 大公式是否使用客户端原生的独立显示，而不是代码块；
- 公式是否紧邻中文解释，而不是只给符号；
- 文件路径、函数名和命令是否仍使用反引号；
- 若本轮同时修改项目 Markdown，文件中的公式是否仍严格使用 `$...$` 和 `$$...$$`。
