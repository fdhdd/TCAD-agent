# TCAD Agent 环境配置指南

## 概述

本指南将一步步教你为 TCAD Agent 项目配置开发环境。TCAD Agent 是一个基于自然语言交互的 Sentaurus TCAD 仿真自动化工具，支持三种运行模式：simulation（模拟）、local（本地）和 ssh（远程虚拟机）。

## 系统要求

### 最低系统要求
- **操作系统**: Windows 10/11, macOS 10.15+, Ubuntu 18.04+
- **内存**: 至少 8GB RAM
- **磁盘空间**: 至少 2GB 可用空间
- **网络**: 稳定的互联网连接

### 推荐配置
- **操作系统**: Windows 11 或 Ubuntu 20.04+
- **内存**: 16GB RAM 或更多
- **磁盘空间**: 10GB 可用空间
- **处理器**: 多核处理器 (推荐 4 核以上)

## 步骤 1: 安装 Node.js

TCAD Agent 前后端都基于 Node.js 开发，需要 Node.js 18 或更高版本。

### Windows 用户

1. 访问 [Node.js 官网](https://nodejs.org/)
2. 下载 **LTS 版本** 的安装包
3. 运行安装包，按照默认设置安装
4. 安装完成后，打开命令提示符或 PowerShell，验证安装：

```bash
node --version
npm --version
```

### macOS 用户

推荐使用 Homebrew 安装：

```bash
# 安装 Homebrew (如果还没有)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Node.js
brew install node

# 验证安装
node --version
npm --version
```

### Linux (Ubuntu/Debian) 用户

```bash
# 更新包管理器
sudo apt update

# 安装 Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# 验证安装
node --version
npm --version
```

### 验证 Node.js 安装

运行以下命令，确保版本正确：

```bash
node --version  # 应该显示 v18.x.x 或更高
npm --version   # 应该显示 8.x.x 或更高
```

### 安装 Git (版本控制)

TCAD Agent 使用 Git 进行版本控制，你需要安装 Git 来管理代码和推送到 GitHub。

#### 自动安装 (推荐)

项目中提供了自动安装脚本：

**PowerShell 脚本 (推荐):**
```powershell
# 右键点击 install_git.ps1，选择"使用 PowerShell 运行"
```

**批处理脚本:**
```cmd
# 双击运行 install_git.bat
```

#### 手动安装

1. 访问 [Git 官网](https://git-scm.com/downloads)
2. 下载 Windows 版本的安装包
3. 运行安装包，按照默认设置安装
4. 安装完成后，验证安装：

```bash
git --version
```

#### 验证 Git 安装

运行以下命令确保 Git 正确安装：

```bash
git --version  # 应该显示版本信息
```

如果遇到权限问题，可能需要重启命令提示符或 PowerShell。

## 步骤 3: 获取项目代码

### 方法 1: 从 Git 仓库克隆 (推荐)

```bash
git clone <repository-url>
cd tcad-agent
```

### 方法 2: 下载 ZIP 包

1. 从项目仓库下载 ZIP 文件
2. 解压到本地目录
3. 进入项目目录

## 步骤 4: 安装项目依赖

进入项目根目录，安装所有依赖：

```bash
npm install
```

这个命令会安装所有必要的依赖包，包括前端和后端的依赖。安装过程可能需要几分钟。

### 可能的安装问题

如果遇到权限问题，在 macOS/Linux 上使用：

```bash
sudo npm install
```

如果遇到网络问题，可以尝试使用国内镜像：

```bash
npm config set registry https://registry.npmmirror.com
npm install
```

## 步骤 5: 配置虚拟机 SSH 连接 (可选)

如果要使用 SSH 模式连接到虚拟机中的 Sentaurus TCAD，需要进行以下配置。

### 5.1 准备虚拟机

确保虚拟机满足以下要求：
- 已安装 Sentaurus TCAD
- SSH 服务已启用
- 用户有执行 TCAD 的权限

### 5.2 配置 SSH 密钥 (推荐方式)

1. **生成 SSH 密钥对**：

```bash
# 在项目根目录下生成密钥
ssh-keygen -t rsa -b 4096 -f .ssh/tcad_agent_key -N ""
```

2. **将公钥复制到虚拟机**：

```bash
# 替换为你的虚拟机信息
ssh-copy-id -i .ssh/tcad_agent_key.pub username@virtual-machine-ip
```

### 5.3 创建环境配置文件

在项目根目录创建 `.env` 文件：

```env
# TCAD 运行模式: simulation, local, ssh
TCAD_MODE=ssh

# SSH 连接配置
SSH_HOST=192.168.1.100
SSH_PORT=22
SSH_USERNAME=your_username
SSH_PRIVATE_KEY=./.ssh/tcad_agent_key
SSH_REMOTE_DIR=/home/your_username/tcad_workspace

# 可选：如果 TCAD 不在系统 PATH 中
# SENTAURUS_TCAD_PATH=/usr/local/sentaurus
```

### 5.4 测试 SSH 连接

```bash
# 测试连接
ssh -i .ssh/tcad_agent_key username@192.168.1.100

# 在虚拟机中测试 TCAD
which sdevice
sdevice -version
```

### 5.5 配置虚拟机工作目录

在虚拟机中创建工作目录：

```bash
# SSH 到虚拟机
ssh -i .ssh/tcad_agent_key username@192.168.1.100

# 创建工作目录
mkdir -p ~/tcad_workspace
chmod 755 ~/tcad_workspace
```

## 步骤 6: 启动开发服务器

### 开发模式启动

```bash
npm run dev
```

这个命令会同时启动前端和后端服务器：
- 前端: http://localhost:5173 (Vite 开发服务器)
- 后端: http://localhost:3000 (Express 服务器)

### 单独启动

如果你需要单独启动前端或后端：

```bash
# 只启动前端
npm run dev:frontend

# 只启动后端
npm run dev:backend
```

## 步骤 7: 验证安装

### 7.1 检查服务状态

打开浏览器访问 http://localhost:5173，应该能看到 TCAD Agent 的界面。

### 7.2 测试基本功能

1. **测试聊天功能**: 在聊天面板中输入一些简单的指令
2. **测试脚本编辑器**: 尝试创建或编辑一个简单的 TCAD 脚本
3. **测试 SSH 连接** (如果配置了): 使用测试按钮验证 SSH 连接

### 7.3 运行构建测试

```bash
# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

## 故障排除

### 常见问题

#### 1. Node.js 版本问题
```
Error: Node.js version 18+ is required
```
**解决**: 升级 Node.js 到 18 或更高版本

#### 2. 端口占用
```
Error: Port 3000 is already in use
```
**解决**: 关闭占用端口的程序，或修改端口配置

#### 3. SSH 连接失败
```
Error: connect ECONNREFUSED
```
**解决**:
- 检查虚拟机 IP 地址和端口
- 确保 SSH 服务正在运行
- 验证防火墙设置
- 检查 SSH 密钥权限 (应该只有所有者可读)

#### 4. 依赖安装失败
```
npm ERR! code ENOTFOUND
```
**解决**:
- 检查网络连接
- 尝试使用 VPN 或代理
- 使用国内镜像: `npm config set registry https://registry.npmmirror.com`

#### 5. 构建失败
```
Error: Cannot find module 'xxx'
```
**解决**:
- 重新运行 `npm install`
- 删除 node_modules 和 package-lock.json，然后重新安装

### 获取帮助

如果遇到问题：
1. 检查控制台错误信息
2. 查看项目文档中的故障排除部分
3. 在项目仓库提交 issue
4. 查看 [VM_SETUP.md](./VM_SETUP.md) 获取更多虚拟机配置详情

## 下一步

环境配置完成后，你可以：
1. 开始开发新功能
2. 学习项目架构
3. 贡献代码到项目
4. 部署到生产环境

祝你使用愉快！