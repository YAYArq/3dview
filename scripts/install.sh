#!/usr/bin/env bash
# =========================================================
# 3dview - GitHub 仓库一键部署（安装依赖 + 部署）
# 适用：Ubuntu / Debian（root）
# 用法在仓库根目录运行：
#   sudo bash install.sh
# 可选：PUBLIC_BASE='http://你的公网IP:10280' sudo bash install.sh
# =========================================================
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "[提示] 需要 root 权限，请用: sudo bash install.sh"
  exit 1
fi

# ---------- 1) 安装系统依赖 ----------
echo "[1/3] 安装系统依赖 (python3 / nginx / unzip) ..."
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 nginx unzip curl
else
  echo "[错误] 未检测到 apt-get，本脚本仅支持 Ubuntu/Debian。"
  exit 1
fi

# ---------- 2) 自动/手动确定公网地址 ----------
# 若未通过环境变量指定 PUBLIC_BASE，则尝试探测本机公网 IP
if [[ -z "${PUBLIC_BASE:-}" ]]; then
  echo "[2/3] 探测公网 IP ..."
  DETECTED_IP="$(curl -s -m 8 ifconfig.me 2>/dev/null || curl -s -m 8 http://ipv4.icanhazip.com 2>/dev/null || true)"
  if [[ -n "${DETECTED_IP}" ]]; then
    PUBLIC_BASE="http://${DETECTED_IP}:10280"
    echo "    检测到公网地址: ${PUBLIC_BASE}"
  else
    PUBLIC_BASE="http://YOUR_SERVER_IP:10280"
    echo "    未探测到公网 IP，使用占位 ${PUBLIC_BASE}（部署后请手动修正）"
  fi
fi
export PUBLIC_BASE

# ---------- 3) 执行部署 ----------
echo "[3/3] 执行部署 ..."
bash scripts/deploy.sh

echo ""
echo "================================================="
echo " 完成！访问地址: http://<服务器公网IP>:10280/index.html"
echo " 若不能访问，请在云安全组放行 TCP 入站 10280 端口"
echo "================================================="
