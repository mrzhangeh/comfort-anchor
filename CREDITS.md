# 出处、致谢与第三方许可

本文件用于履行 **MIT 许可的署名要求**以及学术引用的出处说明。项目全部自研代码见
[`LICENSE`](LICENSE)（MIT）。整理时间：2026-11-05。

## 1. 合规声明

- 本项目的 Python 源码、文档、图形参数与渲染实现**均为原创**，**未复制、未移植、未改写**
  任何第三方项目的源码、着色器、图标或图片素材。
- 参照框的形状、密度、不透明度、中央透明区等设计，参考的是**公开发表的论文结论与实验参数**；
  论文中的事实、方法与结论不受著作权保护，但按学术规范在下文逐条列出出处。
- 因此本项目**不受** GPL / AGPL 等传染性许可约束，可整体采用 MIT 许可。
- `docs/cybersickness-evidence-review.html` 是本项目的循证整理文档，同样适用 MIT 许可；
  其中转述的每项研究结论均应引用**原始论文**，而非引用本文档。
- `preview.png`、`patterns.png` 以及报告中的示意图均由本项目代码程序化生成
  （`mock_game_frame()` / `pattern_sheet()`），**不含任何第三方游戏截图或美术素材**。
- 中文字形由运行环境的 Windows 系统字体（微软雅黑 / 黑体）渲染，
  **项目不分发任何字体文件**；对照表图片中的文字仅为运行时渲染结果。

## 2. 参照过但**未使用其源码**的软件项目

这些项目用于确认「同类工具提供哪些图形」「哪些做法不应照搬」，仅作设计参照：

| 项目 | 平台 / 许可 | 与本项目关系 |
|---|---|---|
| [Dot[9]](https://github.com/JGM-89/dot9) | Windows / **非开源**，README 与 NOTICE 声明 *not currently open source, no reuse license is granted* | 参考其「边缘点 / 分段地平线 / 柔和暗角」的图形分类；**未使用任何代码或素材**，其 Counter-Motion 仍在 roadmap |
| [Steady](https://github.com/AlexW-F/Steady) | macOS / **MIT** | 参考其 Frame / Dome / Grid 的图形命名与可调参数思路；未使用 Swift 源码 |
| [MotionAnchor](https://github.com/dituon/MotionAnchor) | Windows 等 / **AGPL-3.0** | 仅参考其插件式图形清单；**未使用源码**，故不触发 AGPL 义务；其部分插件随输入移动，与本项目「绝对静止」结论相反 |
| [PeripheralTeleportation](https://github.com/nietongyu/PeripheralTeleportation) | Unity VR / 以仓库声明为准 | Nie 2025 论文实现，用于核对「参照内容跟随物理运动、移除连续虚拟光流」的机制；未使用其 C# / Shader |
| [Granulated Rest Frames](https://github.com/ZacheryCao/Visually-Induced-Motion-Sickness-by-Granulated-Rest-Frames) | Unity VR / 以仓库声明为准 | Cao 2021 论文实现，用于核对颗粒尺寸与密度参数；未使用其代码 |

## 3. 运行时依赖与许可证全文

源码运行需要 Pillow；打包 exe 需要 PyInstaller。二者**不被复制到本仓库源码中**，
但打包产物内含其运行时组件，按各自许可要求在此注明并提供许可证全文：

| 依赖 | 版本（构建时） | 许可 | 许可证全文 |
|---|---|---|---|
| Python 3.13（含 tkinter / Tcl-Tk） | 3.13.5 | PSF License / Tcl-Tk License | <https://docs.python.org/3/license.html> |
| [Pillow](https://python-pillow.github.io/) | 12.0.0 | MIT-CMU（HPND，宽松许可） | [`docs/third-party/PIL-LICENSE.txt`](docs/third-party/PIL-LICENSE.txt) |
| [PyInstaller](https://pyinstaller.org/) | 6.16.0 | **GPLv2 + Bootloader Exception**（允许打包并分发任意许可的程序） | [`docs/third-party/PyInstaller-COPYING.txt`](docs/third-party/PyInstaller-COPYING.txt) |

> 关于 PyInstaller：单文件 exe 内含其 bootloader。依据官方 Bootloader Exception，
> 由此生成的程序可以采用本项目的 MIT 许可；分发时保留本文件与上述许可证全文即满足其要求。
> 本仓库**不提交** exe 二进制，仅通过 GitHub Releases 附带上述说明分发。

## 4. 主要学术参考文献

完整整理、效应量与证据分级见 [`docs/cybersickness-evidence-review.html`](docs/cybersickness-evidence-review.html)。

### 元分析与系统综述

1. Allison RS, Palmisano S. *Visual Factors in Cybersickness: A Literature Survey and Meta-Analysis.* Multisensory Research, 2025. [10.1163/22134808-bja10181](https://doi.org/10.1163/22134808-bja10181) — 97 项实验；周边视野限制与独立视觉背景为一致有效的两类视觉干预。
2. Ang S, Quarles J. *Reduction of cybersickness in head mounted displays use: A systematic review and taxonomy of current strategies.* Frontiers in Virtual Reality, 2023;4:1027552. [10.3389/frvir.2023.1027552](https://doi.org/10.3389/frvir.2023.1027552) — 判定只有静态参照框显著减晕。
3. Yildirim C. *Don't make me sick: investigating the incidence of cybersickness in commercial virtual reality headsets.* Virtual Reality, 2020;24(2):231–239. [10.1007/s10055-019-00401-0](https://doi.org/10.1007/s10055-019-00401-0)
4. Sundaram AM, et al. *From ancient roots to modern routes: a systematic review of ginger's anti-motion sickness efficacy...* 2026. [10.2478/aspr-2026-0001](https://doi.org/10.2478/aspr-2026-0001)

### 静止参照框 / 独立视觉背景（有效证据）

5. Prothero JD, Draper MH, Furness TA, Parker DE, Wells MJ. *The use of an independent visual background to reduce simulator side-effects.* Aviat Space Environ Med, 1999;70(3):277–283. [PMID 10102741](https://pubmed.ncbi.nlm.nih.gov/10102741/)
6. Cao Z, Jerald J, Kopper R. *Visually-Induced Motion Sickness Reduction via Static and Dynamic Rest Frames.* IEEE VR 2018:105–112. [10.1109/VR.2018.8446210](https://doi.org/10.1109/VR.2018.8446210) — 原文定义：*dynamic* 指不透明度随运动淡入淡出，参照框始终相对真实世界静止。
7. Cao Z, Grandi J, Kopper R. *Granulated Rest Frames Outperform Field of View Restrictors on Visual Search Performance.* Frontiers in Virtual Reality, 2021;2:604889. [10.3389/frvir.2021.604889](https://doi.org/10.3389/frvir.2021.604889) — **注意：该研究只测视觉搜索表现，未测晕动症**，不可作为减晕有效性证据。
8. Fernandes AS, Feiner SK. *Combating VR sickness through subtle dynamic field-of-view modification.* IEEE 3DUI 2016（最佳论文）.
9. Nie T, Pospick CH, Cantory V, et al. *Peripheral Teleportation: A Rest Frame Design to Mitigate Cybersickness During Virtual Locomotion.* IEEE TVCG, 2025. [10.1109/TVCG.2025.3549568](https://doi.org/10.1109/TVCG.2025.3549568) · [arXiv:2502.15227](https://arxiv.org/abs/2502.15227)
10. Baek M, Kim H. *Investigating the effects of density and opacity of rest frames for VR sickness reduction.* Virtual Reality, 2025;29:41. [10.1007/s10055-025-01116-1](https://doi.org/10.1007/s10055-025-01116-1) — 密度变化对减晕与临场感均无显著影响，是「低遮挡」设计的直接依据。
11. Chang EH, et al. *Effects of rest frames on cybersickness and oscillatory brain activity.* IEEE IWW-BCI 2013. [10.1109/IWW-BCI.2013.6506631](https://doi.org/10.1109/IWW-BCI.2013.6506631) — 两横两竖白线九宫格，n=22 EEG。
12. De Vries K, Smeets J, Bos J. *The effect of rest frames on cybersickness.* Eur J Transl Myol, 2025;35(s1):14486. [10.4081/ejtm.2025.14486](https://doi.org/10.4081/ejtm.2025.14486) — 主观「更稳定」的一帧对应更大症状下降，是提供多图形自选的依据。
13. Kim J, Park S, Park C, Lee S-U, Kim GJ. *Cybersickness Reduction Effects of Visual and Vestibular Player-Fixed Rest Frames.* IEEE TVCG, 2026. [10.1109/TVCG.2026.3747491](https://doi.org/10.1109/TVCG.2026.3747491) — 与重力竖直对齐的参照框才抑制症状累积。
14. Prothero JD, et al. US Patent 6,497,649, 2002 — 纯周边参照可能不如稍靠中央有效。

### 零结果 / 反例（同样重要）

15. Shi R, Liang H-N, Wu Y, Yu D, Xu W. *Virtual Reality Sickness Mitigation Methods: A Comparative Study in a Racing Game.* PACMCGIT, 2021;4(1). [10.1145/3451255](https://doi.org/10.1145/3451255) · [arXiv:2103.05200](https://arxiv.org/abs/2103.05200) — 头固定准星、FOV 收窄、景深模糊三者无显著差异。
16. Wienrich C, Obremski D, Israel JH. *Repeated experience or a virtual nose to reduce simulator sickness?* Entertainment Computing, 2022. [10.1016/j.entcom.2022.100514](https://doi.org/10.1016/j.entcom.2022.100514)
17. *Preregistered test of whether a virtual nose reduces cybersickness.* Cognitive Research: Principles and Implications, 2024. [10.1186/s41235-024-00593-3](https://doi.org/10.1186/s41235-024-00593-3) — 预注册复制，零结果。
18. Palmisano S, Kim J, et al. *Cybersickness in Head-Mounted Displays Is Caused by Differences in the User's Virtual and Physical Head Pose.* Frontiers in Virtual Reality, 2020. [10.3389/frvir.2020.587698](https://doi.org/10.3389/frvir.2020.587698)
19. Lin JJ-W, Duh HBL, Parker DE, Abi-Rached H, Furness TA. *Effects of field of view on presence, enjoyment, memory, and simulator sickness...* IEEE VR 2002:164–171. [10.1109/VR.2002.996519](https://doi.org/10.1109/VR.2002.996519)

### 反向光流（可选实验模式的依据）

20. Park SH, Han B, Kim GJ. *Mixing in Reverse Optical Flow to Mitigate Vection and Simulation Sickness in Virtual Reality.* CHI 2022. [10.1145/3491102.3501847](https://doi.org/10.1145/3491102.3501847) — 与画面光流反向的短线显著降低 VIMS，但高对比会分心。

## 5. 引用本项目

若在研究、文章或二次开发中使用本工具，建议同时引用原始论文（尤其是 1、6、10、13、20），并可如下引用本软件：

> mrzhangeh. *静锚 ComfortAnchor — Windows 桌面静止参照框叠加层* (v2.0.0).
> <https://github.com/mrzhangeh/comfort-anchor>. MIT License.

**请勿把本工具描述为经过临床验证的医疗手段**：项目本身未做对照临床试验，
README 中给出了用 FMS + SSQ 做被试内交叉 A/B 自测的协议。
