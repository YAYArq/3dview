#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D 模型上传服务
- 监听 127.0.0.1:10281（仅本机，由 Nginx 反向代理 /upload 到此）
- POST /upload 接收 multipart 文件，保存到 /var/www/3dview 下的可配置目录
- 返回 JSON：{ ok, url, path, size, filename }
- 字节级解析 multipart，正确还原中文文件名
- 路径安全：save_dir 必须限定在 WEB_ROOT 内，防目录穿越
"""
import os
import re
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB_ROOT = '/var/www/3dview'          # 站点根目录
DEFAULT_SUBDIR = 'models'             # 默认保存子目录
PORT = 10281
MAX_BODY = 300 * 1024 * 1024
LISTABLE_DIRS = ('models', 'music', 'pdf')  # 允许 GET /list 列出的子目录（白名单）
PUBLIC_BASE = 'http://YOUR_SERVER_IP:10280'  # 公网对外访问地址（host/端口固定）—— 部署时由 deploy.sh 替换为你的真实公网 IP

def _abs_url(rel):
    """生成可被浏览器直接访问的服务器资源 URL（固定公网基址 + 路径百分号编码）"""
    rel = rel.replace(os.sep, '/')
    return PUBLIC_BASE + '/' + urllib.parse.quote(rel, safe='/@')



# 短链配置存储目录（独立链接只带短 ID，长文本/配置存服务器）
CONFIG_DIR = '/opt/3dview-upload/configs'
_ID_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


def _make_short_id():
    import random
    return ''.join(random.choice(_ID_ALPHABET) for _ in range(8))


def _config_path(cid):
    if not cid or not re.fullmatch(r'[A-Za-z0-9]{1,32}', cid or ''):
        return None
    return os.path.join(CONFIG_DIR, cid + '.json')


def _read_config(cid):
    p = _config_path(cid)
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            obj = json.load(f)
        return obj
    except Exception:
        return None




def decode_filename(raw):
    """还原 UTF-8 编码的中文文件名（浏览器把 UTF-8 字节直接放入 header，以 latin-1 传输）"""
    if not raw:
        return raw
    try:
        restored = raw.encode('latin-1').decode('utf-8')
        if any(ord(c) > 127 for c in restored):
            return restored
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return raw


def parse_multipart(body, boundary):
    """字节级解析 multipart/form-data，返回 [(name, filename, data)]"""
    parts = []
    sep = b'--' + boundary.encode('utf-8')
    chunks = body.split(sep)
    for chunk in chunks:
        chunk = chunk.strip(b'\r\n')
        if chunk in (b'', b'--'):
            continue
        if b'\r\n\r\n' in chunk:
            header_blob, content = chunk.split(b'\r\n\r\n', 1)
        else:
            header_blob, content = chunk, b''
        header_text = header_blob.decode('latin-1', 'ignore')
        # 提取 name / filename / filename*
        name = None
        filename = None
        for m in re.finditer(r'([\w*]+)=(?:"((?:[^"\\]|\\.)*)"|([^;\s]+))', header_text):
            key = m.group(1)
            val = m.group(2) if m.group(2) is not None else m.group(3)
            if key == 'name':
                name = val
            elif key == 'filename':
                filename = val
            elif key == 'filename*':
                # 形如 UTF-8''%E5%B2%A9.glb
                if "'" in val:
                    _, _, encval = val.partition("''")
                    try:
                        filename = urllib.parse.unquote(encval)
                    except Exception:
                        filename = encval
                else:
                    filename = val
        if name == 'file' and filename:
            filename = decode_filename(filename)
        parts.append((name, filename, content))
    return parts


class UploadHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With')

    def _send_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/list'):
            # GET /list?dir=music => 列出指定子目录下文件（含子目录），带公网 URL
            from urllib.parse import urlparse, parse_qs
            try:
                q = parse_qs(urlparse(self.path).query)
            except Exception:
                q = {}
            sub = (q.get('dir') or [''])[0].strip().strip('/')
            if not sub:
                self._send_json(400, {'ok': False, 'error': '缺少 dir 参数（models 或 music）'})
                return
            if sub not in LISTABLE_DIRS:
                self._send_json(403, {'ok': False, 'error': '不允许列出该目录'})
                return
            base = os.path.normpath(os.path.join(WEB_ROOT, sub))
            if base != WEB_ROOT and not base.startswith(WEB_ROOT + os.sep):
                self._send_json(403, {'ok': False, 'error': '目录越界'})
                return
            if not os.path.isdir(base):
                self._send_json(200, {'ok': True, 'dir': sub, 'files': []})
                return
            # host 头经 nginx 反代会丢失端口(如 10280)，故用固定公网地址生成 URL，
            # 同时把中文/空格等路径段做百分号编码，保证浏览器可直接访问。
            files = []
            for root, dirs, names in os.walk(base):
                for n in sorted(names):
                    full = os.path.join(root, n)
                    if not os.path.isfile(full):
                        continue
                    rel = os.path.relpath(full, WEB_ROOT).replace(os.sep, '/')
                    try:
                        fsize = os.path.getsize(full)
                    except OSError:
                        fsize = 0
                    files.append({
                        'name': n,
                        'path': rel,
                        'url': _abs_url(rel),
                        'size': fsize,
                        'mtime': int(os.path.getmtime(full))
                    })
            self._send_json(200, {'ok': True, 'dir': sub, 'files': files})
            return
        # GET /config/<id> => 读取服务器端存储的短链配置
        if self.path.startswith('/config/'):
            cid = self.path[len('/config/'):].split('?')[0].strip('/')
            info = _read_config(cid)
            if info is None:
                self._send_json(404, {'ok': False, 'error': '配置不存在或已失效'})
                return
            self._send_json(200, {'ok': True, 'id': cid, 'config': info})
            return
        self._send_json(200, {'ok': True, 'name': '3dview-upload', 'web_root': WEB_ROOT})

    def do_POST(self):
        # POST /config => 保存短链配置，body 为 JSON，返回 { ok, id }
        if self.path.rstrip('/') == '/config':
            try:
                length = int(self.headers.get('Content-Length', 0) or 0)
                if length <= 0 or length > 1024 * 1024:
                    raise ValueError('content too large or empty')
                raw = self.rfile.read(length)
                cfg = json.loads(raw.decode('utf-8'))
                if not isinstance(cfg, dict) or not cfg.get('url'):
                    self._send_json(400, {'ok': False, 'error': '配置缺少 url'})
                    return
                allow = ('url', 'title', 'text', 'mp3', 'autoRotate', 'rotateSpeed',
                         'playAnimation', 'animSpeed', 'background', 'volume', 'pdf')
                store = {k: cfg[k] for k in allow if k in cfg}
                try:
                    os.makedirs(CONFIG_DIR, exist_ok=True)
                except Exception as e:
                    self._send_json(500, {'ok': False, 'error': '创建配置目录失败: ' + str(e)})
                    return
                cid = cfg.get('id') or _make_short_id()
                if not _config_path(cid):
                    cid = _make_short_id()
                try:
                    with open(_config_path(cid), 'w', encoding='utf-8') as f:
                        json.dump(store, f, ensure_ascii=False)
                except Exception as e:
                    self._send_json(500, {'ok': False, 'error': '保存配置失败: ' + str(e)})
                    return
                self._send_json(200, {'ok': True, 'id': cid})
                return
            except json.JSONDecodeError:
                self._send_json(400, {'ok': False, 'error': '无效的 JSON 配置'})
                return
            except Exception as e:
                self._send_json(500, {'ok': False, 'error': '读取配置失败: ' + str(e)})
                return

        if self.path.rstrip('/') != '/upload':
            self._send_json(404, {'ok': False, 'error': 'not found'})
            return

        ctype = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', 0) or 0)
        if length <= 0 or length > MAX_BODY:
            self._send_json(413, {'ok': False, 'error': '文件过大或为空（上限 300MB）'})
            return
        m = re.search(r'boundary=([^;]+)', ctype)
        if not m:
            self._send_json(400, {'ok': False, 'error': '缺少 boundary'})
            return
        boundary = m.group(1).strip('"')
        body = self.rfile.read(length)

        parts = parse_multipart(body, boundary)
        file_data = None
        filename = None
        save_dir = ''
        for (pname, pfilename, pdata) in parts:
            if pname == 'file' and pfilename:
                file_data = pdata
                filename = pfilename
            elif pname == 'save_dir':
                save_dir = pdata.decode('utf-8', 'ignore').strip()

        if file_data is None or not filename:
            self._send_json(400, {'ok': False, 'error': '未收到文件（请使用字段名 file）'})
            return

        # 清理文件名（去掉路径分隔符与危险字符，保留中文，防止路径穿越）
        filename = os.path.basename(filename or 'model.glb')
        filename = re.sub(r'[\x00-\x1f\\/:*?"<>|]', '_', filename)
        filename = filename.strip('. ')
        if not filename or filename in ('.', '..'):
            filename = 'model.glb'
        if len(filename) > 120:
            name, ext = os.path.splitext(filename)
            filename = name[:100] + ext

        # 计算目标目录：默认 models，可指定 save_dir，但必须位于 WEB_ROOT 内
        if save_dir:
            target = os.path.normpath(os.path.join(WEB_ROOT, save_dir))
            if target != WEB_ROOT and not target.startswith(WEB_ROOT + os.sep):
                self._send_json(403, {'ok': False, 'error': '保存目录越界，仅允许站点目录内'})
                return
        else:
            target = os.path.join(WEB_ROOT, DEFAULT_SUBDIR)

        try:
            os.makedirs(target, exist_ok=True)
            # 同名文件自动加序号，避免覆盖
            name, ext = os.path.splitext(filename)
            final = filename
            i = 1
            while os.path.exists(os.path.join(target, final)):
                final = f'{name}_{i}{ext}'
                i += 1
            path = os.path.join(target, final)
            with open(path, 'wb') as f:
                f.write(file_data)
        except Exception as e:
            self._send_json(500, {'ok': False, 'error': '保存失败: ' + str(e)})
            return

        rel = os.path.relpath(path, WEB_ROOT).replace(os.sep, '/')
        url = _abs_url(rel)
        self._send_json(200, {
            'ok': True,
            'url': url,
            'path': path,
            'size': len(file_data),
            'filename': final,
            'saved_dir': rel.rsplit('/', 1)[0]
        })


if __name__ == '__main__':
    print(f'3dview upload server listening on 127.0.0.1:{PORT}, root={WEB_ROOT}')
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), UploadHandler)
    srv.serve_forever()
