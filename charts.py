#!/usr/bin/env python3
"""Fine Solves blog charts -> 1200x750 PNG (convert to JPEG after).

Usage: python3 charts.py charts.json OUTDIR      -> OUTDIR/chart-1.png, chart-2.png, ...
charts.json = [ {
  "type": "bar" | "column" | "line",
  "title": "Share of AI budget lost to complexity",      # <= 8 words, states the finding
  "subtitle": "Mid-market firms, 2026",                  # what / who / when
  "unit": "%",                                            # appended to value labels ("" for none, "₹ cr", "x" ...)
  "series": ["India", "Global"],                          # 1 or 2 names (2 max). Omit for single series.
  "data": [["India", 27], ["Global average", 25]],        # bar/column single series: [label, value]
                                                           # 2 series: [label, v1, v2]; line: [x_label, v1(, v2)]
  "highlight": "India",                                   # bar/column single series: label drawn teal (optional)
  "source": "Source: Freshworks Global Cost of Complexity Report, 2026"
} ]
Rules (dataviz): one axis only; max 2 series (navy #092040 + teal #09A9A5); every bar/end point
direct-labelled with its value; the same numbers must also appear as an HTML table in the post.
Needs ./node_modules/@fontsource fonts (see creatives.py).
"""
import html, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from creatives import css, logo_html

NAVY, TEAL, INK, MUTED, LINE = "#092040", "#09A9A5", "#092040", "#56645F", "#E1E4E8"
W, H = 1200, 750
PL, PR, PT, PB = 72, 72, 190, 120          # plot margins
e = html.escape

def fmt(v, unit):
    s = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    return f"₹{s} cr" if unit == "₹ cr" else f"{s}{unit}"

def nice_max(m):
    import math
    if m <= 0: return 1
    p = 10 ** math.floor(math.log10(m)); n = m / p
    for k in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if n <= k: return k * p
    return 10 * p

def ticks(m):
    step = nice_max(m / 4)
    import math
    n = math.ceil(m / step)
    return step * n, [step * k for k in range(n + 1)]

def bar_svg(c):
    rows, unit = c["data"], c.get("unit", "")
    two = len(rows[0]) == 3
    lw = 330                                     # label column
    pw = W - PL - PR - lw - 90
    vmax = nice_max(max(max(r[1:]) for r in rows))
    ph = H - PT - PB
    band = ph / len(rows)
    bh = min(44, band * (0.36 if two else 0.6))
    out = []
    for i, r in enumerate(rows):
        y0 = PT + i * band + (band - (bh * (2 if two else 1) + (4 if two else 0))) / 2
        out.append(f'<text x="{PL+lw-16}" y="{y0 + (bh*(2 if two else 1))/2 + 6}" text-anchor="end" font-family="IN" font-weight="500" font-size="20" fill="{INK}">{e(str(r[0]))}</text>')
        vals = r[1:]
        for j, v in enumerate(vals):
            col = (NAVY if j == 0 else TEAL) if two else (TEAL if c.get("highlight") == r[0] else NAVY)
            w = max(4, pw * v / vmax); y = y0 + j * (bh + 4)
            out.append(f'<rect x="{PL+lw}" y="{y}" width="{w}" height="{bh}" rx="4" fill="{col}"/>')
            out.append(f'<text x="{PL+lw+w+12}" y="{y+bh/2+7}" font-family="DM" font-weight="500" font-size="19" fill="{INK}">{e(fmt(v, unit))}</text>')
    out.append(f'<line x1="{PL+lw}" y1="{PT-10}" x2="{PL+lw}" y2="{H-PB+10}" stroke="{LINE}" stroke-width="1"/>')
    return "".join(out)

def column_svg(c):
    rows, unit = c["data"], c.get("unit", "")
    two = len(rows[0]) == 3
    pw, ph = W - PL - PR, H - PT - PB - 40
    vmax, tk = ticks(max(max(r[1:]) for r in rows))
    band = pw / len(rows)
    bw = min(120, band * (0.32 if two else 0.55))
    base = PT + ph
    out = []
    for t in tk[1:]:                              # recessive gridlines
        gy = base - ph * t / vmax
        out.append(f'<line x1="{PL}" y1="{gy}" x2="{W-PR}" y2="{gy}" stroke="{LINE}" stroke-width="1"/>')
        out.append(f'<text x="{PL}" y="{gy-8}" font-family="DM" font-size="14" fill="{MUTED}">{e(fmt(t, unit))}</text>')
    for i, r in enumerate(rows):
        cx = PL + i * band + band / 2
        vals = r[1:]
        total = bw * len(vals) + 4 * (len(vals) - 1)
        for j, v in enumerate(vals):
            col = (NAVY if j == 0 else TEAL) if two else (TEAL if c.get("highlight") == r[0] else NAVY)
            h = max(4, ph * v / vmax); x = cx - total / 2 + j * (bw + 4)
            out.append(f'<path d="M{x},{base} V{base-h+4} Q{x},{base-h} {x+4},{base-h} H{x+bw-4} Q{x+bw},{base-h} {x+bw},{base-h+4} V{base} Z" fill="{col}"/>')
            out.append(f'<text x="{x+bw/2}" y="{base-h-12}" text-anchor="middle" font-family="DM" font-weight="500" font-size="19" fill="{INK}">{e(fmt(v, unit))}</text>')
        out.append(f'<text x="{cx}" y="{base+34}" text-anchor="middle" font-family="IN" font-weight="500" font-size="19" fill="{INK}">{e(str(r[0]))}</text>')
    out.append(f'<line x1="{PL}" y1="{base}" x2="{W-PR}" y2="{base}" stroke="{MUTED}" stroke-width="1"/>')
    return "".join(out)

def line_svg(c):
    rows, unit = c["data"], c.get("unit", "")
    ns = len(rows[0]) - 1
    pw, ph = W - PL - PR - 150, H - PT - PB - 40
    vals = [v for r in rows for v in r[1:]]
    vmax, tk = ticks(max(vals)); base = PT + ph
    X0 = PL + 110                                  # inset so points clear the axis labels
    pw -= 110
    step = pw / max(1, len(rows) - 1)
    out = []
    for t in tk:
        gy = base - ph * t / vmax
        out.append(f'<line x1="{PL}" y1="{gy}" x2="{X0+pw}" y2="{gy}" stroke="{LINE}" stroke-width="1"/>')
        out.append(f'<text x="{PL}" y="{gy-8}" font-family="DM" font-size="14" fill="{MUTED}">{e(fmt(t, unit))}</text>')
    for i, r in enumerate(rows):
        out.append(f'<text x="{X0+i*step}" y="{base+34}" text-anchor="middle" font-family="IN" font-weight="500" font-size="18" fill="{INK}">{e(str(r[0]))}</text>')
    names = c.get("series", [""] * ns)
    for j in range(ns):
        col = NAVY if j == 0 else TEAL
        pts = [(X0 + i * step, base - ph * r[j+1] / vmax) for i, r in enumerate(rows)]
        out.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in pts)}" fill="none" stroke="{col}" stroke-width="3" stroke-linejoin="round"/>')
        for x, y in pts:
            out.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{col}" stroke="#fff" stroke-width="2"/>')
        x, y = pts[-1]
        out.append(f'<text x="{x+16}" y="{y+6}" font-family="DM" font-weight="500" font-size="19" fill="{INK}">{e(fmt(rows[-1][j+1], unit))} {e(names[j])}</text>')
        x0, y0 = pts[0]
        out.append(f'<text x="{x0}" y="{y0-16}" text-anchor="middle" font-family="DM" font-weight="500" font-size="17" fill="{INK}">{e(fmt(rows[0][j+1], unit))}</text>')
    return "".join(out)

def legend(c):
    s = c.get("series")
    if not s or len(s) < 2: return ""
    items = "".join(f'<span style="display:inline-flex;align-items:center;gap:8px;margin-right:24px"><i style="width:14px;height:14px;border-radius:3px;background:{col};display:inline-block"></i>{e(n)}</span>'
                    for n, col in zip(s, (NAVY, TEAL)))
    return f'<div class="mono" style="position:absolute;right:72px;top:72px;font-size:15px;color:{INK}">{items}</div>'

def page(c):
    body = {"bar": bar_svg, "column": column_svg, "line": line_svg}[c["type"]](c)
    return f"""<html><head><style>{css()}</style></head><body style="width:{W}px;height:{H}px">
<div style="position:absolute;left:0;top:0;width:{W}px;height:8px;background:{NAVY}"></div>
<div style="position:absolute;left:0;top:0;width:280px;height:8px;background:{TEAL}"></div>
<div style="position:absolute;left:72px;top:56px;right:420px">
  <div class="h" style="font-size:40px;line-height:1.05;letter-spacing:-.035em">{e(c['title'])}</div>
  <div style="margin-top:10px;font-size:19px;color:{MUTED}">{e(c.get('subtitle',''))}</div>
</div>
{legend(c)}
<svg width="{W}" height="{H}" style="position:absolute;left:0;top:0">{body}</svg>
<div style="position:absolute;left:72px;right:72px;bottom:36px;display:flex;justify-content:space-between;align-items:center">
  <div class="mono" style="color:{MUTED};font-size:12px;max-width:820px">{e(c.get('source',''))}</div>
  <div class="logo" style="transform:scale(.8);transform-origin:right center">{logo_html(30)}</div>
</div></body></html>"""

def main():
    charts = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    assert 1 <= len(charts) <= 4, "1-4 charts per post"
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H})
        for i, c in enumerate(charts, 1):
            assert c["type"] in ("bar", "column", "line"), c["type"]
            assert len(c["data"][0]) - 1 <= 2, "max 2 series"
            pg.set_content(page(c)); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(150)
            pg.screenshot(path=str(out / f"chart-{i}.png")); print(out / f"chart-{i}.png")
        b.close()

if __name__ == "__main__":
    main()
