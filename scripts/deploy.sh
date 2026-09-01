#!/usr/bin/env bash
# =========================================================
# 3D模型全景热点展示系统 - 一键部署脚本
# 适用：Ubuntu 22.04 / 24.04（需已安装 python3 与 nginx）
# 运行：sudo bash deploy.sh
# 说明：需以 root 运行；执行后自动部署并启动服务。
# =========================================================
set -euo pipefail

# ---------- 可配置项（按需修改） ----------
# 站点对外端口（需与 conf/3dview.nginx.conf 里的 listen 一致）
HTTP_PORT=10280
# 公网访问地址（upload_server 用固定公网基址生成模型/音频 URL，务必改成你的真实公网 IP:端口）
# 部署地址：可被环境变量覆盖（远程部署工具会自动注入目标 IP）
# 例: PUBLIC_BASE='http://YOUR_SERVER_IP:10280' bash deploy.sh
PUBLIC_BASE="${PUBLIC_BASE:-http://YOUR_SERVER_IP:10280}"

# 部署路径（一般无需修改）
WEB_ROOT="/var/www/3dview"
UPLOAD_DIR="/opt/3dview-upload"
CONFIG_DIR="/opt/3dview-upload/configs"
SVC_FILE="/etc/systemd/system/3dview-upload.service"
NGINX_AVAIL="/etc/nginx/sites-available/3dview"
NGINX_ENABLED="/etc/nginx/sites-enabled/3dview"

echo "==================================================="
echo " 3D模型全景热点展示系统 部署开始"
echo " 对外端口: ${HTTP_PORT}"
echo " PUBLIC_BASE: ${PUBLIC_BASE}"
echo "==================================================="

# ---------- 0) 前置检查 ----------
if [[ $EUID -ne 0 ]]; then
  echo "[错误] 请以 root 运行：sudo bash deploy.sh"; exit 1
fi
for c in python3 nginx; do
  if ! command -v $c >/dev/null 2>&1; then
    echo "[错误] 缺少 $c，请先安装：apt-get install -y python3 nginx"; exit 1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- 1) 站点目录与前端 ----------
echo "[1/6] 部署前端到 ${WEB_ROOT}"
mkdir -p "${WEB_ROOT}/models" "${WEB_ROOT}/music" "${WEB_ROOT}/pdf"
cp -f "${SCRIPT_DIR}/index.html" "${WEB_ROOT}/index.html"

# ---------- 2) 上传/短链后端 ----------
echo "[2/6] 部署上传服务到 ${UPLOAD_DIR}"
mkdir -p "${UPLOAD_DIR}" "${CONFIG_DIR}"
sed "s|^PUBLIC_BASE = .*|PUBLIC_BASE = '${PUBLIC_BASE}'|" \
  "${SCRIPT_DIR}/upload_server.py" > "${UPLOAD_DIR}/upload_server.py"
chmod +x "${UPLOAD_DIR}/upload_server.py"

# ---------- 3) systemd 服务 ----------
echo "[3/6] 安装开机自启服务"
cp -f "${SCRIPT_DIR}/conf/3dview-upload.service" "${SVC_FILE}"
sed -i "s@ExecStart=.*@ExecStart=/usr/bin/python3 ${UPLOAD_DIR}/upload_server.py@" "${SVC_FILE}"
systemctl daemon-reload

# ---------- 4) Nginx 站点 ----------
echo "[4/6] 配置 Nginx（端口 ${HTTP_PORT}）"
cp -f "${SCRIPT_DIR}/conf/3dview.nginx.conf" "${NGINX_AVAIL}"
sed -i "s/listen[[:space:]]*[0-9]*;/listen ${HTTP_PORT};/" "${NGINX_AVAIL}"
ln -sf "${NGINX_AVAIL}" "${NGINX_ENABLED}"
nginx -t && nginx -s reload || { echo "[错误] nginx 配置校验失败，请检查"; exit 1; }

# ---------- 5) 启动上传服务 ----------
echo "[5/6] 启动上传服务"
systemctl enable 3dview-upload >/dev/null 2>&1 || true
systemctl restart 3dview-upload

# ---------- 6) 验证 ----------
echo "[6/6] 验证服务状态"
sleep 1
echo "  - 上传服务: $(systemctl is-active 3dview-upload)"
echo "  - 页面:     $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${HTTP_PORT}/index.html)"
echo "  - 文件列表: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${HTTP_PORT}/list?dir=music)"

echo ""
echo "==================================================="
echo " 部署完成！"
echo " 访问地址: http://${PUBLIC_BASE#http://}/index.html"
echo " 提示: 请在云服务器安全组放行 TCP 入站 ${HTTP_PORT} 端口"
echo "==================================================="
