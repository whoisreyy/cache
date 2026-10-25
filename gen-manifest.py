#!/usr/bin/env python3
"""Buat data.json (manifest game files) + update.json untuk launcher dari folder files/.

Contoh:
  python3 gen_manifest.py --root ./files --user USERNAME --repo NAMA-REPO
Opsi: --branch main --release-tag v1.0.0 --big-mb 90 --out data.json
  --all-release  : SEMUA file diarahkan ke GitHub Releases (Opsi A), repo hanya berisi JSON
  --update-json  : sekaligus tulis update.json (app_status, game_version, data_list_url)
  --game-version 1.0.0
GPU ditentukan dari nama file: *.dxt.* -> dxt, *.pvr.* -> pvr, *.etc.* -> etc, selain itu all.
File > --big-mb (atau semua, dgn --all-release) diarahkan ke GitHub Releases. Nama asset = path dgn '/'->'__';
file siap-upload dengan nama itu disiapkan di --stage-dir.
"""
import argparse, hashlib, json, os, re, sys

def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()

def gpu_of(name):
    m = re.search(r'\.(dxt|pvr|etc)\.', name.lower())
    return m.group(1) if m else 'all'

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True)
ap.add_argument('--user', required=True)
ap.add_argument('--repo', required=True)
ap.add_argument('--branch', default='main')
ap.add_argument('--release-tag', default='v1.0.0')
ap.add_argument('--big-mb', type=float, default=90)
ap.add_argument('--out', default='data.json')
ap.add_argument('--all-release', action='store_true')
ap.add_argument('--stage-dir', default='release_upload', help='folder berisi file siap-upload ke Release (nama datar)')
ap.add_argument('--update-json', action='store_true')
ap.add_argument('--game-version', default='1.0.0')
a = ap.parse_args()

raw = f'https://raw.githubusercontent.com/{a.user}/{a.repo}/{a.branch}/files/'
rel = f'https://github.com/{a.user}/{a.repo}/releases/download/{a.release_tag}/'
files, names, big = [], {}, []
for d, _, fs in os.walk(a.root):
    for n in sorted(fs):
        p = os.path.join(d, n)
        path = os.path.relpath(p, a.root).replace(os.sep, '/')
        size = os.path.getsize(p)
        is_big = a.all_release or size > a.big_mb * 1024 * 1024
        asset = path.replace('/', '__')   # nama asset di Release = path dengan '/' -> '__' (anti bentrok)
        if is_big:
            if asset in names:
                sys.exit(f'Nama asset bentrok di Releases: {asset}')
            names[asset] = path
            big.append((path, size, asset, p))
        url = (rel + asset) if is_big else (raw + path)
        files.append({'name': n, 'path': path, 'size': size, 'hash': md5(p), 'url': url, 'gpu': gpu_of(n)})
files.sort(key=lambda f: f['path'].lower())
with open(a.out, 'w') as f:
    json.dump({'files': files}, f, indent=4)
if a.update_json:
    uj = {'app_status': True, 'game_version': a.game_version,
          'data_list_url': f'https://raw.githubusercontent.com/{a.user}/{a.repo}/{a.branch}/data.json',
          'samp_list_url': '', 'app_testers': []}
    with open(os.path.join(os.path.dirname(os.path.abspath(a.out)), 'update.json'), 'w') as f:
        json.dump(uj, f, indent=4)
    print('update.json ditulis')
print(f'{len(files)} file, {sum(f["size"] for f in files)/1e6:.1f} MB -> {a.out}')
cnt = {}
for f in files: cnt[f['gpu']] = cnt.get(f['gpu'], 0) + 1
print('per GPU:', cnt)
if big and not a.all_release:
    # Tulis daftar file besar ke .gitignore (di samping --out) supaya tidak ikut ter-commit/push ke repo.
    gi = os.path.join(os.path.dirname(os.path.abspath(a.out)), '.gitignore')
    cur = open(gi).read().splitlines() if os.path.exists(gi) else []
    add = ['release_upload/'] + ['files/' + path for path, _, _, _ in big]
    with open(gi, 'a') as f:
        for line in add:
            if line not in cur: f.write(line + '\n')
    print(f'\nFile BESAR (> {a.big_mb:.0f} MB) -> Release, TIDAK masuk repo (sudah ditulis ke .gitignore):')
    for path, size, asset, _ in big:
        print(f'  files/{path}  ({size/1e6:.0f} MB)  -> asset "{asset}"')
if big:
    os.makedirs(a.stage_dir, exist_ok=True)
    for path, size, asset, src in big:
        dst = os.path.join(a.stage_dir, asset)
        if os.path.exists(dst): os.remove(dst)
        try: os.link(src, dst)          # hardlink: tidak memakai ruang disk tambahan
        except OSError:
            import shutil; shutil.copy2(src, dst)
    print(f'{len(big)} file untuk Release {a.release_tag} disiapkan di folder "{a.stage_dir}/" -> upload SEMUA isinya ke release itu.')
    print(f'  contoh: gh release upload {a.release_tag} {a.stage_dir}/* --clobber')