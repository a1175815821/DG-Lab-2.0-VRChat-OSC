<div align="center" id="top">
  <img width="200" src="images/logo.svg" alt="DG-Lab 2.0 Logo" />
</div>

<h1 align="center">DG-Lab 2.0 — VRChat OSC</h1>

<p align="center">
  <img alt="GitHub" src="https://img.shields.io/github/license/a1175815821/DG-Lab-2.0-VRChat-OSC?label=license">
  <img alt="GitHub repo size" src="https://img.shields.io/github/repo-size/a1175815821/DG-Lab-2.0-VRChat-OSC">
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/a1175815821/DG-Lab-2.0-VRChat-OSC">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/a1175815821/DG-Lab-2.0-VRChat-OSC?style=social">
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
- [相对于上游的改动](#相对于上游的改动)
- [常见问题](#常见问题)
- [安全警告](#安全警告)
- [致谢](#致谢)
- [许可证](#许可证)

## 项目简介

本项目运行一个本地 Web 服务（FastAPI + Next.js 静态前端），监听 VRChat 通过 OSC 协议发出的 avatar 参数（例如耳朵触摸探针 `EarLDis` / `EarRDis`），实时将数值映射为 DG-Lab Coyote 电刺激设备的输出强度，从而实现「虚拟形象被触碰 → 现实身体受电击」的反馈闭环。

适用于带有 `VRCContactReceiver`（Proximity 类型，输出 Float）参数的 VRChat 形象。

## 主要特性

### 修复的关键 Bug（上游存在）

- 修复 `get_avg` 信号映射逻辑错误：原代码只有两档输出（min_power / 满档），现已实现 `start_limit → 0`、`min_limit → min_power`、`max_limit → 1.0` 之间的平滑线性插值
- 修复信号低于阈值时 `set_pwm(1, -1)` 应为 `0` 的问题（原代码会留下微弱持续输出）
- 修复 `start_limit` 配置项未被使用、阈值硬编码 `0.1` 的问题
- 修复 Stop 时 `transport.close()` 在未连接状态下崩溃的问题
- 修复 `power_multiplier` 配置失效问题（原硬编码 1.28，现读取 `settings.coyote_multiplier`）

### 强度范围对齐官方

DG-Lab Coyote 官方强度范围为 **0–200**，本项目已全面对齐：

- `set_pwm` 输入范围：0–200（safe_mode 启用时上限 100）
- 前端 Max Power slider：0–200
- 功率死区从 `< 10` 缩小到 `< 2`，避免小变化被忽略导致的突跳

### OSC 地址自动获取

VRChat 会在 `%LOCALAPPDATA%\Low\VRChat\VRChat\OSC\` 下为每个 avatar 生成 OSC 配置 json。本项目新增 `/api/vrc/avatars` 接口读取该目录，前端 OSC Addresses 卡片新增 **Auto Fetch** 按钮：

- 点击后弹窗列出所有本地 avatar
- 仅显示 Float 类型参数（本项目需要 0–1 浮点值）
- 点击参数即自动填入对应通道，无需再手动复制粘贴

### Patterns 波形可视化预览

- Patterns 卡片下方新增 Canvas 波形预览组件
- 每个 pattern state（`[脉冲时长, 间隔, 幅度]`）以矩形高度直观呈现
- 设备连接后会出现红色播放指针循环扫过波形，表示当前正在按该波形输出
- 显示波形总时长与播放状态

### UI 改进

- 窗口默认尺寸从 1920×1080 调整为 **1280×820**，不再霸占屏幕
- **深浅色主题切换**：右上角日/月图标按钮，选择持久化到 localStorage，首次访问跟随系统偏好
- 修复侧边栏左下角文字不可见问题（原 `neutral.500` 等灰色文字在深色背景上对比度极低，已统一改为白色透明度三档）
- 侧边栏背景色随主题切换（浅色 `#1C2536`，深色 `#0B1220`）
- 顶栏增加分隔线，毛玻璃背景透明度调整


## 快速开始

### 方式一：使用 Release（推荐普通用户）

1. 前往 [Releases 页面](https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC/releases) 下载最新 `release_windows_x64.zip`
2. 解压后运行 `osc-toys.exe`
3. 准备一个支持 OSC 参数的 VRChat 形象（参数需为 Float 类型，例如 `VRCContactReceiver` Proximity 探针）
4. 启动 VRChat，在 WebUI 中：
   - **Coyote** 页面填写设备 UID（留空可自动扫描）→ 点击 `Connect and Start`
   - **OSC Addresses** 页面点击 `Auto Fetch` 从本地 VRC 配置自动读取参数
   - **Max Power** 调整最大强度（0–200，建议从 50 开始）
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

大部分配置可在 WebUI 中修改并自动持久化到 `settings.yaml`。如需手动调整，关键字段如下：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `coyote_uid` | `""` | 设备蓝牙地址，留空自动扫描名为 `D-LAB ESTIM01` 的设备 |
| `coyote_addr_a` | `/avatar/parameters/EarLDis` | 通道 A 绑定的 OSC 参数地址（值需为 0–1 浮点） |
| `coyote_addr_b` | `/avatar/parameters/EarRDis` | 通道 B 绑定的 OSC 参数地址 |
| `coyote_max_power_a/b` | `100` | VRC 信号为 1.0 时设备的输出强度（0–200） |
| `coyote_multiplier` | `2.0` | 振动强度到电刺激强度的转换系数 |
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

- `main.py` — FastAPI 入口，启动 uvicorn（端口 38080）+ pywebview 桌面窗口
- `routers/coyote.py` — Coyote 设备控制 API 与 OSC 信号处理
- `routers/osc_server.py` — VRC OSC 地址配置 API
- `routers/vrc_osc.py` — **新增**，读取 VRC 本地 OSC json，提供 avatar 参数列表
- `toys/estim/coyote/dg_interface.py` — 基于 bleak 的蓝牙通信实现
- `settings.py` / `settings.yaml` — 配置模型与持久化

### 前端（Next.js + MUI）

- `src/pages/_app.js` — 主题与 ColorModeContext Provider
- `src/contexts/color-mode-context.js` — **新增**，深浅色模式 Context
- `src/components/pattern-preview.js` — **新增**，Canvas 波形预览组件
- `src/sections/coyote/` — Coyote 控制台各卡片（status/address/power/pattern）
- `src/theme/` — MUI 主题，支持 light/dark 双模式
- `src/layouts/dashboard/` — 侧边栏、顶栏（含主题切换按钮）

## 相对于上游的改动

| 模块 | 改动 |
|---|---|
| `routers/coyote.py` | 修复 `get_avg` 映射、`set_pwm(0)` 断电、`start_limit` 生效、`transport` 空指针、`power_multiplier` 读取配置；新增 patterns detail 接口 |
| `toys/estim/coyote/dg_interface.py` | 强度范围 0–2047 → 0–200；safe_mode 上限 768 → 100；死区 10 → 2 |
| `routers/vrc_osc.py` | 新增文件，读取 VRC 本地 OSC json |
| `main.py` | 注册新路由；窗口尺寸 1920×1080 → 1280×820 |
| `settings.yaml` / `settings.py` | 默认值更新（max_power 100、multiplier 2.0） |
| `frontend/src/contexts/` | 新增 color-mode-context |
| `frontend/src/components/pattern-preview.js` | 新增波形预览组件 |
| `frontend/src/sections/coyote/coyote-address.js` | 新增 Auto Fetch 弹窗 |
| `frontend/src/sections/coyote/coyote-pattern.js` | 集成波形预览与实时状态 |
| `frontend/src/sections/coyote/coyote-power.js` | slider max 768 → 200 |
| `frontend/src/theme/` | createPalette/createTheme 支持 light/dark |
| `frontend/src/pages/_app.js` | 引入 ColorModeContext、localStorage 持久化、系统偏好跟随 |
| `frontend/src/layouts/dashboard/` | 顶栏主题切换按钮；侧边栏文字对比度修复 |

## 常见问题

**Q: 程序连不上 Coyote？**
A: 确保设备指示灯不是白色（白色为配对模式）。尝试重启程序、重启电脑蓝牙、将设备靠近电脑。信号干扰多时连接质量会下降。

**Q: 强度变化有延迟？**
A: 默认 `window_size = 0.1` 秒更新一次。可减小该值提升响应速度，但太小会导致设备处理不过来反而延迟。建议在 0.05–0.1 之间寻找平衡。

**Q: Auto Fetch 拉不到参数？**
A: 请先在 VRChat 中切换到目标 avatar 至少一次，让 VRC 生成 OSC 配置 json。同时确认 VRChat 设置中 OSC 已启用。

**Q: 改了 `settings.yaml` 没生效？**
A: 部分配置（如 `coyote_addr_a/b`）在设备已连接时无法修改，请先 Disconnect 再改。改完点击 Save 会自动持久化。

**Q: 深色模式不跟随系统？**
A: 首次访问会跟随系统，之后以手动选择为准（保存在 localStorage）。清除浏览器/应用缓存可重置。

## 安全警告

> 电刺激设备非常强大，软硬件故障可能导致突然或剧烈的电击。

- **不要在腰部以上使用，尤其不要跨胸部使用**
- 不要在意识不清的状态下使用
- 设备工作时不要移动或接触电极
- 不要在未经明确同意的情况下对他人使用
- 始终保持 `coyote_safe_mode: true`，除非你完全清楚后果
- 使用前请确保 Max Power 从低值开始逐步调整

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
