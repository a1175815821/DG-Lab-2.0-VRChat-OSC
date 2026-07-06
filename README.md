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
- **OSC 地址热更新**：修改 OSC 地址无需断开设备，自动重启监听服务应用新地址
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

VRChat 会在 `%LOCALAPPDATA%\Low\VRChat\VRChat\OSC\` 下为每个 avatar 生成 OSC 配置 json。本项目新增 `/api/vrc/avatars` 接口读取该目录：

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
- 默认 multiplier 从 2.0 提升至 **6.0**（可在 settings.yaml 中自行调整）

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
- **进程模型重构**：uvicorn 作为 daemon 子进程，关闭窗口后 `kill → terminate` 超时等待优雅退出
- **Avatar 运行时追踪**：监听 `/avatar/change` OSC 消息，实时记录当前穿戴 avatar ID
- **代码清理**：删除空文件、未使用的 hook、constants.py 使用 BASE_DIR


## 快速开始

### 方式一：使用 Release（推荐普通用户）

1. 前往 [Releases 页面](https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC/releases) 下载最新 `release_windows_x64.zip`
2. 解压后运行 `osc-toys.exe`
3. 准备一个支持 OSC 参数的 VRChat 形象（参数需为 Float 类型，例如 `VRCContactReceiver` Proximity 探针）
4. 启动 VRChat，在 WebUI 中：
   - **总览页** 查看 OSC 链接状态、安全模式开关
   - **Coyote 页面** 填写设备 UID（留空可自动扫描）→ 点击「连接并启动」（安全模式关闭时需二次确认）
   - **OSC 地址** 点击「自动获取」从本地 VRC 配置读取参数
   - **侧边栏** 调整 A/B 通道强度上限（0–200，建议从 50 开始）
   - **Patterns** 选择波形并查看实时预览
5. 享受反馈

### 方式二：从源码运行

```bash
# 后端
git clone https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC.git
cd DG-Lab-2.0-VRChat-OSC
pip install -r requirements.txt

# 前端
cd frontend
npm install
npm run build
npm run export
cd ..

# 启动
python main.py
```

启动后会同时打开桌面 WebUI 窗口与本地 HTTP 服务（端口 38080）。

## 配置说明

大部分配置可在 WebUI 中修改并自动持久化到 `settings.yaml`。首次运行时程序会从内置默认配置释放一份 `settings.yaml` 到 exe 同目录，便于用户修改。关键字段如下：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `coyote_uid` | `""` | 设备蓝牙地址，留空自动扫描名为 `D-LAB ESTIM01` 的设备 |
| `coyote_addr_a` | `/avatar/parameters/EarLDis` | 通道 A 绑定的 OSC 参数地址（值需为 0–1 浮点） |
| `coyote_addr_b` | `/avatar/parameters/EarRDis` | 通道 B 绑定的 OSC 参数地址 |
| `coyote_max_power_a/b` | `100` | VRC 信号为 1.0 时设备的输出强度（0–200） |
| `coyote_multiplier` | `6.0` | 强度倍增系数。V2.0 起对 `set_pwm` 路径也生效：`min(200, max_power × s × multiplier)` |
| `coyote_safe_mode` | `true` | 安全模式，限制最大输出为 100（约 50%）。**强烈建议保持开启** |
| `start_limit` | `0.05` | 信号低于此值时完全断电 |
| `min_limit` | `0.2` | 信号低于此值时保持 `min_power` |
| `max_limit` | `0.8` | 信号高于此值时输出满档 |
| `min_power` | `0.5` | 最小功率比例 |
| `window_size` | `0.1` | 滑动窗口平均滤波时长（秒），影响响应平滑度 |
| `vrc_host` | `127.0.0.1` | VRChat 客户端 OSC 主机 |
| `vrc_osc_port` | `9001` | VRChat OSC 端口 |

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

### v2.0 (当前)

- **引导式新手引导 (Onboarding Wizard)**：粒子动画欢迎页 → 连接设备 → OSC 地址 → 波形选择 → 强度调节，逐步骤引导新用户
- **实时 OSC 监控 (SSE)**：`/api/coyote/osc_stream` 推送原始值/均值/映射值 + 消息历史，首页进度条实时显示
- **OSC 状态区分**：yellow"等待 VRChat" / green"VRChat 已连接" / grey"未启动"
- **Avatar 运行时追踪**：监听 `/avatar/change` 实时记录当前 avatar ID，不再仅依赖文件修改时间
- **`power_multiplier` 失效修复**：multiplier 现对 `set_pwm` 路径也生效，默认从 2.0 提升到 **6.0**
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
- 使用前请确保强度从低值开始逐步调整

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
