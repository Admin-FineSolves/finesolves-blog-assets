#!/usr/bin/env python3
"""Fine Solves blog creatives: hero (1200x630) + infographic (1080x1350).

Usage: python3 creatives.py spec.json OUTDIR
spec.json = {
  "eyebrow": "AI IN MANUFACTURING",          # mono label, <= 4 words
  "title": "Why predictive maintenance pays back in 6 months",  # <= 10 words
  "highlight": "6 months",                    # optional phrase in title to set on a teal bar
  "takeaways_title": "5 things to know",      # infographic headline, <= 6 words
  "takeaways": ["...", "..."],                 # 3-5 items, each <= 14 words
  "source_note": "Sources: McKinsey 2026; Gartner 2026"   # optional, mono footer
}
Fonts: needs npm packages @fontsource/space-grotesk @fontsource/inter @fontsource/dm-mono
in ./node_modules (run: npm i @fontsource/space-grotesk @fontsource/inter @fontsource/dm-mono).
Logo: if ./logo-colour.png exists it is used; else a Space Grotesk wordmark placeholder.
"""
import base64, html, json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FS = HERE / "node_modules" / "@fontsource"

def font(pkg, file):
    p = FS / pkg / "files" / file
    return "data:font/woff2;base64," + base64.b64encode(p.read_bytes()).decode()

def css():
    return f"""
@font-face{{font-family:SG;font-weight:600;src:url({font('space-grotesk','space-grotesk-latin-600-normal.woff2')})}}
@font-face{{font-family:IN;font-weight:400;src:url({font('inter','inter-latin-400-normal.woff2')})}}
@font-face{{font-family:IN;font-weight:500;src:url({font('inter','inter-latin-500-normal.woff2')})}}
@font-face{{font-family:DM;font-weight:500;src:url({font('dm-mono','dm-mono-latin-500-normal.woff2')})}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#fff;color:#092040;font-family:IN;overflow:hidden;position:relative}}
.mono{{font-family:DM;font-weight:500;text-transform:uppercase;letter-spacing:.08em}}
.eyebrow{{color:#08545C;font-size:18px}}
.h{{font-family:SG;font-weight:600;color:#092040}}
.hl{{background:#09A9A5;color:#080A08;padding:0 .12em;box-decoration-break:clone;-webkit-box-decoration-break:clone}}
.bands{{position:absolute;pointer-events:none}}
.bands i{{position:absolute;display:block;transform:rotate(-35deg);transform-origin:center}}
.rule{{height:1px;background:#E1E4E8}}
.logo{{display:flex;align-items:center;gap:12px}}
.wm{{font-family:SG;font-weight:600;font-size:26px;letter-spacing:-.03em}}
.wm b{{font-weight:600;color:#08545C}}
.site{{color:#56645F;font-size:14px}}
"""

def logo_html(height=40):
    p = HERE / "logo-colour.png"
    if p.exists():
        b = base64.b64encode(p.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{b}" style="height:{height}px">'
    return '<span class="wm">Fine <b>Solves</b></span>'

def title_html(title, highlight):
    t = html.escape(title)
    if highlight and highlight in title:
        h = html.escape(highlight)
        t = t.replace(h, f'<span class="hl">{h}</span>', 1)
    return t

def bands(right, top, scale=1.0):
    w = int(560 * scale)
    return f"""<div class="bands" style="right:{right}px;top:{top}px;width:{w}px;height:{w}px">
<i style="background:#092040;width:{int(900*scale)}px;height:{int(46*scale)}px;left:{int(40*scale)}px;top:{int(150*scale)}px"></i>
<i style="background:#09A9A5;width:{int(900*scale)}px;height:{int(46*scale)}px;left:{int(40*scale)}px;top:{int(250*scale)}px"></i>
<i style="background:#088888;width:{int(900*scale)}px;height:{int(18*scale)}px;left:{int(40*scale)}px;top:{int(330*scale)}px"></i>
</div>"""

def hero(spec):
    n = len(spec["title"])
    size = 76 if n <= 40 else 64 if n <= 58 else 54
    return f"""<html><head><style>{css()}</style></head><body style="width:1200px;height:630px">
{bands(-330, -120, 1.1)}
<div style="position:absolute;left:72px;top:64px;right:400px">
  <div class="mono eyebrow">{html.escape(spec['eyebrow'])}</div>
  <div class="h" style="margin-top:28px;font-size:{size}px;line-height:.98;letter-spacing:-.045em">{title_html(spec['title'], spec.get('highlight'))}</div>
</div>
<div style="position:absolute;left:72px;right:72px;bottom:56px">
  <div class="rule" style="margin-bottom:22px"></div>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div class="logo">{logo_html(36)}</div><div class="mono site">finesolves.com / blog</div>
  </div>
</div></body></html>"""

def infographic(spec):
    items = spec["takeaways"][:5]
    rows = "".join(
        f"""<div style="display:flex;gap:28px;padding:30px 0;border-top:1px solid #E1E4E8">
<div class="mono" style="color:#08545C;font-size:22px;padding-top:6px;min-width:44px">{i+1:02d}</div>
<div style="font-family:IN;font-weight:500;font-size:31px;line-height:1.32;color:#092040">{html.escape(t)}</div></div>"""
        for i, t in enumerate(items))
    note = html.escape(spec.get("source_note", ""))
    return f"""<html><head><style>{css()}</style></head><body style="width:1080px;height:1350px">
<div style="position:absolute;left:0;right:0;top:0;height:12px;background:#092040"></div>
<div style="position:absolute;left:0;width:360px;top:0;height:12px;background:#09A9A5"></div>
<div style="position:absolute;left:72px;right:72px;top:80px">
  <div class="mono eyebrow">{html.escape(spec['eyebrow'])}</div>
  <div class="h" style="margin-top:24px;font-size:72px;line-height:.98;letter-spacing:-.05em;max-width:760px">{html.escape(spec.get('takeaways_title','Key takeaways'))}</div>
  <div style="margin-top:56px">{rows}<div class="rule"></div></div>
</div>
<div style="position:absolute;left:72px;right:72px;bottom:64px">
  <div class="mono" style="color:#56645F;font-size:13px;margin-bottom:22px">{note}</div>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div class="logo">{logo_html(36)}</div><div class="mono site">finesolves.com</div>
  </div>
</div></body></html>"""

def render(page, doc, w, h, out):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(doc)
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(150)
    page.screenshot(path=str(out), type="png")

def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        render(pg, hero(spec), 1200, 630, out / "hero.png")
        render(pg, infographic(spec), 1080, 1350, out / "infographic.png")
        # overflow check: infographic content must end above footer
        b.close()
    print(out / "hero.png"); print(out / "infographic.png")

if __name__ == "__main__":
    main()
