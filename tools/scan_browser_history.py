# -*- coding: utf-8 -*-
"""扫描浏览器历史，找用户已经用过的 AI 视频/图片站点。"""
import os
import shutil
import sqlite3
import tempfile

pats = ['kling', '可灵', 'runway', 'pika', 'vidu', 'hailuo', 'minimax', '海螺', 'jimeng', '即梦',
        'doubao', '豆包', 'sora', 'veo', 'luma', 'pixverse', '通义', 'wanx', 'liblib', '星流', '海螺']

bases = [
    r'C:\Users\PC-7020\AppData\Local\Microsoft\Edge\User Data',
    r'C:\Users\PC-7020\AppData\Local\Google\Chrome\User Data',
]
profs = ['Default', 'Profile 1', 'Profile 2', 'Profile 3', 'Profile 4']

found = {}
scanned = []
for b in bases:
    if not os.path.isdir(b):
        continue
    for p in profs:
        h = os.path.join(b, p, 'History')
        if not os.path.exists(h):
            continue
        scanned.append(h)
        tmp = os.path.join(tempfile.gettempdir(), 'hist_%d.db' % abs(hash(h)))
        try:
            shutil.copy2(h, tmp)
            con = sqlite3.connect(tmp)
            for pat in pats:
                rows = list(con.execute(
                    "select url, title, visit_count, last_visit_time from urls "
                    "where url like ? order by last_visit_time desc limit 3", ('%' + pat + '%',)))
                for (u, t, c, lt) in rows:
                    found.setdefault(pat, []).append((p, c, (t or '')[:40], u[:110]))
            con.close()
        except Exception as e:
            print('ERR', h, e)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

print('scanned:', len(scanned), 'files')
for k in pats:
    if k in found:
        print('===', k)
        for row in found[k][:5]:
            print('   ', row)
if not found:
    print('no matching history entries')
