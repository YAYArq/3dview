#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3dview 一键远程部署工具
========================
在本机执行一条命令，即可把整套系统部署到任意新服务器：
    自动 SSH 连接 -> 安装依赖(python3/nginx/unzip) -> 上传部署文件
    -> 自动填入公网 IP -> 部署(upload_server.py + systemd + nginx) -> 健康检查

用法:
    python deploy_remote.py <服务器IP> [用户名] [密码]

    服务器IP   必填，目标服务器的公网 IP
    用户名     可选，默认 root
    密码       可选，不填则在运行时提示输入

示例:
    python deploy_remote.py YOUR_SERVER_IP
    python deploy_remote.py YOUR_SERVER_IP root 123456

说明:
    - 依赖本机 Python 的 paramiko（无则先执行 pip install paramiko）
    - 部署完成后访问 http://<服务器IP>:10280/index.html
    - 若云服务器安全组未放行 10280 端口 TCP 入站，请自行放行
"""
import sys
import os
import stat
import getpass
import posixpath

try:
    import paramiko
except ImportError:
    print("[错误] 本机缺少 paramiko，请先执行: pip install paramiko")
    sys.exit(1)

DEFAULT_USER = "root"
DEFAULT_PORT = 22
HTTP_PORT = 10280
REMOTE_SRC_DIR = "/opt/3dview-deploy-src"

# 需要随包上传的文件（相对于本脚本所在目录的 deploy/ 目录）
# 部署所需文件清单；若文件不存在会跳过并警告
DEPLOY_FILES = [
    "index.html",
    "upload_server.py",
    "conf/3dview-upload.service",
    "conf/3dview.nginx.conf",
    "scripts/deploy.sh",
    "scripts/restart.sh",
    "scripts/verify.sh",
    "DEPLOY.md",
    "README.md",
    "LICENSE",
]

REQUIRED_PKGS = ["python3", "nginx", "unzip"]


def find_deploy_dir():
    """定位 deploy 目录：优先本脚本旁的 deploy/，其次仓库根已展平结构。"""
    here = os.path.dirname(os.path.abspath(__file__))
    deploy_dir = os.path.join(here, "deploy")
    if os.path.isdir(deploy_dir):
        return deploy_dir
    # 若脚本就在部署包根目录（展平结构），直接用它
    if os.path.isfile(os.path.join(here, "index.html")) and os.path.isfile(os.path.join(here, "upload_server.py")):
        return here
    return None


def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    host = args[0]
    user = args[1] if len(args) > 1 else DEFAULT_USER
    password = args[2] if len(args) > 2 else None
    if not password:
        password = getpass.getpass("请输入 %s@%s 的密码: " % (user, host))

    deploy_dir = find_deploy_dir()
    if deploy_dir is None:
        print("[错误] 未找到 deploy/ 目录（本脚本应放在 deploy 包或含 index.html 的目录旁）")
        sys.exit(1)
    print("[1/5] 连接服务器 %s@%s ..." % (user, host))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, port=DEFAULT_PORT, username=user, password=password, timeout=20)
    except Exception as e:
        print("[错误] 连接失败: %s" % e)
        sys.exit(1)

    def run(cmd):
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        return out, err

    # 2) 安装依赖
    print("[2/5] 检查并安装依赖(python3/nginx/unzip) ...")
    out, err = run("which python3 nginx unzip 2>/dev/null || true")
    missing = [p for p in REQUIRED_PKGS if p not in out]
    if missing:
        print("    缺少: %s，开始安装 ..." % ", ".join(missing))
        out, err = run("export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" %s 2>&1 | tail -5" % " ".join(missing))
        print("    安装结果: %s" % out.strip()[-200:] if out.strip() else "    完成")
    else:
        print("    依赖已就绪")

    # 3) 上传部署文件
    print("[3/5] 上传部署文件到 %s ..." % REMOTE_SRC_DIR)
    run("rm -rf %s && mkdir -p %s/conf %s/scripts" % (REMOTE_SRC_DIR, REMOTE_SRC_DIR, REMOTE_SRC_DIR))
    sftp = ssh.open_sftp()
    uploaded = []
    for rel in DEPLOY_FILES:
        local = os.path.join(deploy_dir, rel)
        if not os.path.isfile(local):
            print("    跳过(不存在): %s" % rel)
            continue
        remote = posixpath.join(REMOTE_SRC_DIR, rel)
        sftp.put(local, remote)
        uploaded.append(rel)
    sftp.close()
    print("    已上传 %d 个文件" % len(uploaded))

    # 4) 执行部署（注入公网 IP）
    print("[4/5] 远程执行部署脚本 ...")
    cmd = "cd %s && PUBLIC_BASE='http://%s:%d' bash scripts/deploy.sh" % (REMOTE_SRC_DIR, host, HTTP_PORT)
    out, err = run(cmd)
    # 输出部署日志最后 40 行
    lines = [l for l in out.splitlines() if l.strip()]
    print("\n".join(lines[-40:]))
    if err and err.strip():
        print("--- 部署输出尾部(stderr) ---")
        print("\n".join(err.strip().splitlines()[-20:]))

    # 5) 健康检查
    print("[5/5] 健康检查 ...")
    out, err = run("curl -s -o /dev/null -w '%%{http_code}' http://127.0.0.1:%d/index.html" % HTTP_PORT)
    code = out.strip()
    if code == "200":
        print("    部署成功！访问地址: http://%s:%d/index.html" % (host, HTTP_PORT))
        print("    注意: 若无法访问，请确认云安全组已放行 TCP 入站端口 %d" % HTTP_PORT)
    else:
        print("    警告: 首页返回 HTTP %s（部署可能部分完成），请检查上面日志" % code)

    ssh.close()


if __name__ == "__main__":
    main()
