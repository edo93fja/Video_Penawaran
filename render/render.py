"""Membuat satu video penawaran. Dipanggil oleh GitHub Actions (render.yml) dengan variabel lingkungan PAYLOAD (JSON):
{"vid": "16 hex", "nama": "...", "niche": "...", "kategori": "...", "urls": ["https://...github.io/...", ...]}
Hasil: video/<vid>.mp4
"""
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.parse
from pathlib import Path
import requests

HERE = Path(__file__).parent
OUT_DIR = Path(os.environ.get("OUT_DIR", HERE.parent / "video"))
ALLOWED_HOSTS = [h.strip().lower() for h in os.environ.get("ALLOWED_HOSTS", "github.io").split(",") if h.strip()]
ALLOW_HTTP = os.environ.get("ALLOW_HTTP", "0") == "1"      # hanya untuk uji lokal
WAIT_PAGE_SECONDS = int(os.environ.get("WAIT_PAGE_SECONDS", "240"))
FPS, DUR = 24, 31.0

PALET = {  # niche -> (aksen, latar, frasa pencarian)
    "katering_nasibox": ("ffb454", "6b2d12", "katering"),
    "konveksi_percetakan": ("8aa2ff", "2b3a7a", "jasa percetakan"),
    "jasa_rumah": ("7fd6ff", "14506b", "jasa perbaikan rumah"),
    "klinik_kecantikan": ("4fe3cf", "0e5c55", "klinik"),
    "kursus_bimbel": ("ffd23f", "6b5410", "tempat kursus"),
}
PALET_UMUM = ("ffb454", "6b2d12", "usaha seperti ini")


def bersih(t, n):
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f<>]", " ", str(t or ""))).strip()[:n]


def url_aman(u):
    p = urllib.parse.urlparse(str(u).strip())
    if p.scheme not in (("https", "http") if ALLOW_HTTP else ("https",)):
        raise ValueError("URL harus https: " + str(u)[:80])
    if p.username or p.password:
        raise ValueError("URL tidak valid")
    host = (p.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
        raise ValueError("host tidak diizinkan: " + host)
    return str(u).strip()


def tunggu_halaman(u):
    batas = time.time() + WAIT_PAGE_SECONDS
    while True:
        try:
            r = requests.get(u, timeout=15, allow_redirects=False)
            if r.status_code == 200 and len(r.content) > 500:
                return
        except requests.RequestException:
            pass
        if time.time() > batas:
            raise RuntimeError("halaman demo belum bisa dibuka: " + u)
        time.sleep(10)


def frasa(kategori, fr_niche):
    k = bersih(kategori, 40).lower()
    return k if 3 <= len(k) <= 32 and not re.search(r"\d", k) else fr_niche


def main():
    from playwright.sync_api import sync_playwright
    d = json.loads(os.environ["PAYLOAD"])
    vid = str(d.get("vid", ""))
    if not re.fullmatch(r"[a-f0-9]{16}", vid):
        raise ValueError("vid harus 16 karakter hex")
    urls = [url_aman(u) for u in (d.get("urls") or [])][:5]
    if not urls:
        raise ValueError("urls kosong")
    aksen, latar, fr_niche = PALET.get(str(d.get("niche", "")), PALET_UMUM)
    nama = bersih(d.get("nama"), 60)
    if not nama:
        raise ValueError("nama kosong")
    jenis = frasa(d.get("kategori"), fr_niche)
    tunggu_halaman(urls[0])
    work = Path(tempfile.mkdtemp(prefix="vid_"))
    try:
        shutil.copy(HERE / "template.html", work / "template.html")
        shutil.copytree(HERE / "fonts", work / "fonts")
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            pg = ctx.new_page()
            ok = {}
            for i, u in enumerate(urls, start=1):
                try:
                    try:
                        pg.goto(u, wait_until="networkidle", timeout=30000)
                    except Exception:
                        pass
                    pg.wait_for_timeout(1500)
                    h = pg.evaluate("Math.min(1900, document.documentElement.scrollHeight)")
                    pg.screenshot(path=str(work / f"p{i}.png"), full_page=True, clip={"x": 0, "y": 0, "width": 390, "height": max(844, h)})
                    ok[i] = True
                except Exception as e:
                    print("tangkapan desain", i, "gagal:", e)
                    ok[i] = False
            ctx.close()
            if not ok.get(1):
                raise RuntimeError("tangkapan layar desain 1 gagal")
            for i in range(1, 6):   # desain yang gagal/tidak ada memakai desain 1
                if not (work / f"p{i}.png").exists():
                    shutil.copy(work / "p1.png", work / f"p{i}.png")
            pg2 = b.new_page(viewport={"width": 1080, "height": 1920})
            q = urllib.parse.urlencode({"n": nama, "k": jenis, "a": aksen, "b": latar})
            pg2.goto(f"file://{work}/template.html?{q}")
            pg2.wait_for_timeout(800)
            pg2.evaluate("Promise.all([1,2,3,4,5].map(i=>new Promise(r=>{const m=new Image();m.onload=r;m.onerror=r;m.src='p'+i+'.png'})))")
            fr = work / "fr"
            fr.mkdir()
            for f in range(int(FPS * DUR)):
                pg2.evaluate(f"setT({f / FPS})")
                pg2.screenshot(path=str(fr / f"{f:04d}.jpg"), type="jpeg", quality=92)
            b.close()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"{vid}.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fr / "%04d.jpg"), "-i", str(HERE / "musik-ceria.wav"),
               "-t", str(DUR), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError("ffmpeg gagal: " + r.stderr[-300:])
        print("SELESAI", out, round(out.stat().st_size / 1e6, 2), "MB; desain ok:", [i for i, v in ok.items() if v])
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("GAGAL:", e)
        sys.exit(1)
