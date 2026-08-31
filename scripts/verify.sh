#!/usr/bin/env bash
# =========================================================
# 3D模型全景热点展示系统 - 健康检查脚本
# 运行：bash verify.sh [端口]
# =========================================================
set -uo pipefail

PORT="${1:-10280}"
BASE="http://127.0.0.1:${PORT}"
echo "== 服务与端口 =="
systemctl is-active 3dview-upload || true
ss -ltn | grep -E "10280|10281" || echo "（未发现 10280/10281 监听）"
echo ""
echo "== 接口检查 =="
echo " 首页        : $(curl -s -o /dev/null -w '%{http_code}' ${BASE}/index.html)"
echo " 文件列表    : $(curl -s -o /dev/null -w '%{http_code}' ${BASE}/list?dir=music)"
echo " 短链路由    : $(curl -s -o /dev/null -w '%{http_code}' ${BASE}/config/check_routing)  (期望404)"
echo " 上传路由    : $(curl -s -o /dev/null -w '%{http_code}' -X POST ${BASE}/upload)  (期望非404)"
echo ""
echo "== 目录结构 =="
ls -ld /var/www/3dview /var/www/3dview/models /var/www/3dview/music 2>/dev/null || echo "（站点目录缺失）"
echo "上传服务目录: $(ls -ld /opt/3dview-upload 2>/dev/null || echo '缺失')"
