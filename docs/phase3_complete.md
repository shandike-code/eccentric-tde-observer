# 第三阶段完成说明

## 最合理的第一步及完成范围

第三阶段没有从大规模 NLTE/Kerr 计算起步，而是依次关闭四个最靠近现有裸盘模型的缺口：

1. **3A 非灰失效门**：用低温 H/He LTE 连续吸收审计热化域，明确指出 NLTE 缺口；
2. **3B 角分辨局域辐射**：加入能量归一化的临边昏暗和未分辨 Stokes $I,Q,U$；
3. **3C 像平面传递**：建立 Cunningham 式 $dA_{\rm image} × g^3 I_{\nu}/g$ 接口，并在当前弱场
   用 Schwarzschild 直接像近似实现；
4. **3D 再处理约束**：只给质量、光深、扩散、能量和动量下界，不加入自由风。

## 四类归属

### 1. 文献/ZO 已确定 `[L]`

- ZO 源场 $e(a), \varpi, \Sigma(a,E), j(a,E), H(a,E), T_{\rm eff}(a,E)$；
- Ogilvie--Lynch 偏心轨道几何与呼吸理论；
- $I_{\nu}/\nu^3$ 不变量、自由—自由吸收、Saha/LTE 基础式；
- Cunningham 的源面到观察者 transfer-function 分解；
- 半无限保守电子散射大气的 Chandrasekhar 偏振极限。

### 2. 本项目新增闭合 `[A]`

- 灰 Eddington $T(z)$ 上的低温 H/He Saha 连续谱审计；
- 基态配分函数、氢样 H I/He II 截面与可选 He I 近似；
- Eddington 临边昏暗、Chandrasekhar 偏振拟合；
- Beloborodov Schwarzschild 直接像关系与 Newtonian ZO 速度的弱场混合；
- modified-blackbody 局域谱仍沿用第二阶段的峰频热化闭合。

### 3. 代码验证的条件预言 `[V]`

- optical/UV $F_{\nu}(i,\phi_{\rm obs}-\varpi)$ 与光谱图；
- 保守频段 $T_{\rm bb}=1.788e4--2.086e4 K$，
  $R_{\rm bb}=5.84e13--2.27e14 cm$；
- $i=75^\circ$ 时的频率相关进动调制（$5e14 Hz$ 最大/最小约 $2.81$）；
- 当前角闭合下 $5e14 Hz$ 偏振约 $0.0013\%--5.95\%$；
- 弱场直接像对面积和光谱的增量；
- 任意未来再处理层必须满足的约束面。

这里“预言”均以采用的局域谱与角闭合为条件，不等同于已经拟合任何 TDE。

### 4. 未解决 `[O]`

- 低温、受辐照、含金属的 NLTE annulus atmosphere 与偏心有效重力表；
- X-ray 可用的局域源谱、Compton 化和高能内区；
- 吸收与磁场对偏振的影响及 GR 平行移动；
- Kerr 多像、时间延迟、曲线射线自遮挡；
- 真实再处理层的离化结构与动力学。由于高能种子谱未闭合，当前不加入风。

## 质量门结果

- 全套测试：`138 passed`（含原有阶段回归；最终数目以当前 pytest 输出为准）；
- observer 源网格收敛最大相对变化 $9.05e-4$；
- 无自遮挡参考源的自适应射线深度变化为零；
- 非灰垂向积分变化 $2.14e-5$，但源网格面积中位光深变化可达 $4.15\%$，故只作为
  失效门，不作为精密 NLTE 光谱；
- 禁止 `nan_to_num`、无依据裁剪和物理 floor；零通量偏振、视界内、超光速、像折叠等
  状态直接拒绝。

## 主产物

- 总图：`outputs/phase3_complete_summary.png`
- 总报告：`outputs/phase3_complete_report.json`
- 光谱/Stokes：`outputs/phase3_observer_spectra.csv`
- 观察方位：`outputs/phase3_orientation_diagnostics.csv`
- 非灰光深：`outputs/phase3_non_gray_thermalization.csv`
- 再处理约束：`outputs/phase3_reprocessing_constraints.csv`

运行命令：

```bash
uv run pytest -q
uv run python scripts/phase3_complete.py --output-dir outputs
```

## 下一科学判断

这组严格参考源没有直线自遮挡，弱场 GR 面积修正也很小；optical/UV 的强方位变化主要来自
非轴对称温度/厚度加上投影与角分布。裸盘能给出可检验的 optical/UV 调制与条件偏振预言，
但尚不能回答可信的 $L_{\rm X}/L_{\rm opt}$。下一步应是建立覆盖本项目低 $T_{\rm eff}$、$\Sigma$ 与偏心有效
重力的受辐照 NLTE annulus 表，而不是立即加入任意盘风。

