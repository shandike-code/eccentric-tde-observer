# ZO 2020 Fig. 6/7 原作者代码与数据请求及发送记录

> Status: **Sent / 已发送**。用户于 2026-08-30 明确授权；邮件已于北京时间
> 2026-08-30 15:36:25 从用户认可的 Google 账户发出，并在 `Sent Mail` 中核验。

导航：[[eccentric_tde_observer/docs/phase5b3d_public_source_availability_audit|Phase 5B3d 公开来源审计]] ·
[[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c 方程路径审计]]

## 建议收件信息

- To: `jxz224@psu.edu`；
- Subject: Request for numerical code/data behind Zanazzi & Ogilvie (2020) Figs. 6–7。

地址在发送当日由作者[个人主页](https://www.jjzanazzi.com/)和 Penn State 人员页交叉核验。[V]

## English draft

Dear Professor Zanazzi,

I am independently reproducing the eccentric-disc dynamics in Zanazzi & Ogilvie (2020),
including the 2022 Erratum. I can reproduce the analytic limits and obtain converged
solutions of the printed three-dimensional untwisted equations, but my fundamental
free-boundary branch does not reproduce the eigenfrequencies and eccentricity profiles
shown in Figs. 6 and 7.

To avoid inferring implementation details from digitized curves, would you be willing to
share any of the following materials used to produce Figs. 6/7?

1. The original numerical script, notebook, or minimal solver routine;
2. The raw eigenfrequency and eccentricity-profile arrays plotted in Figs. 6/7;
3. The exact dimensional and sign conventions, including the radius-ratio convention,
   adiabatic index, GR parameter, and two- versus three-dimensional Hamiltonian;
4. The implemented inner and outer free-boundary conditions;
5. Solver settings, continuation procedure, initial guesses, and software version.

For context, I have already tested the regular no-node continuation, multiple frequency
guesses, the full two-dimensional nonlinear Hamiltonian, and the literal appendix-sign
variant. I would preserve any shared files with their original provenance and would not
redistribute them without permission.

Thank you for considering this request.

Best regards,

Wei Tian Wang

实际发送版本还补充询问：共享材料是否允许归档到公开研究仓库，或应保持私有。[V]

## 发送回执

- From display name: `Wei Tian Wang`；
- To: `jxz224@psu.edu`；
- Subject: `Request for numerical code/data behind Zanazzi & Ogilvie (2020) Figs. 6–7`；
- Sent at: `2026-08-30 15:36:25 Asia/Shanghai`；
- Apple Mail 接受发送请求，随后在 Google `Sent Mail` 中按主题检索到同一邮件；
- 原始 Message-ID 不写入 Markdown；其 SHA-256 为
  `0a012f3cf490373974c4e3129a07aa58dba8f707b89dbfd3e63706e0a45b7407`。[V]

没有附带项目源文件、图、数据或未公开材料。[V]

## 发送检查

- 用户明确授权发送：通过；
- 收件地址和署名：通过；未声明未知单位；
- 不附带未公开项目文件：通过；
- 询问共享许可证与是否允许公开归档：通过；
- 收到材料后先做哈希与只读复现，不直接覆盖当前 ZO 源模型。

当前等待作者回复；在收到外部材料前，published Fig. 6/7 的复现状态不变。[O]
