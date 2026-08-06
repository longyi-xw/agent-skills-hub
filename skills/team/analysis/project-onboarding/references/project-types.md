# 项目类型识别 & 新功能落点指南

本文件分两部分：
1. **特征文件识别表** —— 根据仓库里的标志性文件判定项目类型
2. **按类型的目录约定与落点指南** —— 判定类型后，读取对应分节

---

## 第一部分：特征文件识别表

按优先级从上到下匹配（越靠上越具体，优先采信）。

| 特征文件 / 目录 | 判定类型 | 进一步线索 |
|------|------|------|
| `src-tauri/` + `tauri.conf.json` | **Tauri 桌面应用** | 前端可能是 Vue/React/Svelte，看 `package.json`；后端是 Rust（`src-tauri/Cargo.toml`） |
| `dependencies` 含 `electron`、有 `main` 字段指向主进程 / 有 `electron-builder`/`electron.vite.config` | **Electron 桌面应用** | 看是否用 `electron-vite`、`vite-plugin-electron`；区分主进程/渲染进程 |
| `capacitor.config.*` / `ionic.config.json` | **Capacitor/Ionic 混合移动应用** | 内核仍是 Web 框架 |
| `app.json` + `expo` 依赖 / `metro.config.js` | **React Native / Expo 移动应用** | — |
| `pubspec.yaml` | **Flutter 应用** | `lib/main.dart` 为入口 |
| `*.uvue` / `manifest.json` + `pages.json` | **uni-app 跨端应用** | 国内多端框架 |
| `project.config.json` + `app.json`（小程序结构） | **微信/各家小程序** | — |
| `next.config.*` | **Next.js（React 全栈/SSR）** | `app/` 或 `pages/` 目录决定路由模式 |
| `nuxt.config.*` | **Nuxt（Vue 全栈/SSR）** | — |
| `vite.config.*` + `src/App.vue` | **Vite + Vue SPA** | 看是否有 `router/`、`stores/` |
| `vite.config.*` + `src/App.{jsx,tsx}` | **Vite + React SPA** | — |
| `angular.json` | **Angular 应用** | — |
| `svelte.config.js` | **Svelte / SvelteKit** | — |
| `vue.config.js` / `.vue` 文件 + 无 vite | **Vue CLI (webpack) 项目** | 偏老项目 |
| `Cargo.toml`（无 `src-tauri`） | **Rust 项目** | 看是 bin（`main.rs`）还是 lib，是否含 `actix`/`axum`/`tokio` 判断是否后端服务 |
| `pyproject.toml` / `requirements.txt` / `setup.py` | **Python 项目** | 含 `fastapi`/`flask`/`django` → 后端服务；含 `click`/`typer` → CLI；含 `pandas`/`jupyter` → 数据 |
| `pom.xml` / `build.gradle` | **Java / Kotlin 项目** | 含 `spring-boot` → Spring 后端 |
| `go.mod` | **Go 项目** | 含 `gin`/`echo`/`fiber` → Web 服务 |
| `Gemfile` + `config/routes.rb` | **Ruby on Rails** | — |
| `composer.json` + `artisan` | **Laravel (PHP)** | — |
| 多个 `package.json` + `pnpm-workspace.yaml`/`lerna.json`/`turbo.json`/`nx.json` | **Monorepo** | 需逐个子包判定类型；先看 workspace 配置列出的包 |
| 仅 `Dockerfile`/`docker-compose.yml` 无上述 | 看容器内服务 | 从 compose 的 service 推断各部分技术栈 |

**多特征冲突时**：monorepo 优先按 workspace 拆分；单仓库出现历史遗留特征（如同时有 electron 和 tauri）时，向用户确认主体。

---

## 第二部分：按类型的目录约定与落点指南

判定类型后，读取下面对应分节。其余分节可跳过。

---

### Tauri 桌面应用

**典型结构**
```
├── src/                 # 前端（Vue/React/Svelte）
│   ├── views|pages/      # 页面
│   ├── components/
│   ├── router/
│   ├── stores/
│   └── api/ 或 services/  # 含调用 Rust 的封装
├── src-tauri/           # Rust 后端
│   ├── src/
│   │   ├── main.rs       # 程序入口 + invoke_handler 注册
│   │   ├── commands/     # #[tauri::command] 命令
│   │   └── lib.rs
│   ├── tauri.conf.json   # 窗口、权限、打包配置（重点看 allowlist/capabilities）
│   └── Cargo.toml
```

**关键边界**：前端通过 `@tauri-apps/api` 的 `invoke('command_name', args)` 调用 Rust；Rust 侧用 `#[tauri::command]` 暴露并在 `main.rs` 的 `.invoke_handler(tauri::generate_handler![...])` 注册。事件用 `emit`/`listen`。权限在 `tauri.conf.json`（v1 的 allowlist / v2 的 capabilities）控制。

**新功能落点指南**
- **加一个调用系统能力的功能**：① `src-tauri/src/commands/` 新增 `#[tauri::command]` 函数 → ② 在 `main.rs` 的 `generate_handler!` 注册 → ③ 检查 `tauri.conf.json` 权限是否放行 → ④ 前端封装 `invoke` 调用（参照现有 api/services 写法）→ ⑤ 在组件中使用。
- **加一个纯前端页面**：同「前端 SPA」流程（建组件 → 注册路由 → 加导航）。
- **加一个新窗口**：在 `tauri.conf.json` 配置或用 `WebviewWindow` API 动态创建。

---

### Electron 桌面应用

**典型结构**
```
├── src/ 或 electron/
│   ├── main/             # 主进程（Node 环境，访问系统/文件）
│   │   └── index.ts      # app 生命周期、BrowserWindow、ipcMain.handle
│   ├── preload/          # 预加载脚本（contextBridge 暴露安全 API）
│   └── renderer/         # 渲染进程（Web 前端，Vue/React）
├── electron-builder.* / electron.vite.config.*
```

**关键边界**：渲染进程不直接碰 Node，通过 `preload` 用 `contextBridge.exposeInMainWorld` 暴露白名单 API；主进程用 `ipcMain.handle('channel', handler)` 响应，渲染进程用 `ipcRenderer.invoke('channel', ...)`（或经 preload 暴露的方法）调用。

**新功能落点指南**
- **加一个需要系统能力的功能**：① 主进程 `ipcMain.handle('new-feature', ...)` → ② `preload` 里 `contextBridge` 暴露对应方法 → ③ 渲染进程调用暴露出的方法 → ④ 注意 TS 下补全 `window` 的类型声明。
- **加纯前端页面**：在 renderer 内按 SPA 流程处理。
- **常见坑**：`contextIsolation`/`nodeIntegration` 配置决定能不能直接用 Node；遵循现有 preload 模式，别破坏安全边界。

---

### 移动端 / 混合应用（Capacitor / Ionic / RN / uni-app / Flutter）

**Capacitor/Ionic**：内核是 Web 框架，原生能力通过 Capacitor 插件（`@capacitor/*`）调用；`capacitor.config.*` 管配置，`ios/`、`android/` 是原生壳。落点：纯 UI 走 Web 框架流程；原生能力找/装对应 Capacitor 插件后在 service 层封装。

**React Native / Expo**：`App.{js,tsx}` 入口，导航多用 `react-navigation`（看 `navigation/` 或路由配置）。落点：新页面 = 建 screen → 在 navigator 注册；原生能力走 Expo SDK 或原生模块。

**uni-app**：`pages.json` 是路由 + 导航的唯一真相来源，`manifest.json` 管多端配置。落点：新页面必须在 `pages.json` 注册才生效。

**Flutter**：`lib/` 下按 feature 或 layer 组织，`main.dart` 入口，路由看 `MaterialApp` 的 routes 或 `go_router` 配置。落点：新页面 = 建 Widget → 注册路由 → 状态管理按现有方案（Provider/Riverpod/Bloc）接入。

---

### Web SPA（Vue / React / Angular / Svelte）

**典型结构**
```
├── src/
│   ├── main.{ts,js}      # 入口：挂载根组件、注册路由/store/插件
│   ├── App.*             # 根组件
│   ├── router/           # 路由表 ← 页面映射的真相来源
│   ├── stores|store/     # 状态管理（Pinia/Vuex/Redux/Zustand）
│   ├── views|pages/      # 页面级组件
│   ├── components/       # 复用组件
│   ├── api|services/     # 请求封装
│   ├── composables|hooks/ # 逻辑复用
│   ├── utils/            # 工具函数
│   ├── types/            # TS 类型
│   └── assets/、locales/  # 静态资源、i18n
```

**新功能落点指南**
- **加一个新页面**：① `views/pages` 建页面组件 → ② `router/` 注册路由 → ③ 加菜单/导航入口 → ④ 若需数据，在 `api/` 加请求 + `stores/` 加状态 → ⑤ 参照现有同类页面的写法保持一致。
- **加一个接口**：① `api/` 对应模块加方法 → ② `types/` 定义请求/响应类型 → ③ 在 store action 或组件中消费。
- **加全局状态**：在 `stores/` 新增 module/store → 定义类型 → 组件订阅。
- **加复用逻辑**：抽到 `composables/`（Vue）或 `hooks/`（React）。

---

### 全栈 / SSR（Next.js / Nuxt）

**Next.js**：`app/` 目录（App Router）下文件夹即路由，`page.tsx` 是页面、`route.ts` 是 API、`layout.tsx` 是布局；或 `pages/` 目录（Pages Router）下文件即路由、`pages/api/` 是接口。区分 Server Component 与 Client Component（`'use client'`）。落点：新页面 = 在 `app/<route>/page.tsx` 建文件（约定式路由，无需手动注册）；新 API = `app/api/<name>/route.ts`。

**Nuxt**：`pages/` 约定式路由、`server/api/` 后端接口、`composables/` 自动导入、`stores/`（Pinia）。落点同理，约定式路由建文件即生效。

---

### 后端服务（FastAPI / Flask / Django / Spring / Express / Gin / Axum 等）

**通用分层**：入口/启动 → 路由/控制器 → 服务/业务逻辑 → 数据访问（ORM/Repository）→ 模型/Schema → 中间件 → 配置。

**新功能落点指南（加一个接口）**：① 定义数据模型/Schema → ② 数据访问层加查询 → ③ 服务层写业务逻辑 → ④ 路由/控制器注册端点 → ⑤ 按现有鉴权/校验/异常处理模式接入。具体框架的目录名不同，但分层职责一致——先找到现有的一个同类端点，照着它的链路加。

> 使用者主业是前端，遇到后端项目时，落点指南尤其要点明「现有的一个完整端点链路在哪几个文件」，让其照葫芦画瓢。

---

### CLI 工具

入口在 `bin/` 或 `main` 指向的文件；命令定义看用的库（commander/yargs/click/typer/cobra）。落点：新命令 = 在命令注册处加 subcommand → 实现 handler → 更新 help/文档。

---

### Monorepo

先读 workspace 配置（`pnpm-workspace.yaml` / `turbo.json` / `nx.json` / 根 `package.json` 的 `workspaces`）列出所有子包，画出包之间的依赖关系（哪个是 app、哪个是共享 lib/ui/utils）。再对用户关心的子包按其自身类型走上面对应流程。落点：跨包改动要注意共享包的版本与构建顺序。
