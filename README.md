# 3D 模型全景热点展示系统

一套用于全景平台热点跳转的 3D 模型展示系统：在线多窗口展示 GLB/GLTF/OBJ/FBX 模型，
每个窗口可独立配置展示文本、专属 MP3 背景音乐、PDF、动画/旋转、背景色等，并可生成
纯净短链独立页（模型 + 文字 + 音乐 + PDF），完美嵌入全景网页热点。

## 功能特性

- 多格式模型：支持 GLB、GLTF、OBJ（含 .mtl 贴图多文件）、FBX（含动画）
- 自动动画：模型动画自动播放，解决纯白不显示问题
- 多窗口独立：每窗口独立相机/光照/控制器/动画，互不干扰
- 每实例独立配置：标题（可改名）、展示文本（可折叠）、专属 MP3、PDF、自动旋转、动画速度、背景色、独立链接 ID
- 服务器上传：模型 / 音乐 / PDF 一键上传到服务器（供各实例配置面板选择）
- 纯净独立页：一键复制短链（?id=xxx），仅模型 + 文字 + 音乐 + PDF，适配全景网页热点
- 持久化：窗口与配置存 localStorage，刷新保留

## 目录结构

```
├── index.html                  # 前端主程序（单文件，全部功能内嵌）
├── upload_server.py            # 上传 / 文件列表 / 短链 后端（Python3，零依赖）
├── conf/
│   ├── 3dview-upload.service   # systemd 开机自启服务
│   └── 3dview.nginx.conf       # Nginx 站点配置
├── scripts/
│   ├── deploy.sh               # 一键部署脚本（服务器端）
│   ├── deploy_remote.py        # 一键远程部署脚本（本机运行，可选）
│   ├── restart.sh              # 重启脚本
│   └── verify.sh               # 健康检查脚本
├── DEPLOY.md                   # 完整部署文档
├── README.md                   # 本文档
└── LICENSE                     # MIT 开源许可
```

## 快速部署

### 方式一：服务器端脚本（在目标服务器上执行）

环境要求：Ubuntu 22.04/24.04、Python3、Nginx。

```bash
# 1. 上传仓库到服务器并进入目录
# 2. 编辑 scripts/deploy.sh，把 PUBLIC_BASE 改成你的真实公网 IP
#    PUBLIC_BASE="http://你的公网IP:10280"
# 3. 一键部署（需要 root）
sudo bash scripts/deploy.sh
```

### 方式一（最简单）：从 GitHub 公开仓库直接一键部署

在目标服务器上，直接用 git 克隆本公开仓库并一键部署（无需手动传文件，可自动探测公网 IP）：

```bash
# 安装 git 与依赖并克隆
sudo apt-get update && sudo apt-get install -y git python3 nginx unzip curl
git clone https://github.com/YAYArq/3dview.git
cd 3dview

# 一键部署（自动装依赖+探测公网IP+部署；需要 root）
sudo bash install.sh

# 或者手动指定公网地址（推荐，最稳妥）
PUBLIC_BASE='http://你的公网IP:10280' sudo bash install.sh
```

之后访问 `http://你的公网IP:10280/index.html`，并到云安全组放行 **TCP 入站 10280**。

> `install.sh` 会自动：安装 python3/nginx/unzip -> 探测/指定公网 IP -> 调用 `scripts/deploy.sh` 完成 systemd + Nginx 部署。

### 方式二：本机一键远程部署（推荐，一条命令搞定）

在你的本机电脑上（已安装 Python 与 paramiko）运行：

```bash
python scripts/deploy_remote.py  <目标服务器公网IP>   [用户名] [密码]
```

会自动完成：SSH 连接 -> 安装 python3/nginx/unzip -> 上传部署文件 ->
自动填入目标公网 IP -> 部署(upload_server.py + systemd + nginx) -> 健康检查。

示例：
```bash
python scripts/deploy_remote.py YOUR_SERVER_IP
python scripts/deploy_remote.py YOUR_SERVER_IP root 我的密码
```

> 若本机缺 paramiko：`pip install paramiko`

部署完成后访问：`http://你的IP:10280/index.html`
请在云安全组放行 TCP 入站 10280 端口。

> 详细步骤、手动部署、目录/端口速查、运维命令、注意事项见 DEPLOY.md。

## 使用简介

1. 打开主页后点「上传模型 / 上传音乐 / 上传 PDF」把素材传到服务器。
2. 点「新建实例」创建空白实例，再打开该窗口的「配置」面板：
   - 选择/上传模型、改实例名称、设置展示文本（可折叠）、MP3、PDF、自动旋转、背景色等。
3. 点窗口的链接按钮复制独立短链，粘贴到全景平台作为「网页热点」地址。
4. 用户点击热点 -> 打开纯净独立页：模型 + 文本 + 背景音乐 + PDF。

## 关于背景音乐自动播放

浏览器有自动播放安全策略：用户没有交互时禁止网页自动出声（这是 Chrome/Safari 强制规则，
任何网页都无法绕过）。页面已做最佳处理：
- 进入独立页先尝试静音起播；若被拦截则显示「点击开始播放」封面，一点即出声并消失。
- 若独立页被全景平台的 iframe 嵌入，还需在 iframe 标签加 allow="autoplay" 属性才可以自动播放。

## 安全提示

- 本仓库为源码/部署包，不含任何真实服务器 IP、密码或密钥。部署时需把 PUBLIC_BASE 替换为你的公网地址。
- 上传后端仅监听 127.0.0.1，不对外暴露；对外只需放行 Nginx 端口。

## 开源许可

本项目使用 MIT License。使用/修改/再分发请保留版权与许可声明。
