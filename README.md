# 静锚 ComfortAnchor v2

Windows 桌面「静止参照框」叠加层，辅助缓解 3D 电脑游戏的晕动症（晕 3D / cybersickness / VIMS）。

**它是舒适辅助工具，不是医疗设备，也不宣称能治疗或预防恶心呕吐。** 出现症状请立即停止游戏并休息。

> 许可：[MIT](LICENSE) · 出处与致谢：[CREDITS.md](CREDITS.md) · 循证报告：[docs/cybersickness-evidence-review.html](docs/cybersickness-evidence-review.html)（含 2026-11-05 补充核查章节） · 可执行程序：[Releases](https://github.com/mrzhangeh/comfort-anchor/releases/latest)

---

## 一、v2 改了什么

| 反馈 | 处理 |
|---|---|
| ① 控制面板显示不全 | 改为 **可滚动画布 + 固定底栏**，按系统 DPI（实测 168 dpi / 175%）缩放字体、间距与窗口；实测 959×1460 下所有分区、状态栏、热键提示与按钮**完整可见、无需滚动**。小屏或更高缩放仍可滚动，底栏永远不会被挤掉。 |
| ② 点不随鼠标/手柄轻微移动，是不是移动更好 | **查证后结论是否定的，默认仍为绝对静止**；但把「动态」做成了 3 个可选实验模式并标明证据等级。关键澄清见下节。 |
| ③ 点导致画面下降、遮挡游戏信息 | 默认改为「**无标记 + 1px 静止边框 + 四角刻线**」；颗粒密度比 v1 低一个数量级；新增 **11 种参照图形**、**中央透明区**、**四角 HUD 避让区**、**暗角默认关闭**。实测默认档平均 alpha **0.120/255**、有效墨迹覆盖 **0.44%** 像素、中央 alpha 恒为 0。 |

---

## 二、关于「移动中的点」：一次证据澄清

上一版报告把「绝对静止」写成无例外原则，并误把 Cao 2018 标题里的 *dynamic rest frames* 理解成「可移动的参照物」。核对原文后需修正：

> **Cao 2018 的 dynamic 指「不透明度随视觉运动强度淡入淡出」，金属网本身始终相对真实世界静止，不随头部或虚拟运动移动。** 而且 Ang & Quarles 2023 系统综述明确：*Only the static variant was shown to reduce cybersickness*。动态版虽让被试多走航点，但未验证与静态版等效。

| 做法 | 证据 | 结论 |
|---|---|---|
| 屏幕空间完全静止（与真实房间对齐） | Prothero 1999；Cao 2018 静态版；Allison & Palmisano 2025 元分析 | **默认，证据最强** |
| 参照内容跟随**物理头部运动**，同时移除虚拟镜头的连续周边光流 | Nie 2025, IEEE TVCG, N=90，显著优于黑色 FOV 遮罩 | VR 有效；**桌面屏幕本身物理静止，静态叠加层已等价满足** |
| 参照物跟随**虚拟镜头 / 鼠标同向移动** | Buhler 2018「Circle effect」引入不想要的光流，N=18 无显著差异；以 2 倍速度远离的光球亦无效 | **无证据，可能加重** |
| 不透明度随运动强度变化（Cao 2018 的 dynamic） | 44 人两项多日研究；只有静态版在实时舒适度上显著 | 部分支持，适合作为减少常驻遮挡的折中 |
| **反向光流**（与画面光流方向相反的短线段） | Park, Han & Kim, CHI 2022：显著降低 VIMS；仅高对比时才明显分心 | 有正向证据，需低对比、小幅度；桌面外推未验证 |

**一句话：关键不是「动不动」，而是「跟谁动、往哪动」。** 桌面玩家身体物理静止，鼠标/手柄驱动的是虚拟镜头；把参照物绑到虚拟镜头上等于添加额外光流。Dot[9] 把 Counter-Motion / Motion Echo 列在 roadmap 并注明「beyond 1.0」，MotionAnchor 有 motion-responsive 插件，两者都没有有效性验证。

另外 De Vries 2025 发现：head-fixed 与 earth-fixed 参照框的症状水平相似，但**被试主观认为「更稳定」的那一帧对应更大的症状下降**。这直接支持「多给几种形状让用户自己挑」，而不是替所有人定死一种。

### 实现的可选运动模式（全部默认关闭）

| 模式 | 做什么 | 证据等级 |
|---|---|---|
| `static` 绝对静止 | frame 层与 marks 层都固定 | 循证推荐（默认） |
| `adaptive` 明度自适应 | 用只读的鼠标位移 / WASD 估计运动强度，marks 层不透明度随之淡入淡出；静止时几乎不可见 | 与 Cao 2018 的 dynamic 定义一致，但只有静态版显著 |
| `counter` 反向光流微动 | marks 层朝画面光流反方向做 ≤12px 平滑位移 | Park 2022 思路，实验性 |
| `follow` 同向跟随微动 | marks 层与画面光流同向微移 | **无证据，不推荐**，仅供 A/B 对照自测 |

**架构上分两层**：`frame` 层（暗角 / 1px 边框 / 四角刻线 / 地平线 / 准星）**永远绝对静止**；只有 `marks` 层可淡入淡出或微动。即使开了实验模式，与重力对齐的主参照框也不会动。明度自适应与微动通过 `BLENDFUNCTION.SourceConstantAlpha` 和 `pptDst` 实现，**不重新渲染、不重新分配位图、不逐帧重绘**。

> raw input 且锁定光标的 FPS 游戏里 `GetCursorPos` 可能不变，此时退化为 WASD / 方向键估计，微动方向会不准。这是已知局限，不会为了取数据去 hook 或注入输入。

---

## 三、11 种参照图形

面板「② 参照图形」下拉切换，右侧有实时预览；游戏中 `Ctrl+Alt+P` 逐个试。`patterns.png` 是全部图形的对照表（刻意调高可见度以便比较）。

| ID | 名称 | 依据 / 特点 |
|---|---|---|
| `none` | 无标记（仅 1px 细边框） | **默认**。零遮挡，先确认会不会分心 |
| `dots` | 稀疏圆点 | Cao 2021 颗粒化参照框的桌面近似。注意该论文**只测视觉搜索、未测晕动症** |
| `rings` | 空心圆环 | 同密度下墨迹面积远小于实心点 |
| `crosses` | 小十字 | 水平/垂直双向线段，强化重力方向（Kim 2026） |
| `grid` | 细网格 / 金属网 | Cao 2018 see-through metal mesh、Chang 2013 静态网格、Baek 2025 mesh RF |
| `lines` | 两横两竖（九宫格） | Chang 2013, n=22 EEG 实验用的极简网格，像素占用最低 |
| `ticks` | 四边短刻度 | 借鉴 Dot[9] side-tick 风格 |
| `horizon` | 分段地平线 | 水平线是最强的「主观竖直」提示，中央断开避免挡准星 |
| `dome` | 椭圆穹顶 + 地平线 | 借鉴 Steady 的 Dome |
| `radial` | 边缘径向刻度 | 只在最外圈提供方位参照 |
| `clouds` | 柔和云状自然参照 | Lin 等报告自然 IVB 在恶心评分上优于纯网格；探索性选项 |

**低遮挡设计**：Baek & Kim 2025 发现参照框密度变化对减晕与临场感**均无显著影响**，并把中央 120°×60° 设为 mesh-free；因此在效果相近时应优先选遮挡最少的配置。本工具用 `coverage_mask` 统一裁掉中央椭圆与四角 HUD 矩形（小地图 / 技能栏），边界做柔化，所有形状共用。暗角默认关闭——它是「画面发灰」的主要来源之一。

---

## 四、运行

### 直接用 exe

从 [GitHub Releases](https://github.com/mrzhangeh/comfort-anchor/releases/latest) 下载 `ComfortAnchor.exe`，双击即可，无需安装、无需 Python。配置在 `%APPDATA%\ComfortAnchor\settings.json`；v1 配置会自动迁移（重点把过密颗粒降下来）。

也可以按下方「打包」步骤在本机自行构建，产物为 `dist/ComfortAnchor.exe`。仓库**不提交**二进制文件。

### 源码运行
```bash
pip install -r requirements.txt
python comfort_anchor.py
```

### 命令行
```bash
python comfort_anchor.py --selftest --out preview.png   # 低遮挡指标 + 全部图形渲染自检
python comfort_anchor.py --sheet   --out patterns.png  # 生成 11 种图形对照表
python comfort_anchor.py --check   --out check.txt      # 端到端：渲染 + 两层分层窗口 + 淡化/微位移
python comfort_anchor.py --uicheck --out ui.txt         # 构建完整控制面板 + 实时预览
python comfort_anchor.py --version

# 打包后验证 exe 内部路径（--windowed 无控制台输出，故写文件）
dist\ComfortAnchor.exe --check   --out check_exe.txt
dist\ComfortAnchor.exe --uicheck --out ui_exe.txt
```

### 打包
```bash
python build_exe.py
# 或双击 build_exe.bat
```
产物 `dist/ComfortAnchor.exe`，单文件、无控制台窗口。仅依赖标准库 tkinter + Pillow + PyInstaller，打包时排除 numpy / psutil / requests 等无关依赖。

---

## 五、使用

**热键**（只读按键状态，不拦截、不注入）
- `Ctrl+Alt+D` 开关叠加层
- `Ctrl+Alt+S` 显示 / 隐藏面板
- `Ctrl+Alt+P` 切换下一个参照图形
- `F9` 紧急关闭

**预设**：极简（默认，近乎零遮挡）→ 柔和（稀疏圆点）→ 标准（细网格 + 微暗角）→ 增强。建议从极简玩 10 分钟，觉得完全没感觉再逐级升；若觉得分心，先降「标记不透明度」而不是堆密度。滑杆有 170ms 防抖。

**游戏设置优先级（比叠加层更重要，见循证报告）**
1. 关闭头部摆动 / 镜头晃动 / 武器摇摆 / 动态模糊
2. 降低镜头灵敏度、关闭鼠标加速度
3. FOV 与屏幕距离匹配（16:9 桌面 90–100° 水平起步，每次只调 5°）
4. 锁定稳定帧率（稳定 60 优于波动 80–120）
5. 开灯 / 显示器背光、坐远、窗口化，让真实房间进入余光（天然 IVB）
6. 每日短时、症状出现前就停的渐进习惯化
7. 最后才是本工具这类周边视觉干预

---

## 六、验证结果（本机 Python 3.13.5 / Pillow 12.0 / 2560×1600 @175%）

```
py_compile                 OK（4 个模块）
--selftest                 PASS
  minimal   mean alpha 0.120   有效墨迹 0.44%   中央 0.000
  gentle    mean alpha 0.135   有效墨迹 0.51%   中央 0.000
  standard  mean alpha 4.833   有效墨迹 3.61%   中央 0.000
  strong    mean alpha 11.703  有效墨迹 40.59%  中央 0.000
  patterns rendered 11/11
--check                    render OK all 11 patterns / layered windows OK (frame + marks, fade + offset)
UI 构建                    959×1460，scrollregion 1197 < canvas 1246 → 无需滚动，底栏完整
```

修复过程中确认并处理了：v1 未声明 DPI 感知时显示器被报成 1463×914（现已正确识别 2560×1600）；v1 固定 `520x690` + `resizable(False)` 导致底部控件被截断（现为可滚动 + 固定底栏 + DPI 缩放字体）；v1 颗粒候选点约上万个（现为百级）。

---

## 七、自测是否真的有效

不要靠「感觉好像好点」下结论——重复暴露本身会习惯化，很容易骗出假阳性。

1. 被试内交叉设计，20–30 人；开 / 关条件顺序完全平衡（2024 复制研究里第一场 FMS 显著更高，η²=.419）。
2. 每条件等长暴露（如 12 分钟），每 2 分钟记一次 **FMS**（0–20），前后各填一次 **SSQ**，记录因不适提前退出的时间。
3. 同时记录任务表现与主观分心程度，确认不是靠「把画面挡住」换来的。
4. 比较不同图形 / 运动模式时，一次只改一个变量，并按 De Vries 2025 额外记录「你觉得哪个参照最稳定」。
5. 跨多日重复，把习惯化作为协变量；报告效应量与置信区间，而不是只报 p 值。

---

## 八、安全、隐私与反作弊

- **不注入游戏、不 hook 内存/输入、不读取显存、不截屏、不联网、无遥测、无自动更新。** 叠加层只是操作系统层面的透明窗口，与游戏进程零交互。
- 热键与运动估计只用 `GetAsyncKeyState` / `GetCursorPos` **只读轮询**（热键 110ms、运动 50ms），不安装全局钩子、不拦截也不注入输入。多人竞技游戏对任何第三方叠加工具都可能有自己的规则，使用前请自行确认条款。
- 游戏请设为**无边框 / 窗口化全屏**；独占全屏可能绘制在叠加层之上。
- 若游戏以管理员权限运行而本工具不是，叠加层可能被盖住；用相同权限启动。
- 声明了 DPI 感知，高缩放屏按物理像素精确覆盖；可下拉选择具体显示器。
- 出现恶心、头晕、出汗、定向障碍时按 `F9` 关闭并停止游戏。频繁呕吐或平时乘车也常发作，应当前往耳鼻喉 / 神经内科做前庭与偏头痛评估。

---

## 九、已知局限

- 绝大多数参照框 RCT 在 VR 头显完成，**桌面显示器专门证据稀薄**；桌面已有真实房间作天然参照，边际收益可能小于 VR。
- 只对「视觉参照」一个环节起作用，不能替代关镜头晃动、调 FOV、锁帧率等更确定的措施；只能**预防 / 延缓症状累积**，不能缓解已发作的恶心呕吐。
- `adaptive` / `counter` / `follow` 三个运动模式**均未经临床验证**，其中 `follow` 有明确的零结果先例。默认与推荐值永远是 `static`。
- 采用 raw input 并锁定光标的游戏里，运动强度只能靠键盘估计，方向不可靠；`adaptive` 的淡入淡出仍可用，`counter` / `follow` 可能形同关闭。
- 无托盘图标（热键召回面板代替）；暂不支持「同时覆盖所有显示器」的独立渲染。
- 本项目**未做临床对照试验**，README 第七节给出的是自测协议而非有效性结论。

---

## 十、文件

```
comfort-anchor/
├── comfort_anchor.py     主程序：控制面板 / 热键 / 运动循环 / CLI
├── ca_config.py          配置模型：默认值、预设、v1→v2 迁移、值域校验
├── ca_render.py          渲染层：11 种图形、覆盖率掩码、两层位图、对照表
├── ca_win32.py           Win32：分层窗口（缓存 DIB）、显示器枚举、只读输入采样
├── build_exe.py          PyInstaller 打包脚本
├── build_exe.bat         Windows 双击打包
├── requirements.txt      Pillow + PyInstaller（tkinter 为标准库）
├── README.md             本文件
├── LICENSE               MIT 许可证
├── CREDITS.md            论文出处、致谢与第三方许可说明
├── .gitignore            构建产物 / 本机配置 / 凭证忽略规则
├── preview.png           叠加效果预览
├── patterns.png          11 种图形对照表
└── docs/
    ├── cybersickness-evidence-review.html   完整循证报告（自包含 HTML）
    └── third-party/                        Pillow / PyInstaller 许可证全文
```

`dist/ComfortAnchor.exe` 由 `build_exe.py` 本地生成，不纳入版本库，仅在 GitHub Releases 分发。

---

## 十一、开源协议与引用

本项目采用 **[MIT License](LICENSE)**：允许商用、修改、再分发，只需保留版权与许可声明。

- 全部源码为原创，**未复用** Dot[9]、Steady、MotionAnchor 或任何论文附带工程的源码，故不受 GPL / AGPL 传染；这些项目仅作图形与参数参照，已在 [CREDITS.md](CREDITS.md) 逐条标明。
- 设计所依据的 **20+ 篇论文（含 DOI）**、零结果反例，以及运行时依赖的许可（Pillow MIT-CMU、PyInstaller GPLv2 + Bootloader Exception，全文随仓库提供）同样列在 [CREDITS.md](CREDITS.md)。
- 文档与示意图适用同一 MIT 许可；其中转述的研究结论请引用**原始论文**，而非引用本项目。
- 引用本软件的推荐格式见 CREDITS.md 第 5 节。**请勿将本工具描述为经过临床验证的医疗手段。**

欢迎 Issue / PR；提交代码即表示同意以 MIT 许可贡献。
