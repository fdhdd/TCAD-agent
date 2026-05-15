# TCAD Agent - 智能仿真助手

一个基于自然语言交互的 Sentaurus TCAD 仿真自动化工具。

[![GitHub](https://img.shields.io/badge/GitHub-TCAD--Agent-blue)](https://github.com/fdhdd/TCAD-agent)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 功能特性

1. **智能对话** - 通过自然语言描述仿真需求
2. **脚本编辑器** - 读取、创建、编辑 TCAD 脚本并保存
3. **脚本类型选择** - 支持生成 `sdevice` 和 `sprocess` 脚本
4. **SSH 远程执行测试** - 可测试脚本是否能通过 SSH 在虚拟机上运行
5. **仿真控制台** - 启动仿真并展示执行日志与状态

## 支持的 TCAD 集成

TCAD Agent 支持三种运行模式：

1. **simulation** (默认): 使用模拟数据，适合开发和测试
2. **local**: 在本地机器上直接运行 Sentaurus TCAD
3. **ssh**: 通过 SSH 连接到运行 Sentaurus TCAD 的虚拟机

详细的配置说明请查看 [VM_SETUP.md](./VM_SETUP.md)

## 技术栈

- **前端**: React 18 + TypeScript + Tailwind CSS
- **后端**: Express.js + TypeScript
- **图表**: Chart.js
- **编辑器**: Monaco Editor
- **状态管理**: Zustand
- **SSH 连接**: ssh2
- **环境配置**: dotenv

## 快速开始

### 环境配置

详细的环境配置步骤请查看：
- [环境配置指南](./ENVIRONMENT_SETUP.md) - 完整的开发环境搭建指南
- [GitHub 仓库设置](./GITHUB_SETUP.md) - 创建和管理 GitHub 仓库

### 前置要求

- Node.js 18+
- npm 或 yarn 或 pnpm
- Git (用于版本控制)

### 安装依赖

```bash
npm install
```

### 运行开发服务器

```bash
npm run dev
```

这将同时启动前端 (http://localhost:3000) 和后端 (默认 http://localhost:3002)。

### 构建生产版本

```bash
npm run build
```

## 项目结构

```
TCAD agent/
├── api/                    # 后端代码
│   ├── index.ts           # Express服务器入口
│   ├── routes/            # API路由
│   └── services/          # 业务逻辑服务
├── src/                   # 前端代码
│   ├── components/        # React组件
│   ├── App.tsx           # 主应用组件
│   ├── main.tsx          # 应用入口
│   ├── store.ts          # Zustand状态管理
│   └── index.css         # 全局样式
├── shared/                # 共享类型定义
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── README.md
└── VM_SETUP.md
```

## 使用指南

1. **开始对话** - 在"智能对话"面板中描述你的仿真需求
2. **选择脚本类型** - 在聊天或脚本生成时选择 `sdevice` 或 `sprocess`
3. **编辑脚本** - 在脚本编辑器中查看、修改和保存生成的 TCAD 脚本
4. **测试连接** - 使用 SSH 测试按钮验证脚本在虚拟机上是否可执行
5. **运行仿真** - 在仿真控制台中启动仿真并查看运行日志
6. **查看报告** - 仿真完成后在报告面板中查看分析结果

## API接口

- `POST /api/chat` - 处理自然语言对话
- `POST /api/script/read` - 读取 TCAD 脚本
- `POST /api/script/write` - 保存 TCAD 脚本
- `POST /api/script/parse` - 解析脚本参数
- `GET /api/script/sample` - 获取示例脚本
- `POST /api/script/generate` - 生成 TCAD 脚本
- `POST /api/simulation/run` - 启动仿真
- `GET /api/simulation/status/:id` - 查询仿真状态
- `POST /api/simulation/test` - 测试脚本 SSH 执行能力
- `POST /api/report/generate` - 生成分析报告

## 注意事项

当前版本已实现脚本生成、SSH 远程执行测试和基础仿真控制功能。实际使用时请注意：

1. AI 生成的脚本仍可能包含语法不兼容项，需要手工检查与调整。
2. SSH 执行依赖虚拟机端的 TCAD 环境、网格文件和权限配置。
3. 当前脚本解析与参数提取功能适用于基础 TCAD 脚本，复杂脚本可能需要扩展支持。
4. 真实生产环境中请配置正确的 `DEEPSEEK_API_KEY`、`SENTAURUS_TCAD_PATH` 和 SSH 连接信息。

## 许可证

MIT
