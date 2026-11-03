#!/usr/bin/env python3
"""Fine Solves reel renderer: script.json -> 1080x1920 30fps H.264 MP4 + cover.jpg.

Usage: python3 reels/render_reel.py REEL_DIR/script.json REEL_DIR [--fps 30] [--stills]

script.json
{
  "id": "2026-11-04",
  "brand": "finesolves" | "finehealth" | "finehr",
  "scenes": [
    {"type": "headline", "dur": 3.0,
     "eyebrow": "OPD · 10:42 AM",              # optional mono label
     "text": "The queue isn't\\nat the doctor.",  # \\n = line break; <= 8 words
     "highlight": "doctor",                      # optional phrase that gets a teal bar under it
     "sub": "Optional Inter supporting line"},
    {"type": "cards", "dur": 4.5, "title": "optional headline",
     "cards": [{"label": "REGISTER", "text": "Patient details on a paper slip"}, ...]},   # 2-4 cards
    {"type": "steps", "dur": 3.5, "title": "optional", "numbered": false,
     "items": ["Register.", "Treat.", "Bill."]},  # 2-4 items; teal dot travels (or 01/02/03 if numbered)
    {"type": "counter", "dur": 5.0,
     "rows": ["2 HRS / DAY", "× 6 PEOPLE", "= 12 HRS / DAY"],
     "result": "≈ 3,000 HRS / YEAR", "note": "ILLUSTRATIVE · 250 WORKING DAYS"},
    {"type": "end", "dur": 3.0, "line": "FineHealth by Fine Solves", "tag": "HOSPITAL MANAGEMENT SYSTEM"}
  ]
}
The last scene must be "end". Numbers in counter rows tick up from 0.
Logo: reels/assets/logo-colour.png and reels/assets/mark-colour.png are used if present;
otherwise a Space Grotesk wordmark placeholder ("Fine Solves").
"""
import argparse, base64, html, json, math, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FS = ROOT / "node_modules" / "@fontsource"
W, H = 1080, 1920


def font(pkg, file):
    p = FS / pkg / "files" / file
    return "data:font/woff2;base64," + base64.b64encode(p.read_bytes()).decode()


def b64img(p):
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def esc(s):
    return html.escape(s or "")


def text_html(text, highlight=None):
    lines = []
    for ln in (text or "").split("\n"):
        t = esc(ln)
        if highlight and esc(highlight) in t:
            h = esc(highlight)
            t = t.replace(h, f'<span class="hlw">{h}<i class="bar"></i></span>', 1)
        lines.append(f'<div class="ln a">{t}</div>')
    return "".join(lines)


def counter_row(row):
    # wrap each number in a span so JS can tick it up
    import re
    out, last = [], 0
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", row):
        out.append(esc(row[last:m.start()]))
        raw = m.group(0)
        out.append(f'<span class="num" data-v="{raw.replace(",", "")}" data-c="{1 if "," in raw else 0}">{raw}</span>')
        last = m.end()
    out.append(esc(row[last:]))
    return "".join(out)


def scene_html(s, idx):
    t = s["type"]
    if t == "headline":
        eb = f'<div class="mono eyebrow a">{esc(s["eyebrow"])}</div>' if s.get("eyebrow") else ""
        sub = f'<div class="sub a">{esc(s["sub"])}</div>' if s.get("sub") else ""
        return f'<div class="content">{eb}<div class="h">{text_html(s["text"], s.get("highlight"))}</div>{sub}</div>'
    if t == "cards":
        title = f'<div class="h hs">{text_html(s["title"])}</div>' if s.get("title") else ""
        cards = "".join(
            f'<div class="card a"><div class="mono clabel">{esc(c["label"])}</div><div class="ctext">{esc(c["text"])}</div></div>'
            for c in s["cards"])
        return f'<div class="content">{title}<div class="cards">{cards}</div></div>'
    if t == "steps":
        title = f'<div class="h hs">{text_html(s["title"])}</div>' if s.get("title") else ""
        items = []
        for i, it in enumerate(s["items"]):
            mark = f'<span class="mono stepno">{i+1:02d}</span>' if s.get("numbered") else ""
            items.append(f'<div class="step a">{mark}<span class="steptext">{esc(it)}</span></div>')
        dot = "" if s.get("numbered") else '<i class="dot"></i>'
        return f'<div class="content">{title}<div class="steps">{dot}{"".join(items)}</div></div>'
    if t == "counter":
        rows = "".join(f'<div class="mono crow a">{counter_row(r)}</div>' for r in s["rows"])
        note = f'<div class="mono note a">{esc(s["note"])}</div>' if s.get("note") else ""
        return (f'<div class="content">{rows}<div class="rule a"></div>'
                f'<div class="result a"><span class="hlblock">{counter_row(s["result"])}</span></div>{note}</div>')
    if t == "end":
        tag = f'<div class="mono endtag a">{esc(s["tag"])}</div>' if s.get("tag") else ""
        return (f'<div class="content endc"><div class="a">{LOGO_FULL}</div>'
                f'<div class="endline a">{esc(s["line"])}</div>{tag}'
                f'<div class="mono site a">finesolves.com</div></div>')
    raise SystemExit(f"unknown scene type: {t}")


def build_page(script):
    global LOGO_FULL
    logo = HERE / "assets" / "logo-colour.png"
    mark = HERE / "assets" / "mark-colour.png"
    LOGO_FULL = (f'<img src="{b64img(logo)}" style="max-width:430px;height:auto">' if logo.exists()
                 else '<span class="wm">Fine <b>Solves</b></span>')
    MARK = (f'<img src="{b64img(mark)}" style="height:64px">' if mark.exists()
            else '<span class="wm sm">Fine <b>Solves</b></span>')
    scenes, t0 = [], 0.0
    for i, s in enumerate(script["scenes"]):
        scenes.append(f'<section class="scene t-{s["type"]}" id="s{i}" data-start="{t0}" data-dur="{s["dur"]}">'
                      f'{scene_html(s, i)}</section>')
        t0 += float(s["dur"])
    css = f"""
@font-face{{font-family:SG;font-weight:600;src:url({font('space-grotesk','space-grotesk-latin-600-normal.woff2')})}}
@font-face{{font-family:SG;font-weight:700;src:url({font('space-grotesk','space-grotesk-latin-700-normal.woff2')})}}
@font-face{{font-family:SG;font-weight:600;src:url({font('space-grotesk','space-grotesk-latin-ext-600-normal.woff2')});unicode-range:U+0100-02AF,U+20A0-20CF}}
@font-face{{font-family:IN;font-weight:400;src:url({font('inter','inter-latin-400-normal.woff2')})}}
@font-face{{font-family:IN;font-weight:400;src:url({font('inter','inter-latin-ext-400-normal.woff2')});unicode-range:U+0100-02AF,U+20A0-20CF}}
@font-face{{font-family:DM;font-weight:500;src:url({font('dm-mono','dm-mono-latin-500-normal.woff2')})}}
@font-face{{font-family:DM;font-weight:500;src:url({font('dm-mono','dm-mono-latin-ext-500-normal.woff2')});unicode-range:U+0100-02AF,U+20A0-20CF}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;background:#fff;overflow:hidden}}
body{{color:#092040;font-family:IN,'DejaVu Sans',sans-serif;position:relative}}
.mono{{font-family:DM,'DejaVu Sans Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.08em}}
.scene{{position:absolute;inset:0;opacity:0}}
.content{{position:absolute;left:96px;right:96px;top:300px;bottom:520px;display:flex;flex-direction:column;justify-content:center;gap:36px}}
.eyebrow{{color:#56645F;font-size:30px}}
.h{{font-family:SG,'DejaVu Sans',sans-serif;font-weight:600;font-size:108px;line-height:.98;letter-spacing:-.055em;color:#092040}}
.hs{{font-size:80px}}
.ln{{display:block}}
.hlw{{position:relative;display:inline-block}}
.bar{{position:absolute;left:0;right:0;bottom:-10px;height:10px;background:#09A9A5;transform-origin:left;transform:scaleX(0)}}
.sub{{font-size:42px;line-height:1.35;color:#56645F;max-width:860px}}
.cards{{display:flex;flex-direction:column;gap:24px}}
.card{{border:1px solid #E1E4E8;border-radius:4px;padding:36px 40px;background:#fff}}
.clabel{{font-size:28px;color:#08545C;margin-bottom:14px}}
.ctext{{font-size:44px;line-height:1.25;color:#092040}}
.steps{{position:relative;display:flex;flex-direction:column;gap:28px;padding-left:64px}}
.step{{font-family:SG;font-weight:600;font-size:104px;line-height:1;letter-spacing:-.05em;display:flex;align-items:baseline;gap:28px}}
.stepno{{font-family:DM;font-size:40px;color:#08545C;letter-spacing:.04em;min-width:64px}}
.steps:has(.stepno){{padding-left:0}}
.steps:has(.stepno) .step{{font-size:76px}}
.dot{{position:absolute;left:0;top:0;width:28px;height:28px;border-radius:50%;background:#09A9A5}}
.crow{{font-size:54px;color:#092040;letter-spacing:.04em}}
.rule{{height:1px;background:#092040;transform-origin:left}}
.result{{font-family:SG;font-weight:600;font-size:92px;letter-spacing:-.04em;line-height:1.1}}
.hlblock{{background:#09A9A5;color:#080A08;padding:4px 18px}}
.note{{font-size:28px;color:#56645F}}
.endc{{justify-content:center;gap:40px}}
.endline{{font-family:SG;font-weight:600;font-size:64px;line-height:1.05;letter-spacing:-.04em;color:#092040}}
.endtag{{font-size:30px;color:#08545C}}
.site{{font-size:32px;color:#56645F}}
.wm{{font-family:SG;font-weight:700;font-size:84px;letter-spacing:-.04em;color:#092040}}
.wm b{{font-weight:700;color:#08545C}}
.wm.sm{{font-size:36px}}
#mark{{position:absolute;left:96px;top:1430px;opacity:0}}
"""
    js = """
const ease = p => 1 - Math.pow(1 - Math.min(Math.max(p, 0), 1), 4);
const fmt = (v, comma, target) => comma ? Math.round(v).toLocaleString('en-IN') : (Number.isInteger(target) ? String(Math.round(v)) : v.toFixed(1));
// auto-fit: shrink a headline until every authored line fits on one visual line
window.fit = () => document.querySelectorAll('.h').forEach(h => {
  let fs = parseFloat(getComputedStyle(h).fontSize);
  const lines = [...h.querySelectorAll('.ln')];
  const wraps = () => lines.some(l => l.getBoundingClientRect().height > fs * 1.3);
  while (wraps() && fs > 64) { fs -= 4; h.style.fontSize = fs + 'px'; }
  h.dataset.fit = fs;
});
const total = TOTAL;
window.seek = (t) => {
  let showMark = false;
  document.querySelectorAll('.scene').forEach(sc => {
    const st = +sc.dataset.start, du = +sc.dataset.dur, lt = t - st;
    const isEnd = sc.classList.contains('t-end');
    if (lt < 0 || lt >= du) { sc.style.opacity = 0; return; }
    const out = isEnd ? 1 : Math.min(1, (du - lt) / 0.2);
    sc.style.opacity = out;
    if (!isEnd) showMark = true;
    const els = sc.querySelectorAll('.a');
    els.forEach((el, i) => {
      const start = 0.15 + i * (sc.classList.contains('t-cards') || sc.classList.contains('t-steps') ? 0.32 : 0.09);
      const p = ease((lt - start) / 0.45);
      el.style.opacity = p;
      el.style.transform = `translateY(${24 * (1 - p)}px)`;
      el._start = start;
    });
    sc.querySelectorAll('.bar').forEach(b => { b.style.transform = `scaleX(${ease((lt - 0.7) / 0.45)})`; });
    sc.querySelectorAll('.rule').forEach(r => { const p = ease((lt - r._start) / 0.45); r.style.transform = `scaleX(${p})`; r.style.opacity = 1; });
    sc.querySelectorAll('.num').forEach(n => {
      const host = n.closest('.a'); const v = +n.dataset.v;
      const p = ease((lt - host._start) / 0.9);
      n.textContent = fmt(v * p, n.dataset.c === '1', v);
    });
    const dot = sc.querySelector('.dot');
    if (dot) {
      const steps = [...sc.querySelectorAll('.step')];
      let y = 0, op = 0;
      steps.forEach(s => { if (lt >= s._start) { y = s.offsetTop + s.offsetHeight / 2 - 14; op = 1; } });
      // smooth move between positions
      const k = steps.findIndex(s => lt < s._start); const cur = k === -1 ? steps.length - 1 : k - 1;
      if (cur > 0) { const prev = steps[cur - 1], now = steps[cur]; const p = ease((lt - now._start) / 0.4);
        const y0 = prev.offsetTop + prev.offsetHeight / 2 - 14, y1 = now.offsetTop + now.offsetHeight / 2 - 14; y = y0 + (y1 - y0) * p; }
      dot.style.transform = `translateY(${y}px)`; dot.style.opacity = op;
    }
  });
  const m = document.getElementById('mark');
  m.style.opacity = showMark ? Math.min(1, t / 0.4) : 0;
};
""".replace("TOTAL", str(t0))
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'{"".join(scenes)}<div id="mark">{MARK}</div><script>{js}</script></body></html>')
    return page, t0


def music(dur, out):
    """Quiet ambient bed: two soft chords crossfading every 8s, lowpassed, faded in/out."""
    a = "(sin(2*PI*220*t)+0.8*sin(2*PI*277.18*t)+0.7*sin(2*PI*329.63*t)+0.4*sin(2*PI*440*t))"
    b = "(sin(2*PI*196*t)+0.8*sin(2*PI*246.94*t)+0.7*sin(2*PI*293.66*t)+0.4*sin(2*PI*392*t))"
    w = "(0.5+0.5*cos(2*PI*t/16))"
    expr = f"0.035*({w}*{a}+(1-{w})*{b})*(0.85+0.15*sin(2*PI*0.25*t))"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"aevalsrc='{expr}|{expr}':s=48000:d={dur}",
                    "-af", f"lowpass=f=1800,afade=t=in:d=1.5,afade=t=out:st={max(dur-2,0)}:d=2",
                    "-c:a", "aac", "-b:a", "128k", str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("outdir")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--stills", action="store_true", help="only render review stills")
    a = ap.parse_args()
    script = json.loads(Path(a.script).read_text())
    assert script["scenes"][-1]["type"] == "end", "last scene must be type end"
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    page_html, total = build_page(script)
    (out / "reel.html").write_text(page_html)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.set_content(page_html); pg.evaluate("document.fonts.ready"); pg.evaluate("fit()")
        pg.wait_for_timeout(300)
        # review stills: the moment each scene has fully settled, plus the end card
        t0 = 0.0
        for i, s in enumerate(script["scenes"]):
            ts = t0 + max(float(s["dur"]) - 0.35, 0)
            pg.evaluate(f"seek({ts})")
            pg.screenshot(path=str(out / f"still-{i+1:02d}.png"))
            t0 += float(s["dur"])
        # cover = settled first scene
        pg.evaluate(f"seek({max(float(script['scenes'][0]['dur'])-0.35,0)})")
        pg.screenshot(path=str(out / "cover.jpg"), type="jpeg", quality=88)
        if a.stills:
            br.close(); return
        n = int(math.ceil(total * a.fps))
        silent = out / "_video.mp4"
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps),
                               "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                               "-pix_fmt", "yuv420p", "-r", str(a.fps), str(silent)], stdin=subprocess.PIPE)
        for f in range(n):
            pg.evaluate(f"seek({f / a.fps})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
        ff.stdin.close(); ff.wait(); br.close()
    aud = out / "_audio.m4a"; music(total, aud)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(aud), "-c:v", "copy",
                    "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
    silent.unlink(); aud.unlink()
    print(f"rendered {out/'reel.mp4'} ({total:.1f}s, {n} frames)")


if __name__ == "__main__":
    main()
