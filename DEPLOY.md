# 3D 模型全景热点展示系统 — 部署文档

一套用于**全景平台热点跳转**的 3D 模型展示系统：在线多窗口展示 GLB/GLTF 模型，
每个窗口可独立配置展示文本、专属 MP3 背景音乐、动画/旋转，并生成**纯净的短链独立页**
（模型 + 文字 + 音乐，无任何管理按钮），完美嵌入全景网页热点。

> 本部署包已将服务器上的最终运行版本提取。给其他环境部署时，直接用本包即可。

---

## 1. 文件清单

```
deploy/
├── index.html                  # 前端主程序（单文件，全部功能内嵌）
├── upload_server.py            # 上传/文件列表/短链后端（Python3，无第三方依赖）
├── conf/
│   ├── 3dview-upload.service   # systemd 开机自启服务
│   └── 3dview.nginx.conf       # Nginx 站点配置（含 /upload /list /config 反代）
├── scripts/
│   ├── deploy.sh               # 一键部署脚本（root 运行）
│   ├── restart.sh              # 重启服务脚本
│   └── verify.sh               # 健康检查脚本
└── DEPLOY.md                   # 本文档
```

---

## 2. 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 22.04 / 24.04（Debian 亦可） |
| 运行时 | Python 3（内置，无第三方库） |
| Web 服务 | Nginx（1.20+） |
| 权限 | root（安装服务与配置 nginx 需要） |
| 端口 | 对外 10280、内网上传 10281（仅本机监听） |

> 前端依赖 Three.js 等 CDN 资源（jsDelivr）。若部署环境无法访问外网 CDN，
> 需将相关 JS 下载并改成本地引用（见节 7 注意事项）。

---

## 3. 快速部署（推荐：一键脚本）

### 3.1 准备
把整个 `deploy` 目录传到服务器（如 `/root/3dview-deploy`），然后编辑脚本里两处配置：
1. `scripts/deploy.sh` 顶部：
   - `HTTP_PORT=10280`：对外端口
   - `PUBLIC_BASE="http://YOUR_SERVER_IP:10280"`：**改成服务器真实公网 IP**（用于生成模型/音频的可访问 URL）
2. `conf/3dview.nginx.conf` 里 `listen 10280;`：改端口

### 3.2 执行
```bash
cd deploy      # 进入 deploy 目录
sudo bash scripts/deploy.sh
```

脚本会：建站点目录 → 拷贝前端 → 部署上传服务 → 写固定公网 IP → 装 systemd 服务 →
配置 nginx 站点（软链）+ reload → 启动服务 → 打印验证结果。

部署完成后访问：`http://你的IP:10280/index.html`

---

## 4. 手动部署（不跑脚本时）

### 4.1 放置文件
```bash
# 站点根目录（前端 + 模型/音乐上传目录）
mkdir -p /var/www/3dview/models /var/www/3dview/music
cp index.html /var/www/3dview/index.html

# 上传后端
mkdir -p /opt/3dview-upload/configs
cp upload_server.py /opt/3dview-upload/upload_server.py
# 修改 upload_server.py 顶部 PUBLIC_BASE 为你的公网地址：
#   PUBLIC_BASE = 'http://你的IP:10280'
```

### 4.2 装 systemd 服务
```bash
cp conf/3dview-upload.service /etc/systemd/system/3dview-upload.service
systemctl daemon-reload
systemctl enable 3dview-upload
systemctl start 3dview-upload
systemctl status 3dview-upload     # 应显示 active (running)
```

### 4.3 配 Nginx
```bash
cp conf/3dview.nginx.conf /etc/nginx/sites-available/3dview
ln -sf /etc/nginx/sites-available/3dview /etc/nginx/sites-enabled/3dview
nginx -t        # 校验通过
nginx -s reload
```

### 4.4 放行端口
在你的云厂商安全组（如阿里云）放行 **TCP 入站 10280**。

---

## 5. 目录与端口速查

| 类型 | 路径/端口 | 说明 |
|------|-----------|------|
| 前端页面 | `/var/www/3dview/index.html` | 主程序 |
| 模型目录 | `/var/www/3dview/models/` | 上传的 GLB/GLTF（前台可配） |
| 音乐目录 | `/var/www/3dview/music/` | 上传的 MP3 |
| 短链配置 | `/opt/3dview-upload/configs/` | 独立链接存的窗口配置（JSON） |
| 上传服务 | `127.0.0.1:10281` | 内网，仅本机 listen，不对外 |
| 对外服务 | `10280` | Nginx（+ /upload /list /config 反代到 10281） |

### 后端接口
| 路径 | 方法 | 说明 |
|------|------|------|
| `/upload` | POST | multipart 上传，`save_dir` 指定保存目录（models/music） |
| `/list?dir=music` | GET | 列出某目录已上传文件（白名单：models、music） |
| `/config` | POST | 保存短链配置，返回 8 位短 ID（带同一 id 则复用覆盖） |
| `/config/<id>` | GET | 读取短链配置 |

---

## 6. 运维常用命令

```bash
sudo bash deploy/scripts/restart.sh   # 一键重启上传服务 + nginx
sudo bash deploy/scripts/verify.sh    # 健康检查（端口、接口、目录）

systemctl restart 3dview-upload        # 重启上传服务
journalctl -u 3dview-upload -f         # 查看上传服务实时日志
systemctl stop|start 3dview-upload     # 停止/启动
nginx -s reload                        # 重载 nginx
```

---

## 7. 注意事项

1. **公网 IP 必改**：`upload_server.py` 的 `PUBLIC_BASE` 与 deploy.sh 里的 `PUBLIC_BASE`
   必须改成服务器**真实公网 IP:端口**。否则前端拿到的模型/音频地址不带正确 host/端口，无法加载播放。
2. **模型/音乐文件名含中文/空格**：系统已自动做 URL 百分号编码，无需你处理；上传时保留中文名即可。
3. **短链稳定**：同一窗口多次复制链接返回相同 ID（已持久化到 localStorage）。删除窗口后其短链配置仍留在服务器。如需要清理，删除 `/opt/3dview-upload/configs/*.json`。
4. **防火墙上传**：上传后端仅监听 127.0.0.1，不对外暴露；对外只开 10280，安全组请勿再开 10281。
5. **CDN 依赖**：前端依赖 jsDelivr 的 Three.js。若内网/受限网络无法访问，需事先把
   `three.min.js`、`OrbitControls.js`、`GLTFLoader.js` 三个文件下载并改 `index.html` 中对应 `<script src>` 为本地相对路径。
6. **大文件上传**：nginx 已设 `client_max_body_size 300m`；上传超时 300s。超大模型如仍报 413 或超时，可放大该值。

---

## 8. 功能一览（部署完成后即具备）

- 首页多窗口 3D 模型展示（独立相机/光照/控制器，互不干扰），支持拖拽/滚轮/右键
- 支持 **GLB / GLTF / OBJ（含 .mtl 贴图多文件）/ FBX（含动画）** 四种模型
  - 模型本地预览支持多选（OBJ 连同 .mtl 与贴图一起选择）
  - 上传到服务器后，模型 URL 若为 OBJ 会自动加载同目录同名的 .mtl 贴图
- 模型动画自动播放，解决纯白不显示（GLB/FBX 均支持）
- 上传模型/音乐/PDF 到服务器
- 每个窗口独立：标题、展示文本（可折叠）、专属 MP3（可下拉选择/上传）、自动旋转、动画速度、背景色、**独立链接 ID**
- 底层控制条（画布中间最下方、水平居中）：**PDF 按钮** | **文本折叠按钮** | **背景音乐播放/暂停按钮**
  - PDF 按钮：打开主页上传的全局 PDF（新窗口）
  - 文本按钮：收起/展开模型下方展示文本
- 一键复制**纯净短链独立页**（`?id=xxx`），适配全景网页热点：仅模型 + 文字 + 音乐 + PDF
  - 短链 ID 可在主页配置面板 **自定义固定 ID**（字母/数字，1-32 位）；留空则自动生成
- 全量 localStorage 持久化，刷新保留（含短链 ID）

### 8.1 新增目录/用途
| 目录 | 说明 |
|------|------|
| `/var/www/3dview/models/` | GLB/GLTF/OBJ/FBX 模型（OBJ 的多文件用 `models/<模型名>/` 子目录）|
| `/var/www/3dview/music/` | 背景音乐 MP3 |
| `/var/www/3dview/pdf/`  | 全局 PDF（主页「上传 PDF」）|

### 8.2 注意事项补充
- OBJ 若带外部贴图，请把 `.obj + .mtl + 贴图文件` **一起选择**上传；上传后端会放到同一子目录。
- OBJ 上传重复时，同名贴图可能被自动加后缀改名，若遇到贴图丢失，建议换一个模型子目录名或先删旧目录。

