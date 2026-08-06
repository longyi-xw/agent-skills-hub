---
name: frontend-development
description: 前端与桌面端功能开发的执行规范。当用户要求「实现一个页面/组件」「加个交互」「改样式」「对接接口」「做个表单」「优化首屏/性能」「适配移动端或暗色模式」，或在 React / Vue / TypeScript / Electron / Tauri 项目中新增或修改界面代码时，使用本技能。覆盖从复用现有代码、状态与数据流选型、样式与主题、可访问性、到自测清单的完整流程。适用于 Web、桌面端与移动端 H5 项目。Use this skill when implementing or modifying any frontend UI, component, page, form, or styling work.
category: frontend
tags: [frontend, react, vue, typescript, ui, electron]
status: verified
---

# 前端开发

## 何时使用本技能

- 新增页面、组件、交互、表单
- 修改样式、主题、响应式与暗色模式
- 前端对接后端接口、处理加载与错误态
- 首屏性能、包体积、渲染性能优化

不适用：纯后端接口实现（用 `python-backend`）、纯视觉回归验证（用 `visual-verification`）。

## 铁律：先复用，再新建

写任何一个组件之前，**必须**先在仓库里找有没有现成的。

```
1. 找同类组件：  按目录（components/、ui/、shared/）与关键词搜索
2. 找设计令牌：  搜索 theme / tokens / variables / tailwind.config
3. 找相似页面：  找一个功能最接近的现有页面，照抄它的结构与命名
```

只有确认三处都没有，才允许新建。新建时命名、目录、导出方式一律跟随该仓库既有惯例，不引入个人风格。

## 执行流程

### 1. 定位落点（不要跳过）

- 这个功能属于哪一层：页面 / 容器 / 展示组件 / hook / 工具函数
- 数据从哪来：已有 store、已有请求层、还是需要新接口
- 有没有现成的路由、布局、权限包装要接进去

把落点用一句话写清楚再动手，例如：「在 `pages/order/list` 下加筛选栏，复用 `components/FilterBar`，数据走已有的 `useOrderQuery`」。

### 2. 状态与数据流选型

按「作用域最小」原则，从上往下选第一个够用的：

| 作用域 | 用什么 |
|---|---|
| 单组件内 | `useState` / `ref` |
| 父子几层 | props + 回调，或 `useReducer` |
| 跨页面共享的服务端数据 | 项目已有的请求缓存层（TanStack Query / SWR / Pinia 等） |
| 跨页面共享的客户端状态 | 项目已有的全局 store |

**不要**为了一个开关引入新的状态管理库。**不要**把服务端数据塞进全局 store 再手动同步——那是 bug 的主要来源。

### 3. 实现

- **TypeScript**：不写 `any`。类型从接口定义或已有 model 推导，不重复手写。
- **异步**：每个请求都要处理 loading / empty / error 三态，缺一个就是没写完。
- **副作用**：`useEffect` 的依赖数组要如实填写；需要清理的（定时器、订阅、AbortController）必须清理。
- **列表**：`key` 用稳定业务 id，不用数组下标。
- **样式**：用项目既有方案（Tailwind / CSS Modules / styled-components），不混用第二种。颜色、间距、圆角一律取设计令牌，不写魔法值。

### 4. 可访问性与适配（默认要做，不是加分项）

- 可点击元素用 `button` / `a`，不用带 onClick 的 `div`
- 表单控件有关联的 `label`；图标按钮有 `aria-label`
- 键盘可达：Tab 顺序合理，弹层可 Esc 关闭且焦点被困住
- 暗色模式：颜色走令牌或 `prefers-color-scheme`，不硬编码
- 移动端：用相对单位与弹性布局；宽内容（表格、代码块）在自身容器内横向滚动，页面本身不出现横向滚动条

### 5. 桌面端补充（Electron / Tauri）

- 渲染进程不直接碰文件系统与系统 API，一律走 preload 暴露的受限接口
- IPC 通道名集中定义，参数做校验；不把主进程能力整体暴露给渲染层
- 窗口尺寸、缩放、多显示器下的位置要有兜底

## 自测清单（提交前逐条过）

- [ ] 首屏、空数据、加载中、请求失败四种状态都手动看过
- [ ] 控制台无报错、无 React key/依赖警告
- [ ] 窄屏（375px）与宽屏都不破版，无横向滚动条
- [ ] 亮色与暗色都可读
- [ ] 键盘能完成主流程
- [ ] 新增依赖？说明为什么现有依赖不够用

需要截图或像素级比对时，转 `visual-verification` 技能。

## 反面案例

| 不要这样 | 要这样 |
|---|---|
| 直接新建 `MyButton` | 先搜 `components/` 有没有 `Button` |
| `catch {}` 吞掉错误 | 错误态渲染给用户 + 保留日志 |
| `style={{color:'#3b82f6'}}` | 用主题令牌 `text-primary` |
| 为一个 modal 引入新 UI 库 | 用项目已有的 modal |
| `data as any` | 补全类型或用类型守卫 |
| 改完只看了正常路径 | 按上面清单逐条过 |
