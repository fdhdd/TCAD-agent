# TCAD Agent 项目文件说明

## 根目录

- `.env`
  - 本地运行时配置文件，用于设置 TCAD 模式、SSH 连接、工作目录、DeepSeek API 等关键环境变量。

- `.env.example`
  - `.env` 的示例模板，展示可配置项和默认注释。

- `.trae/`
  - VS Code 副本或协作插件产生的临时目录，通常和项目运行无关。

- `.vscode/`
  - VS Code 编辑器配置目录，包含工作区设置、调试配置等。

- `index.html`
  - 前端应用入口 HTML。Vite 会以此文件作为 React 应用挂载页面。

- `package.json`
  - npm 包配置和脚本入口，定义了项目依赖、开发依赖以及常用运行命令。

- `package-lock.json`
  - 锁定当前安装的 npm 依赖版本，保证团队环境一致。

- `postcss.config.js`
  - Tailwind / PostCSS 配置文件，用于前端样式编译。

- `README.md`
  - 项目说明文档，通常包含安装、运行、功能和开发说明。

- `requirements.txt`
  - 目前可能用于记录 Python 或其他工具依赖，视项目需要而定。

- `start.bat`
  - Windows 环境一键启动脚本，可能联合运行前端和后端服务。

- `start_services.bat`
  - 启动所需服务的批处理脚本，例如本地服务器或后台进程。

- `start_tcad.bat`
  - 运行 TCAD 相关服务或环境初始化的 Windows 批处理脚本。

- `tailwind.config.js`
  - Tailwind CSS 的自定义配置文件，定义颜色、插件和样式扩展。

- `tmp_sim_test.js`
  - 项目中的临时测试脚本文件，通常用于本地验证仿真或 SSH 执行逻辑。

- `tsconfig.json`
  - TypeScript 编译器配置，定义源码编译目标、类型检查选项等。

- `tsconfig.node.json`
  - Node.js 环境下的 TypeScript 配置，用于后端/构建工具代码。

- `vite.config.ts`
  - Vite 前端构建工具配置，包含开发服务器代理、插件和端口设置。

- `VM_SETUP.md`
  - 虚拟机或 TCAD 环境搭建说明文档，通常包含 SSH、TCAD 安装和远程执行配置指导。

## API 后端目录 (`api/`)

- `api/index.ts`
  - Express 后端应用入口，初始化中间件、路由并监听 API 端口。

### 路由层 (`api/routes/`)

- `api/routes/chat.ts`
  - 聊天接口路由，处理来自前端的对话消息，并调用 AI 聊天服务。

- `api/routes/report.ts`
  - 报告接口路由，负责生成或读取仿真报告数据。

- `api/routes/script.ts`
  - 脚本管理接口，支持读取、保存、解析、生成 TCAD 脚本，以及示例脚本加载。

- `api/routes/simulation.ts`
  - 仿真接口路由，启动仿真、查询状态、停止、重置，以及脚本执行测试。

### 服务层 (`api/services/`)

- `api/services/agentService.ts`
  - AI 代理服务，负责和 DeepSeek 等语言模型通信，生成 TCAD 脚本、解析行为动作，并处理智能聊天逻辑。

- `api/services/analysisService.ts`
  - 仿真结果分析服务，负责解析输出、提取指标、生成图表数据和报告摘要。

- `api/services/scriptService.ts`
  - 脚本读写解析服务，包括读取本地脚本、保存脚本、解析参数和结构化脚本内容。

- `api/services/simulationService.ts`
  - 仿真管理服务，控制仿真生命周期（启动、跟踪、停止、重置）并协调 TCAD 执行流程。

- `api/services/tcadService.ts`
  - TCAD 执行服务，封装与本地 TCAD 或虚拟机 TCAD 交互的基础逻辑。

- `api/services/virtualMachineTCADService.ts`
  - 虚拟机 SSH 执行服务，负责通过 SSH 连接 VM、传输脚本、执行 sdevice/sprocess、读取远程文件等。

## 共享类型定义 (`shared/`)

- `shared/types.ts`
  - 全局类型声明文件，定义 TCAD 脚本、参数、仿真状态、图表数据、聊天消息和行动类型等。

## 前端目录 (`src/`)

- `src/App.tsx`
  - React 应用主组件，组织页面结构、面板显示和全局布局。

- `src/main.tsx`
  - 前端入口，挂载 React 应用并注册 Vite 开发环境所需模块。

- `src/index.css`
  - 全局样式文件，包含 Tailwind 基础样式和自定义 UI 调整。

- `src/store.ts`
  - Zustand 状态管理配置，保存当前脚本、面板、消息、仿真状态等全局数据。

### 前端组件 (`src/components/`)

- `src/components/ChatPanel.tsx`
  - 聊天面板组件，负责用户输入、消息列表展示、脚本生成提示和快速问题入口。

- `src/components/ParameterPanel.tsx`
  - 参数面板组件，显示并编辑 TCAD 脚本提取出的可调参数。

- `src/components/ReportViewer.tsx`
  - 报告查看组件，用于显示仿真结果报告、图表和分析摘要。

- `src/components/ScriptEditor.tsx`
  - 脚本编辑器组件，提供 Monaco 编辑器、脚本打开/保存、运行仿真和 SSH 测试入口。

- `src/components/Sidebar.tsx`
  - 侧边栏组件，管理导航、面板切换和应用整体布局选项。

- `src/components/SimulationConsole.tsx`
  - 仿真控制台组件，显示运行日志、进度条和仿真状态。

## 其他说明

- `node_modules/`
  - npm 依赖目录，不需要手工编辑，存放项目安装的第三方包。

- `start.bat`, `start_services.bat`, `start_tcad.bat`
  - Windows 启动脚本，方便快速启动前端/后端服务和 TCAD 环境。

该文档聚焦项目核心模块和功能边界，适合作为快速入门或团队协作时的文件说明参考。