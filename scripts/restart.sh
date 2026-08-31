#!/usr/bin/env bash
# =========================================================
# 3D模型全景热点展示系统 - 重启/运维脚本
# 运行：sudo bash restart.sh
# 功能：重启上传服务与 nginx，并查看最近日志
# =========================================================
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[错误] 请以 root 运行：sudo bash restart.sh"; exit 1
fi

echo "[1/2] 重启上传服务"
systemctl restart 3dview-upload
sleep 1
systemctl status 3dview-upload --no-pager -l | head -12

echo ""
echo "[2/2] 重载 Nginx"
nginx -t && nginx -s reload

echo ""
echo "==================================================="
echo " 完成！状态："
echo "  上传服务: $(systemctl is-active 3dview-upload)"
echo "  端口监听: $(ss -ltn | grep -E '10280|10281' || echo '未监听')"
echo "==================================================="
echo "常用命令："
echo "  查看运行日志 : journalctl -u 3dview-upload -f"
echo "  停止/启动服务: systemctl stop|start 3dview-upload"
