# TCAD Agent GitHub 仓库设置指南

## 概述

本指南将帮助你创建 TCAD Agent 的 GitHub 仓库，并设置标准的 Git 分支结构（master 和 develop 分支）。

## 前置要求

1. **Git 已安装**: 请先按照 [环境配置指南](./ENVIRONMENT_SETUP.md) 安装 Git
2. **GitHub 账户**: 确保你有 GitHub 账户

## 步骤 1: 在 GitHub 上创建仓库

### 1.1 访问 GitHub

1. 打开浏览器，访问 [https://github.com](https://github.com)
2. 登录你的 GitHub 账户

### 1.2 创建新仓库

1. 点击右上角的 **"+"** 按钮，选择 **"New repository"**
2. 填写仓库信息：
   - **Repository name**: `TCAD_Agent` （注意大小写）
   - **Description**: `智能 TCAD 仿真助手 - 基于自然语言交互的 Sentaurus TCAD 自动化工具`
   - **Visibility**: 选择 `Public` 或 `Private`（根据需要）
3. **不要**勾选以下选项：
   - ☑️ Add a README file
   - ☑️ Add .gitignore
   - ☑️ Choose a license
4. 点击 **"Create repository"**

### 1.3 复制仓库 URL

创建完成后，在仓库页面顶部复制 HTTPS URL：
```
https://github.com/YOUR_USERNAME/TCAD_Agent.git
```
将 `YOUR_USERNAME` 替换为你的实际 GitHub 用户名。

## 步骤 2: 初始化本地 Git 仓库

### 2.1 安装 Git

在开始之前，你需要安装 Git。

#### 自动安装 (推荐)

运行项目中的安装脚本：

**PowerShell 脚本 (推荐):**
```powershell
# 右键点击 install_git.ps1，选择"使用 PowerShell 运行"
```

**批处理脚本:**
```cmd
# 双击运行 install_git.bat
```

#### 手动安装

如果自动安装失败，请手动安装：

1. **运行手动安装指南:**
   ```cmd
   # 双击运行 install_git_manual.bat
   ```

2. **或者手动下载:**
   - 访问: https://git-scm.com/downloads
   - 下载 Windows 版本
   - 运行安装包（使用默认设置）

3. **验证安装:**
   ```bash
   git --version
   ```

**重要提示:**
- 使用所有默认安装选项
- 安装完成后可能需要重启命令提示符
- 如果遇到权限问题，以管理员身份运行

### 2.2 初始化仓库

进入项目目录并初始化 Git：

```bash
cd "c:\Users\Administrator\Desktop\TCAD agent"
git init
```

### 2.3 添加文件到仓库

```bash
# 添加所有文件
git add .

# 创建初始提交
git commit -m "Initial commit: TCAD Agent project setup"
```

## 步骤 3: 设置分支结构

### 3.1 创建 develop 分支

```bash
# 创建并切换到 develop 分支
git checkout -b develop
```

### 3.2 创建 master 分支

```bash
# 创建并切换到 master 分支
git checkout -b master
```

### 3.3 验证分支

```bash
# 查看所有分支
git branch -a

# 应该看到：
# * master
#   develop
```

## 步骤 4: 连接到 GitHub 仓库

### 4.1 添加远程仓库

你的仓库URL是：`https://github.com/fdhdd/TCAD-agent.git`

```bash
# 添加 GitHub 仓库为远程 origin
git remote add origin https://github.com/fdhdd/TCAD-agent.git
```

### 4.2 推送分支到 GitHub

```bash
# 推送 master 分支
git push -u origin master

# 推送 develop 分支
git push -u origin develop
```

## 自动化推送脚本

为了简化操作，你可以运行项目中的自动化脚本：

### 选项 1: PowerShell 脚本 (推荐)
```bash
# 右键点击 push_to_github.ps1，选择"使用 PowerShell 运行"
# 或者在 PowerShell 中运行:
.\push_to_github.ps1
```

### 选项 2: 批处理脚本
```bash
# 双击运行 push_to_github.bat
# 或者在命令提示符中运行:
.\push_to_github.bat
```

这些脚本会自动：
- 检查 Git 安装
- 初始化仓库（如果需要）
- 配置用户信息
- 创建必要的分支
- 添加远程仓库
- 推送所有分支

## 步骤 5: 验证设置

### 5.1 检查远程仓库

访问你的 GitHub 仓库页面，应该能看到：
- 所有项目文件已上传
- master 和 develop 两个分支

### 5.2 本地分支状态

```bash
# 查看分支状态
git status
git branch -a

# 查看远程信息
git remote -v
```

## 分支管理策略

### 推荐的工作流程

1. **master 分支**: 保持稳定，只接受来自 develop 的合并
2. **develop 分支**: 主要开发分支，包含最新的功能
3. **feature 分支**: 为新功能创建分支，从 develop 分支创建

### 示例工作流程

```bash
# 从 develop 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/new-feature

# 开发完成后
git checkout develop
git merge feature/new-feature
git push origin develop

# 发布时合并到 master
git checkout master
git merge develop
git push origin master
git tag -a v1.0.0 -m "Release version 1.0.0"
```

## 故障排除

### 常见问题

#### 1. 推送失败：Authentication failed

**原因**: GitHub 需要身份验证
**解决**:
- 使用 Personal Access Token 代替密码
- 或使用 SSH 密钥

#### 2. 推送失败：non-fast-forward

**原因**: 远程分支有新提交
**解决**:
```bash
git pull --rebase origin master
git push origin master
```

#### 3. 分支不存在

**原因**: 分支没有正确创建
**解决**:
```bash
git branch -a  # 查看所有分支
git checkout -b master  # 重新创建
```

#### 4. 远程仓库已存在文件

**原因**: GitHub 仓库不为空
**解决**:
```bash
git pull origin master --allow-unrelated-histories
```

## 自动化脚本

如果你想使用自动化脚本，可以运行项目中的 `setup_git.bat` 文件：

```bash
# 运行自动化设置脚本
.\setup_git.bat
```

**注意**: 脚本中的用户信息需要手动修改为你的实际信息。

## 下一步

仓库设置完成后，你可以：
1. 开始开发新功能
2. 设置 CI/CD 流水线
3. 邀请协作者加入项目
4. 创建项目文档和 Wiki

## 相关文档

- [环境配置指南](./ENVIRONMENT_SETUP.md)
- [项目功能说明](./PROJECT_FILES.md)
- [用户故事文档](./TCAD_AGENT_STORIES.md)