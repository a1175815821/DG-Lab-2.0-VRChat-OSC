<div align="center" id="top">
  <img width="200" src="images/logo.svg" alt="DG-Lab 2.0 Logo" />
</div>

<h1 align="center">DG-Lab 2.0 — VRChat OSC</h1>

<p align="center">
  <img alt="GitHub" src="https://img.shields.io/github/license/a1175815821/DG-Lab-2.0-VRChat-OSC?label=license">
  <img alt="GitHub repo size" src="https://img.shields.io/github/repo-size/a1175815821/DG-Lab-2.0-VRChat-OSC">
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/a1175815821/DG-Lab-2.0-VRChat-OSC">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/a1175815821/DG-Lab-2.0-VRChat-OSC?style=social">
  <img alt="GitHub release" src="https://img.shields.io/github/v/release/a1175815821/DG-Lab-2.0-VRChat-OSC">
</p>

<p align="center">
  将 DG-Lab Coyote 电刺激设备通过 OSC 协议接入 VRChat，让虚拟形象的触觉反馈传导到现实。<br/>
  基于 <a href="https://github.com/Sakura0721/osc-toys">Sakura0721/osc-toys</a> 二次开发，修复核心 Bug 并大幅增强体验。
</p>

---

## 目录

- [项目简介](#项目简介)
- [主要特性](#主要特性)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [架构说明](#架构说明)
- [版本历史](#版本历史)
- [常见问题](#常见问题)
- [安全警告](#安全警告)
- [致谢](#致谢)
- [许可证](#许可证)

## 项目简介

本项目运行一个本地 Web 服务（FastAPI + Next.js 静态前端），监听 VRChat 通过 OSC 协议发出的 avatar 参数（例如耳朵触摸探针 `EarLDis` / `EarRDis`），实时将数值映射为 DG-Lab Coyote 电刺激设备的输出强度，从而实现「虚拟形象被触碰 → 现实身体受电击」的反馈闭环。

适用于带有 `VRCContactReceiver`（Proximity 类型，输出 Float）参数的 VRChat 形象。

## 主要特性

### OSC 监听与设备解耦 ⭐

- **OSC 监听独立于设备连接**：应用启动即运行 OSC 监听服务，无需 Coyote 设备在手即可测试 VRChat 信号是否正常
- **OSC 地址热更新**：修改 OSC 地址无需断开设备，也**不会重建 UDP 监听 socket**，原地替换分发映射即可生效
- **OSC 链接状态实时显示**：首页 OSC 状态卡片显示服务运行状态、A/B 通道信号活跃度（绿/黄/灰三色指示）

### 信号映射修复

- 修复 `get_avg` 信号映射逻辑错误：原代码只有两档输出（min_power / 满档），现已实现 `start_limit → 0`、`min_limit → min_power`、`max_limit → 1.0` 之间的平滑线性插值
- 修复信号低于阈值时 `set_pwm(1, -1)` 应为 `0` 的问题（原代码会留下微弱持续输出）
- 修复 `start_limit` 配置项未被使用、阈值硬编码 `0.1` 的问题
- 修复 `power_multiplier` 配置失效问题（原硬编码 1.28，现读取 `settings.coyote_multiplier`）
- `can_update_power` 超时兜底：set_pwm 锁定超过 5 秒自动恢复，防止 signal() 异常后永久失效
- `set_pwm` 微调阈值从 2 改为 1，支持更精细的强度调节

### 强度范围对齐官方

DG-Lab Coyote 官方强度范围为 **0–200**，本项目已全面对齐：

- `set_pwm` 输入范围：0–200（safe_mode 启用时上限 100）
- 前端强度调节滑块：0–200，支持滑块拖动和数字直接输入
- 强度调整控件移至侧边栏，在任意页面都能直接调整

### OSC 地址自动获取

VRChat 会在 `%USERPROFILE%\AppData\LocalLow\VRChat\VRChat\OSC\` 下为每个 avatar 生成 OSC 配置 json。本项目新增 `/api/vrc/avatars` 接口读取该目录：

- 修复 BOM 编码问题：使用 `utf-8-sig` 读取 VRC 生成的 json 文件
- 修复参数地址解析：优先读取 `output.address`（完整 OSC 路径），而非 `name`
- 前端 Auto Fetch 按钮弹窗列出所有本地 avatar，仅显示 Float 类型参数
- 实时追踪当前穿戴的 avatar（通过 `/avatar/change` OSC 消息），回退到文件修改时间推测
- 如 OGB/Orf 开头的参数未在列表中出现，提示用户手动填写

### Patterns 波形可视化

- Patterns 卡片下方 Canvas 波形预览组件，每个 state（`[脉冲时长, 间隔, 幅度]`）以矩形高度直观呈现
- **静态预览**（去除了实时指针动画，减少视觉干扰）
- **Pattern 中文名映射**：23 个波形名称中文化（震动/脉冲/呼吸/波浪/武器冲击/场景专用等类别）

### 引导式新手指南 (Onboarding Wizard) 🧭

- **逐步骤引导**：连接设备 → 填写 OSC 地址 → 选择波形 → 调节强度
- 粒子动画欢迎页，渐入式交互，提升易用性
- 所有字段与 WebUI 设置实时同步，引导完成后自动进入主界面

### 实时 OSC 监控 (SSE)

- `/api/coyote/osc_stream` 服务端推送实时原始值、滑动平均、映射后输出比例
- 首页 OSC 状态卡片内嵌进度条展示 A/B 通道实时信号强度（raw / avg / mapped）
- 20 条消息历史循环记录，方便诊断 OSC 通讯是否正常
- OSC "运行中" vs "VRChat 已连接" 状态区分：收到信号前显示黄色等待，收到后变绿

### 强度倍增器生效

- 修复 `power_multiplier` 配置仅存储不生效的问题
- `set_pwm` 路径现也应用 multiplier：`power = min(200, max_power × s × multiplier)`
- 默认 multiplier 为 **1.0**（滑块与输出 1:1；可在 settings.yaml 中自行调整）

### UI 全面汉化与改进

- **全面汉化**：所有 UI 文案改为中文，包括导航、按钮、提示、状态等
- **深浅色主题切换**：右上角日/月图标按钮，选择持久化到 localStorage，首次访问跟随系统偏好
- 窗口默认尺寸 1280×820，不再霸占屏幕
- 修复侧边栏左下角文字不可见问题
- 侧边栏背景色随主题切换（浅色 `#1C2536`，深色 `#0B1220`）
- **安全模式开关**：首页安全模式卡片，切换即时生效并持久化
- **安全模式后端强制**：`POST /api/coyote/max_power` 安全模式下自动限制上限 100
- **启动设备二次确认**：安全模式关闭时启动设备需确认弹窗，警告全功率输出风险
- **蓝牙扫描进度指示**：连接按钮显示"连接中... 剩余 XX 秒"+ 进度条，40 秒超时提示
- **GitHub 统计缓存降级**：localStorage 缓存 + 超时降级显示，避免阻塞初始化
- **API 错误可见反馈**：所有 API 错误连续失败 3 次以上显示警告提示，不再静默吞掉

### 工程优化

- **聚合状态接口**：`/api/coyote/aggregate_status` 一次请求返回所有状态，减少前端轮询
- **打包路径修复**：区分只读资源目录（`BASE_DIR`）和用户配置目录（`USER_DATA_DIR`），首次运行自动释放 settings.yaml
- **进程模型**：uvicorn 跑在同一进程的守护线程里（早期版本用 `multiprocessing` 子进程，在 PyInstaller 单文件模式下 Windows `spawn` 会重复拉起 exe，导致 38080 无监听、窗口白屏）。关闭窗口前先打一次 `/api/coyote/stop` 做优雅停机（功率归零 + 断开蓝牙），再回收线程
- **Avatar 运行时追踪**：监听 `/avatar/change` OSC 消息，实时记录当前穿戴 avatar ID
- **代码清理**：删除空文件、未使用的 hook、constants.py 使用 BASE_DIR


## 快速开始

### 方式一：使用 Release（推荐普通用户）

1. 前往 [Releases 页面](https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC/releases) 下载最新 `release_windows_x64.zip`
2. 解压后运行 `osc-toys.exe`（保持 zip 内目录结构完整；若 38080 端口被占用请先关闭占用程序）
3. 准备一个支持 OSC 参数的 VRChat 形象（参数需为 **Float** 类型，例如 `VRCContactReceiver` Proximity 探针）
4. 启动 VRChat：
   - 在设置中 **启用 OSC**
   - 切换到目标 Avatar **至少一次**（才会在 LocalLow 生成 OSC 配置）
5. 在本程序 WebUI 中：
   - **总览页** 查看 OSC 链接状态（黄=等待信号，绿=已收到）、安全模式开关
   - **Coyote 页面** 填写设备 UID（留空自动扫描 `D-LAB ESTIM01`）→「连接并启动」
     - Coyote 指示灯为**白色（配对模式）时无法连接**，请退出配对
   - **OSC 地址** 点击「自动获取」或手动填写 Float 参数路径
   - **侧边栏** 调整 A/B 通道强度上限（0–200，**建议从 30–50 开始**；默认倍增 1.0，滑块与输出 1:1）
   - **Patterns** 选择波形（无需先连接设备即可预览）
6. 先在总览页确认 A/B 信号变绿，再逐步提高强度

### 方式二：从源码运行

```bash
# 依赖：Python 3.11+、Node.js 16+（仅构建前端需要）
# 后端
git clone https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC.git
cd DG-Lab-2.0-VRChat-OSC
pip install -r requirements.txt
pip install -r requirements-dev.txt        # 跑单元测试才需要（TestClient 依赖 httpx）

# 前端（必须先 export，main.py 依赖 frontend/out）
cd frontend
npm install
npm run build
npm run export
cd ..

# 启动
python main.py
```

### 方式三：自行打包 exe

```bash
pip install -r requirements-build.txt        # PyInstaller
python -m PyInstaller build_local.spec --noconfirm
# 产物：dist/osc-toys.exe（约 29 MB）
# 运行时需要与 exe 同级的 frontend/out、data/、settings.yaml
```

CI（`.github/workflows/release-exe.yaml`）走的就是这套流程：跑单元测试 → 构建前端 →
PyInstaller 打包 → 校验体积与内嵌前端 → 启动 exe 冒烟测试接口 → 打 zip 并发布。

启动后会等待本地服务就绪，再打开桌面 WebUI 窗口（端口 **38080**）。
本程序 OSC **监听**端口默认 **9001**（对应 VRChat 向外发送 OSC 的端口，不是接收端口）。

## 配置说明

大部分配置可在 WebUI 中修改并自动持久化到 `settings.yaml`。首次运行时程序会从内置默认配置释放一份 `settings.yaml` 到 exe 同目录，便于用户修改。关键字段如下：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `coyote_uid` | `""` | 设备蓝牙地址，留空自动扫描名为 `D-LAB ESTIM01` 的设备 |
| `coyote_addr_a` | `/avatar/parameters/EarLDis` | 通道 A 绑定的 OSC 参数地址（值需为 0–1 浮点） |
| `coyote_addr_b` | `/avatar/parameters/EarRDis` | 通道 B 绑定的 OSC 参数地址 |
| `coyote_max_power_a/b` | `50` | 信号满档时设备输出强度上限（0–200）。侧边栏调节此项 |
| `coyote_multiplier` | `1.0` | 强度倍增。`power = min(200, max_power × mapped × multiplier)`。默认 1.0 使滑块与输出 1:1；一般无需改 |
| `coyote_safe_mode` | `true` | 安全模式，限制最大输出为 100（约 50%）。**强烈建议保持开启** |
| `start_limit` | `0.05` | 信号低于此值时完全断电 |
| `min_limit` | `0.2` | 信号低于此值时保持 `min_power` |
| `max_limit` | `0.8` | 信号高于此值时输出满档 |
| `min_power` | `0.5` | 最小功率比例 |
| `window_size` | `0.1` | 滑动窗口平均滤波时长（秒），影响响应平滑度 |
| `vrc_host` | `127.0.0.1` | VRChat 客户端 OSC 主机 |
| `vrc_osc_port` | `9001` | VRChat OSC 端口 |
| `coyote_scan_timeout` | `10` | 蓝牙扫描时长（秒） |
| `coyote_connect_retries` | `3` | 连接失败重试次数。最坏连接耗时 = 扫描 + 重试次数 × `coyote_connect_timeout`，前端倒计时按该预算显示 |

### 信号映射曲线

```
              ▲
              │                max_limit (0.8)
          1.0 │               xx───────
              │              xx
              │             xx
              │            xx
              │           xx
              │          xx
    min_power │   ┌─────xx
       (0.5)  │   │       min_limit (0.2)
              │   │
              └───┴──────────────────────────►
              start_limit (0.05)
```

- 信号 `< start_limit`：输出 0（断电）
- 信号 `< min_limit`：输出 `min_power * max_power`
- 信号 `≥ max_limit`：输出 `1.0 * max_power`
- 中间区域：线性插值

## 架构说明

```
┌─────────────┐   OSC (UDP 9001)   ┌──────────────────┐   BLE   ┌──────────────┐
│  VRChat     │ ─────────────────► │  本程序 (FastAPI) │ ──────► │  DG-Lab      │
│  Avatar     │                    │  + Next.js WebUI │         │  Coyote      │
└─────────────┘                    └──────────────────┘         └──────────────┘
                                          │
                                          │ 读取
                                          ▼
                                  ┌──────────────────┐
                                  │  VRC 本地 OSC    │
                                  │  json 配置目录   │
                                  └──────────────────┘
```

### 后端（Python）

- `main.py` — FastAPI 入口，启动 uvicorn（端口 38080）+ pywebview 桌面窗口；应用启动时即启动 OSC 监听
- `common/paths.py` — 资源路径解析，区分 `BASE_DIR`（只读资源）和 `USER_DATA_DIR`（用户配置）
- `routers/coyote.py` — Coyote 设备控制 API、OSC 信号处理、聚合状态接口
- `routers/osc_server.py` — VRC OSC 地址配置 API（支持热更新）
- `routers/vrc_osc.py` — 读取 VRC 本地 OSC json，提供 avatar 参数列表
- `toys/estim/coyote/dg_interface.py` — 基于 bleak 的蓝牙通信实现
- `settings.py` / `settings.yaml` — 配置模型与持久化

### 前端（Next.js + MUI）

- `src/pages/_app.js` — 主题与 ColorModeContext Provider
- `src/contexts/color-mode-context.js` — 深浅色模式 Context
- `src/contexts/onboarding-context.js` — 新手指南 Context
- `src/components/pattern-preview.js` — Canvas 静态波形预览组件
- `src/sections/coyote/` — Coyote 控制台各卡片（status/address/pattern）
- `src/sections/overview/` — 总览页（coyote/vrc/osc-status/safe-mode）
- `src/features/onboarding/` — 引导式新手引导（欢迎页、步骤指示器）
- `src/theme/` — MUI 主题，支持 light/dark 双模式
- `src/layouts/dashboard/` — 侧边栏（含强度调节）、顶栏（含主题切换按钮）

## 版本历史

### v3.2.0 (当前)

第三轮全项目审查修复，重点解决「功能实际不可用 / 假功能 / 界面崩溃」：

- **非数值 OSC 参数导致整页崩溃修复**：OSC handler 现在会把参数值规整为浮点数，字符串等非法类型只忽略并告警一次，不再污染实时监控值。此前向绑定地址发一个字符串（例如误绑到 Bool/字符串参数）会让概览页 `value.toFixed()` 抛 `TypeError`，整个界面被错误边界接管
- **未知/损坏波形导致后端假死修复**：`signal()` 的循环变量此前只在波形状态循环体内推进，波形为空（`settings.yaml` 写错波形名、`data/estim` 缺失）时会变成无 `await` 的死循环，独占 asyncio 事件循环、后端彻底卡死。现在空波形会记录原因并安全退出
- **保存 OSC 地址不再有 50% 概率失败**：原先每次都先 `close()` 旧 UDP socket 再 `bind()` 同一端口，Windows 上端口尚未释放必然 `WinError 10048`，接口返回 500 且 OSC 监听被打死（实测连续保存 4 次，第 1、3 次失败）。现在监听地址未变时只原地替换分发映射、完全不碰 socket；地址变了则先绑新、成功后再关旧，失败保留原监听继续工作
- **非法端口不再打死 OSC**：`/api/osc_server/address` 在入参层校验 1–65535，越界返回 422（此前会走到 `bind()` 才 500，并顺带停掉监听）
- **OSC 地址格式校验**：非空地址必须以 `/` 开头，否则返回 400。此前漏写前导 `/` 也会提示「保存成功」，实际永远匹配不到信号
- **未知波形不再假成功**：`POST /api/coyote/pattern` 对不存在的波形名返回 400，而不是静默忽略后回 `success`
- **连接超时预算对齐后端**：新增 `coyote_scan_timeout` / `coyote_connect_retries`，`/settings` 暴露 `coyote_connect_budget`（默认 130 秒）。此前前端硬编码 40s/90s，远小于后端最坏 130s，倒计时一到就 abort 并调 `/stop`，慢一点的蓝牙永远连不上
- **非法 MUI 变体修复**：`variant="h7"` 不是合法变体，Typography 会退化成无样式 `<span>`，Coyote 页「电量 / 连接状态」两行排版与页面其余部分不一致
- **品牌名统一**：启动页与页面标题此前用上游项目名「OSC Toys」，与窗口标题/侧边栏「DG-Lab 2.0 — VRChat OSC」不一致
- **主题一致性**：OSC 消息历史面板不再硬编码 `grey.900`（浅色主题下是一块突兀黑底）；深色模式下输入框描边不再使用浅色 `neutral[200]`
- **波形预览支持尺寸变化**：Canvas 增加 `ResizeObserver`，窗口缩放/侧边栏开合后不再被拉伸
- **自动获取参数兜底**：当前模型解析不到 Float 参数时，列出本机所有 Avatar 的 Float 参数合集，而不是直接显示「未找到」
- **减少冗余蓝牙读取**：概览页 Coyote 卡片改用聚合接口，不再额外轮询 `/status`（该接口每次都读一次 BLE 电量）
- **首帧闪烁修复**：`localStorage` 读取完成前不渲染主界面，避免首帧先画出主界面再被启动页盖住
- **未命中的 `/api/*` 返回 JSON 404**，而不是 HTML 404 页面（后者让前端所有接口错误都退化成「status code 404」）
- **桌面窗口改用 `127.0.0.1`**，与健康检查一致，避免 `localhost` 优先解析到 `::1` 时白屏
- **依赖声明与实际运行环境脱节**：仓库里提交的 `requirements.txt` 停在 fastapi 0.95.1 / pydantic 1.10.7 /
  starlette 0.26.1 / uvicorn 0.22.0 / pywebview 4.0.2，而代码与实际验证过的环境是 fastapi 0.136.3 /
  pydantic 2.12.5 / uvicorn 0.47.0 / pywebview 6.2.1。照旧文件执行「方式二：从源码运行」装出来的是另一套运行时。
  更麻烦的是工作区里还躺着一份未提交的改动（把部分版本升上去了，却留着 `typing_extensions==4.5.0`），
  它与 `pydantic==2.12.5`（要求 `>=4.14.1`）直接冲突，`pip install -r requirements.txt` 会 `ResolutionImpossible`。
  现在把**完整运行时闭包**（32 个包）全部锁到实测版本，`bleak-winrt` / `winrt-*` 按 Python 版本加环境标记，
  测试依赖独立到 `requirements-dev.txt`，打包工具独立到 `requirements-build.txt`。
  只锁直接依赖是不够的：CI 上 pip 把 starlette 解析成了需要 `httpx2` 的新版本，单元测试直接跑不起来
- **补上测试依赖声明**：`fastapi` 的 `TestClient` 依赖 `httpx`，而它不在运行时闭包里。
  此前没有任何文件声明它，导致 CI 的「跑单元测试」步骤 `RuntimeError: The starlette.testclient
  module requires the httpx2 package` —— 65 个用例在 CI 里一次都没跑起来过
- **配置读写的错误处理不再自己崩掉**：`settings.py` 的 6 处错误提示用的是 `print()`，且全在
  兜底分支里。Windows 控制台编码由代码页决定，非中文系统上可能是 cp1252/cp437 —— 表示不了中文，
  `print` 会再抛 `UnicodeEncodeError`：`dump()` 里崩会让「持久化失败返回 False」变成异常、
  接口重新变 500；`load()` 里崩则会让异常从 `except` 块冒出去，`Settings.load()` 失败 →
  模块级构造失败 → **整个后端起不来**，恰好把「回落默认配置」的兜底完全废掉。
  现已全部改用 `logging`（内部会吞掉编码异常），并在 `main.py` 里把控制台 `errors` 放宽为
  `replace` 作为兜底。这个问题是**新 CI 第一次跑单元测试时暴露的**（runner 的 stdout 正是 cp1252）
- **单元测试不再隐式依赖构建产物**：SPA 回退用例直接断言 `GET /coyote` 返回 200，这要求
  `frontend/out/coyote.html` 存在 —— 而它是 `.gitignore` 的构建输出。CI 里测试排在构建之前，
  该用例必然 404（本地因为目录一直在，永远发现不了）。现在用例自己造一份临时 `frontend/out`，
  另加一条「真实产物存在时才执行」的用例；CI 顺序也调整为「构建前端 → 跑测试 → 打包」
- **打包配置纳入版本控制**：`build_local.spec` 此前被 `.gitignore` 的 `*.spec` 一起忽略，仓库里根本没有这个文件，克隆下来无法复现发布包。现已显式例外并加入索引
- **CI 对齐本地产物并补上质量门禁**：原工作流用 Nuitka（onefile）打包，与本地 `build_local.spec`（PyInstaller）
  是两套产物；且不跑单元测试、不校验产物。现改为：跑单元测试 → 构建前端 → 用仓库自己的 spec 打包 →
  校验体积与内嵌前端 chunk → **真的启动 exe 冒烟测试** `/health`、`/coyote`、`/settings` →
  打 zip（与本地同布局）→ 仅 tag 时发 Release；Python/Node 版本也对齐到本地已验证的 3.13 / 22
- **波形数据缺失不再导致程序起不来**：`load_patterns` 以前是裸 `open()`，`data/estim` 缺失/损坏会让 `Estim.__init__` 抛异常，而 `CoyoteInterface` 是模块级构造的 —— 表现为「双击 exe 没有任何窗口、38080 无监听」。现在缺失的波形文件会被跳过并告警，且 `default` 波形内置在代码里，程序始终能启动
- **本机请求绕过系统代理**：`urllib` 默认读取系统代理，健康检查与**退出时的优雅停机**（把设备功率归零并断开蓝牙）都可能被代理打断。现在这两处都使用显式禁用代理的 opener
- **退出时设备功率归零更可靠**：见上一条，这一步关系到「关窗后设备是否还在输出」
- **侧边栏强度不再误清另一通道**：两个滑块初值都是 0，而保存接口是「同时提交 A 和 B」。首次同步完成前若只改一个通道，会把另一个通道写成 0。现在会等配置同步完成再允许保存
- **日志不再刷屏**：每个窗口周期的 `set_pwm` 与逐条 avatar 扫描日志降到 debug（打包版带控制台窗口，Windows 控制台 I/O 会明显拖慢主循环）。需要时用 `OSC_TOYS_LOG_LEVEL=DEBUG` 打开
- **打包 spec 清理**：移除 3 个指向不存在模块的 `hiddenimports`（`uvicorn.workers` 依赖未安装的 gunicorn、`pythonosc.handler`、`common.util`），避免噪音警告掩盖真正的缺模块
- **侧边栏「服务器错误提示」由假功能变真功能**：`serverError` 状态一直在统计连续失败次数，却从未被渲染 —— 后端挂了用户在侧边栏看不到任何线索。现在会显示「无法连接到后端服务，强度设置可能未生效」
- **死代码清理**：移除未使用的 import / 变量（前端 18 处、后端 2 处）、
  `dg_encoding.test_function_validity()`（依赖仓库里并不存在的 `fuzzy_*_data.json`，永远跑不起来）、
  `toys/base.py` 中从未被调用的 `check_in/action/get_toys` 桩方法与 3 个未使用常量；
  并把 `no-unused-vars` 加进 ESLint 规则，防止再次堆积
- **清理无用文件**：`frontend/pnpm-lock.yaml`（项目用 npm，`package-lock.json` 才是当前的）、
  `frontend/CHANGELOG.md`（上游 Devias 模板的更新日志，与本项目版本历史无关且版本号会误导）、
  以及 `.workbuddy/backup/`（约 1GB 的历史构建备份）与各类构建缓存
- 单元测试 39 → **73 例**，新增 34 条针对上述问题的回归

### v3.1.1

- **连接即输出修复**：连接设备后收到首个 OSC 信号前保持 0 强度，避免无信号持续输出
- **蓝牙重连超时修复**：`connect()` 重试不再翻倍超时，移除对 bleak 私有 `_backend._timeout` 的依赖
- **断线 fail-safe**：BLE 断开即停止输出并标记未连接，绝不自动恢复输出
- **刷新 404 修复**：静态前端新增路由回退，`/coyote` 等路径刷新不再 404
- **打包路径修复**：BASE_DIR 解析到 exe 同级目录，正确加载 `frontend/out` 与 `data`
- **信号映射重构**：拆分为 `get_raw_avg`/`map_signal`，修正 SSE 滑动平均，处理 `min_limit >= max_limit` 除零与 `window_size <= 0` 边界
- **强度接口加固**：`/api/coyote/max_power` 非负钳制；前端倒计时读取后端 `coyote_connect_timeout`
- **Avatar 判定修复**：`newest_time` 在重复 avatar 分支同步更新，修正当前穿戴模型误判
- **单元测试**：新增 `tests/`，覆盖信号映射、强度钳制与断线处理（11 个用例）

### v2.0

- **引导式新手引导 (Onboarding Wizard)**：粒子动画欢迎页 → 连接设备 → OSC 地址 → 波形选择 → 强度调节，逐步骤引导新用户
- **实时 OSC 监控 (SSE)**：`/api/coyote/osc_stream` 推送原始值/均值/映射值 + 消息历史，首页进度条实时显示
- **OSC 状态区分**：yellow"等待 VRChat" / green"VRChat 已连接" / grey"未启动"
- **Avatar 运行时追踪**：监听 `/avatar/change` 实时记录当前 avatar ID，不再仅依赖文件修改时间
- **`power_multiplier` 失效修复**：multiplier 对 `set_pwm` 路径生效；默认改为 **1.0**，避免滑块失真
- **波形预览静态化**：去除了实时动画指针，减少视觉干扰
- **引导页 Select 原生化**：使用 `native={true}` 消除下拉菜单卡顿
- **安全模式后端强制**：`POST /api/coyote/max_power` 安全模式下自动限制上限 100
- **Avatar ID 显示**：自动获取弹窗改为显示 avatar ID 而非模型名称
- **OGB/Orf 参数提示**：未在列表中时提示用户手动填写
- **进程优雅退出**：`os._exit(0)` → `kill(terminate)` 超时等待，不再暴力终止
- **float 参数过滤限制**：仅显示 Float 类型参数

### v1.5

- 修复 VRC OSC 模型读取：BOM 编码（`utf-8` → `utf-8-sig`）+ 参数地址优先读取 `output.address`
- 完整汉化波形文件：扩展 Pattern 中文名映射至 23 个（武器冲击类、场景专用类）

### v1.3

- OSC 监听独立于设备连接，无需 Coyote 在手即可测试 VRChat 信号
- OSC 地址热更新，无需断开设备
- 首页新增 OSC 链接状态卡片
- 启动设备二次确认（安全模式关闭时）
- 蓝牙扫描进度指示 + 40 秒倒计时
- Pattern 中文名映射
- GitHub 统计 localStorage 缓存 + 降级显示
- 聚合状态接口减少前端轮询
- can_update_power 超时兜底
- API 错误可见反馈

### v1.2

- 修复 Nuitka 打包后 settings.yaml 找不到的问题（区分 BASE_DIR / USER_DATA_DIR）
- 新增安全模式开关（首页卡片）
- 修复 OSC 地址修改不持久化
- 修复停止设备后电量残留

### v1.1

- 全面汉化 UI 文案
- 强度调整迁移至侧边栏
- 新增 OSC 链接状态判定

### v1.0

- 修复 `get_avg` 信号映射逻辑
- 强度范围对齐官方 0–200
- OSC 地址自动获取
- Patterns 波形可视化预览
- 深浅色主题切换
- 窗口默认尺寸 1280×820

## 常见问题

**Q: 程序连不上 Coyote？**
A: 确保设备指示灯不是白色（白色为配对模式）。尝试重启程序、重启电脑蓝牙、将设备靠近电脑。信号干扰多时连接质量会下降。自动扫描失败可在 UID 输入框填入设备的实际 MAC 地址（格式如 `C9:9F:E4:2E:31:60`）跳过自动搜索。

**Q: Auto Fetch 拉不到参数？**
A: 请先在 VRChat 中切换到目标 avatar 至少一次，让 VRC 生成 OSC 配置 json。同时确认 VRChat 设置中 OSC 已启用。

**Q: 改了 `settings.yaml` 没生效？**
A: OSC 地址修改支持热更新，无需断开设备。其他配置改完会自动持久化。如果打包版 exe 的 settings.yaml 在 exe 同目录，修改后会自动保存。

**Q: 深色模式不跟随系统？**
A: 首次访问会跟随系统，之后以手动选择为准（保存在 localStorage）。清除浏览器/应用缓存可重置。

**Q: 强度变化有延迟？**
A: 默认 `window_size = 0.1` 秒更新一次。可减小该值提升响应速度，但太小会导致设备处理不过来反而延迟。建议在 0.05–0.1 之间寻找平衡。


**Q: 侧边栏调了强度但体感不对 / 一碰就很强？**
A: 确认 `settings.yaml` 中 `coyote_multiplier` 为 `1.0`（默认）。旧版本默认 6.0 会导致滑块过早顶满。强度上限建议从 30–50 开始。

**Q: 程序窗口标题或品牌名不一致？**
A: 当前产品名为 **DG-Lab 2.0 — VRChat OSC**（基于 osc-toys 二次开发）。请以本仓库 README 与 Releases 为准。

**Q: 端口 38080 打不开 / 白屏？**
A: 检查是否被其他程序占用；杀毒软件是否拦截；源码运行时是否已执行 `npm run export` 生成 `frontend/out`。

**Q: 双击 exe 没有任何窗口，38080 也没监听？**
A: 先确认压缩包解压后目录结构完整 —— `osc-toys.exe` 必须与 `frontend/`、`data/`、`settings.yaml` 同级。
`data/estim/` 里是波形数据，如果被清理掉，程序启动时读不到波形（旧版本会直接起不来，v3.2.0 起会跳过缺失文件并回退到内置的「默认」波形）。
另外可临时设置环境变量 `OSC_TOYS_LOG_LEVEL=DEBUG` 重新运行，看控制台输出定位原因。

**Q: 打包版 exe 启动后 settings.yaml 在哪？**
A: 在 exe 同目录。首次运行时会从 exe 内部释放默认配置到外部，之后修改的配置都会保存到这个文件。

## 安全警告

> 电刺激设备非常强大，软硬件故障可能导致突然或剧烈的电击。

- **不要在腰部以上使用，尤其不要跨胸部使用**
- 不要在意识不清的状态下使用
- 设备工作时不要移动或接触电极
- 不要在未经明确同意的情况下对他人使用
- 始终保持安全模式开启（限制上限 100），除非你完全清楚后果
- 关闭安全模式后启动设备会有二次确认弹窗，请谨慎操作
- 使用前请确保强度从低值开始逐步调整（默认上限 50，建议先确认 OSC 信号再提高）

详见 `toys/estim/coyote/dg_interface.py` 文件头部的完整免责声明。

## 致谢

本项目基于 [Sakura0721/osc-toys](https://github.com/Sakura0721/osc-toys) 二次开发，原项目又基于：

- [GIFT (GameInterfaceForToys)](https://github.com/MinLL/GameInterfaceForToys) by [@MinLL](https://github.com/MinLL)
- [@inertaert](https://github.com/inertaert) 的 Coyote 通信代码
- [@rezreal](https://github.com/rezreal/coyote) 的字节编码实现

感谢上述作者的开源贡献。

## 许可证

[GNU General Public License v3](LICENSE)

本项目基于 GPLv3 协议开源。原项目 `Sakura0721/osc-toys` 的 LICENSE 文件即为 GPLv3，根据协议要求，本衍生项目继续以 GPLv3 发布。
