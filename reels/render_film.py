#!/usr/bin/env python3
"""Fine Solves "contrast film" renderer: film.json -> 1080x1920 MP4 (+ stills, cover).

Format (modelled on the restrained product-film reel style):
  Act 1, DARK (navy): the problem. A cursor clicks a pill; a clock or counter runs; a grid of squares fills
         like a spreading queue. Subtitle captions pose the bad choice ("…or patients who wait?").
  Pivot, LIGHT: one word ("Neither.") with a teal full stop.
  Beats, LIGHT: 3 short headlines, each acted out by the cursor on an abstract prop
         (merge cards into one record / bill builds day by day / click a button and a status flips /
          drag a cap / choose between two options).
  End: wordmark, line, tag, finesolves.com.

Usage: python3 reels/render_film.py DIR/film.json DIR [--fps 30] [--stills]

film.json
{
 "brand": "finehealth",
 "problem": {"pill": "OPEN BILLING COUNTER", "label": "WAITING SINCE",
             "clock": ["10:42", "13:58"],            # OR "count": {"from":0,"to":4500,"prefix":"₹","suffix":""} (illustrative only)
             "captions": ["Most hospitals pick:", "more staff at the counter,", "or patients who wait?"]},
 "pivot": "Neither.",
 "beats": [
   {"headline": "Register once.", "prop": "merge", "items": ["OPD SLIP","LAB REPORT","PRESCRIPTION"],
    "result": "ONE PATIENT RECORD", "caption": "One record from the first visit."},
   {"headline": "Bill as care happens.", "prop": "build", "days": ["DAY 1","DAY 2","DAY 3"],
    "rows": ["Room · Day 1", "Lab · CBC", "Room · Day 2", "Pharmacy"], "result": "BILL READY", "caption": "..."},
   {"headline": "Discharge on time.", "prop": "flip", "context": "BED 12 · IPD", "button": "Discharge",
    "states": ["BILL PENDING", "BILL READY"], "caption": "..."},
   {"headline": "...", "prop": "choose", "options": ["Cloud", "On-premise"], "pick": 0, "caption": "..."},
   {"headline": "...", "prop": "cap", "label": "CAP", "caption": "..."}
 ],
 "end": {"line": "FineHealth by Fine Solves", "tag": "HOSPITAL MANAGEMENT SYSTEM"}
}
"""
import argparse, base64, html, json, math, random, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render_reel import font, b64img, tone, env, lowpass, bandpass, SCALE, SR  # noqa: E402

W, H = 1080, 1920
NAVY, TEAL, TEALB, INK, MUTED, LINE, SOFT, RAISED = "#092040", "#09A9A5", "#2DE2C5", "#092040", "#56645F", "#E1E4E8", "#F5F7F2", "#EEF2EC"


def esc(s):
    return html.escape(s or "", quote=True)


class Film:
    def __init__(self):
        self.els, self.tracks, self.ev, self.stills = [], [], [], []

    def el(self, id, html_, x, y, cls="", style=""):
        self.els.append(f'<div id="{id}" class="o {cls}" style="left:{x}px;top:{y}px;{style}">{html_}</div>')
        return id

    def k(self, id, p, keys):
        """keys: list of (t, value, ease) ; ease in o (out-quart), io, i (in-cubic), l (linear), s (step)."""
        self.tracks.append({"id": id, "p": p, "k": [[round(t, 3), v, e] for t, v, e in keys]})

    def snd(self, kind, t, **kw):
        self.ev.append((kind, t, kw))

    # -- common motions
    def show(self, id, t_in, t_out=None, mode="blur", dy=28):
        if mode == "blur":
            self.k(id, "o", [(t_in, 0, "o"), (t_in + 0.45, 1, "o")] + ([(t_out, 1, "o"), (t_out + 0.3, 0, "o")] if t_out else []))
            self.k(id, "b", [(t_in, 14, "o"), (t_in + 0.5, 0, "o")] + ([(t_out, 0, "o"), (t_out + 0.3, 12, "o")] if t_out else []))
            self.k(id, "y", [(t_in, dy * 0.6, "o"), (t_in + 0.55, 0, "o")])
        elif mode == "rise":
            self.k(id, "o", [(t_in, 0, "o"), (t_in + 0.4, 1, "o")] + ([(t_out, 1, "o"), (t_out + 0.25, 0, "o")] if t_out else []))
            self.k(id, "y", [(t_in, dy, "o"), (t_in + 0.5, 0, "o")])
        elif mode == "pop":
            self.k(id, "o", [(t_in, 0, "o"), (t_in + 0.3, 1, "o")] + ([(t_out, 1, "o"), (t_out + 0.25, 0, "o")] if t_out else []))
            self.k(id, "s", [(t_in, 0.9, "o"), (t_in + 0.45, 1, "o")])
        elif mode == "cut":
            self.k(id, "o", [(t_in, 1, "s")] + ([(t_out, 0, "s")] if t_out else []))
            self.k(id, "o0", [(0, 0, "s")])

    def cut(self, id, t):
        """hard cut to invisible at t (appends to the element's opacity track)."""
        for tr in self.tracks:
            if tr["id"] == id and tr["p"] == "o":
                tr["k"].append([round(t, 3), 0, "s"]); return

    def caption(self, text, t_in, t_out, cid):
        self.el(cid, f'<span class="cap">{esc(text)}</span>', 0, 1418, "capw")
        self.k(cid, "o", [(t_in, 0, "o"), (t_in + 0.2, 1, "o"), (t_out - 0.15, 1, "o"), (t_out, 0, "o")])


def headline_html(text, dot=True):
    t = esc(text)
    if dot and t.endswith("."):
        t = t[:-1] + '<span class="dot">.</span>'
    return t


def build(spec):
    f = Film()
    rnd = random.Random(42)
    P = spec["problem"]
    t = 0.0
    # ---------------- ACT 1: dark problem
    A_END = 6.8
    f.el("bgdark", "", 0, 0, "bg dark")
    f.k("bgdark", "o", [(0, 1, "s"), (A_END, 0, "s")])
    pill = f.el("pill", esc(P["pill"]), 96, 360, "pill mono")
    f.show(pill, 0.15, None, "rise"); f.cut(pill, A_END)
    f.k(pill, "on", [(0, 0, "s"), (1.0, 1, "s")])
    lab = f.el("plab", f'<i class="ldot"></i>{esc(P.get("label", ""))}', 96, 560, "plab mono")
    f.show(lab, 1.15, None, "rise"); f.cut(lab, A_END)
    big = f.el("pbig", "", 88, 600, "pbig")
    f.show(big, 1.2, None, "rise"); f.cut(big, A_END)
    if "clock" in P:
        a, b = [int(x.split(":")[0]) * 60 + int(x.split(":")[1]) for x in P["clock"]]
        f.k(big, "clock", [(1.2, a, "s"), (1.3, a, "i"), (6.3, b, "i")])
    else:
        c = P["count"]
        f.k(big, "num", [(1.2, c.get("from", 0), "s"), (1.3, c.get("from", 0), "i"), (6.3, c["to"], "i")])
        f.els[-1] = f.els[-1].replace('class="o pbig"', f'class="o pbig" data-pre="{esc(c.get("prefix", ""))}" data-suf="{esc(c.get("suffix", ""))}"')
    # grid of squares filling like a spreading queue
    cols, rows, sz, gap = 16, 8, 46, 10
    gx, gy = 96, 900
    cells = []
    for c in range(cols):
        for r in range(rows):
            cid = f"g{c}_{r}"
            cells.append(f'<i id="{cid}" class="cell" style="left:{c * (sz + gap)}px;top:{r * (sz + gap)}px"></i>')
            fill = 1.5 + 4.8 * ((c + rnd.uniform(0, 2.2)) / (cols + 1.5)) ** 0.75
            f.tracks.append({"id": cid, "p": "on", "k": [[0, 0, "s"], [round(fill, 3), 1, "s"]]})
    f.el("grid", "".join(cells), gx, gy, "grid")
    f.show("grid", 1.1, None, "rise"); f.cut("grid", A_END)
    caps = P.get("captions", [])
    ct = [2.0, 3.6, 5.1, 6.7]
    for i, c in enumerate(caps[:3]):
        f.caption(c, ct[i], ct[i + 1] - 0.05 if i < 2 else A_END - 0.02, f"pc{i}")
    # cursor path act 1
    cur = [(0.0, 1020, 1700), (0.75, 330, 400), (1.6, 520, 1250), (3.5, 760, 1180), (6.6, 900, 1500)]
    clicks = [0.95]
    for k in range(int((6.5 - 1.3) / 0.5)):
        f.snd("tick", 1.3 + 0.5 * k, gain=0.6 + 0.08 * k)
    # ---------------- PIVOT
    pv = f.el("pivot", headline_html(spec.get("pivot", "Neither.")), 0, 860, "h center big")
    f.show(pv, A_END + 0.05, A_END + 1.75, "blur")
    f.caption(spec.get("pivot", "Neither."), A_END + 0.25, A_END + 1.8, "pvc")
    f.snd("impact", A_END)
    t = A_END + 2.05
    # ---------------- BEATS
    BEAT = 4.3
    for i, bt in enumerate(spec["beats"]):
        bs = t
        hid = f.el(f"h{i}", headline_html(bt["headline"]), 0, 520, "h center")
        f.show(hid, bs + 0.05, bs + BEAT - 0.35, "blur")
        if bt.get("caption"):
            f.caption(bt["caption"], bs + 0.45, bs + BEAT - 0.3, f"bc{i}")
        prop = bt["prop"]
        out = bs + BEAT - 0.35
        if prop == "merge":
            items = bt["items"][:3]
            bx, by, bw, bh = 190, 940, 700, 250
            box = f.el(f"box{i}", f'<span class="mono boxl">{esc(bt.get("result", ""))}</span><i class="boxbar"></i>', bx, by, "mbox", f"width:{bw}px;height:{bh}px")
            f.show(box, bs + 0.3, out, "rise")
            f.k(box, "on", [(0, 0, "s"), (bs + 3.05, 1, "s")])
            starts = [(110, 800, -7), (540, 1225, 6), (130, 1250, -4)]
            for k, it in enumerate(items):
                cid = f.el(f"m{i}_{k}", f'<span class="mono">{esc(it)}</span>', 0, 0, "mcard")
                sx, sy, sr = starts[k]
                tx, ty = bx + 140 + k * 10, by + 90 + k * 10
                g0 = bs + 0.6 + 0.8 * k; g1 = g0 + 0.55
                f.k(cid, "x", [(0, sx, "s"), (g0, sx, "io"), (g1, tx, "io")])
                f.k(cid, "y", [(0, sy, "s"), (g0, sy, "io"), (g1, ty, "io")])
                f.k(cid, "r", [(0, sr, "s"), (g0, sr, "io"), (g1, 0, "io")])
                f.k(cid, "o", [(bs + 0.25 + 0.1 * k, 0, "o"), (bs + 0.6 + 0.1 * k, 1, "o"), (out, 1, "o"), (out + 0.25, 0, "o")])
                cur += [(g0 - 0.28, sx + 200, sy + 50), (g0, sx + 200, sy + 50), (g1, tx + 200, ty + 50)]
                f.grab = getattr(f, "grab", []) + [(g0, g1)]
                f.snd("pick", g0); f.snd("drop", g1)
            f.snd("chime", bs + 3.05)
        elif prop == "build":
            days = bt.get("days", ["DAY 1", "DAY 2", "DAY 3"])
            tl = f.el(f"tl{i}", "".join(f'<span class="mono tday" style="left:{int(k * 780 / (len(days) - 1))}px">{esc(d)}</span>' for k, d in enumerate(days)) + '<i class="tline"></i>', 150, 790, "tl")
            f.show(tl, bs + 0.3, out, "rise")
            dot = f.el(f"td{i}", "", 150 - 12, 830, "tdot")
            f.show(dot, bs + 0.4, out, "pop")
            f.k(dot, "x", [(bs + 0.5, 0, "s"), (bs + 3.0, 780, "io")])
            rows = bt["rows"][:4]
            card = f.el(f"bill{i}", f'<div class="bhead"><span class="mono">BILL · IPD</span><span class="mono chip" id="bchip{i}">{esc("IN PROGRESS")}</span></div>'
                        + "".join(f'<div class="brow" id="br{i}_{k}"><span>{esc(r)}</span><span class="mono badd">ADDED</span></div>' for k, r in enumerate(rows)), 140, 900, "bill")
            f.show(card, bs + 0.35, out, "rise")
            for k in range(len(rows)):
                rt = bs + 0.7 + 0.6 * k
                f.k(f"br{i}_{k}", "o", [(rt, 0, "o"), (rt + 0.35, 1, "o")]); f.k(f"br{i}_{k}", "y", [(rt, 20, "o"), (rt + 0.4, 0, "o")])
                f.snd("tick", rt, gain=1.0); f.snd("type", rt + 0.15, n=5)
            f.k(f"bchip{i}", "on", [(0, 0, "s"), (bs + 3.15, 1, "s")])
            f.k(f"bchip{i}", "txt", [(0, "IN PROGRESS", "s"), (bs + 3.15, bt.get("result", "READY"), "s")])
            f.snd("chime", bs + 3.15)
            cur += [(bs + 0.5, 860, 1500), (bs + 3.0, 820, 1000), (bs + 3.4, 860, 960)]
        elif prop == "flip":
            states = bt.get("states", ["PENDING", "READY"])
            card = f.el(f"fc{i}", f'<div class="fhead"><span class="mono">{esc(bt.get("context", ""))}</span><span class="mono chip" id="fchip{i}">{esc(states[0])}</span></div>'
                        f'<div class="btn" id="fbtn{i}">{esc(bt.get("button", "Confirm"))}</div>', 140, 860, "fcard")
            f.show(card, bs + 0.3, out, "rise")
            ck = bs + 1.45
            f.k(f"fbtn{i}", "s", [(ck - 0.05, 1, "o"), (ck + 0.05, 0.94, "o"), (ck + 0.35, 1, "o")])
            f.k(f"fchip{i}", "on", [(0, 0, "s"), (ck + 0.3, 1, "s")])
            f.k(f"fchip{i}", "txt", [(0, states[0], "s"), (ck + 0.3, states[-1], "s")])
            cur += [(bs + 0.5, 900, 1480), (ck - 0.1, 560, 1130), (ck + 1.6, 640, 1240)]
            clicks.append(ck); f.snd("click", ck); f.snd("chime", ck + 0.3)
        elif prop == "choose":
            opts = bt.get("options", ["A", "B"])[:2]; pick = bt.get("pick", 0)
            for k, o in enumerate(opts):
                oid = f.el(f"op{i}_{k}", esc(o), 120 + k * 430, 900, "opt")
                f.show(oid, bs + 0.35 + 0.15 * k, out, "rise")
            ck = bs + 1.6
            f.k(f"op{i}_{pick}", "on", [(0, 0, "s"), (ck, 1, "s")])
            f.k(f"op{i}_{pick}", "s", [(ck - 0.05, 1, "o"), (ck + 0.05, 0.95, "o"), (ck + 0.35, 1, "o")])
            px = 120 + pick * 430 + 200
            cur += [(bs + 0.5, 880, 1450), (ck - 0.1, px, 965), (ck + 1.5, px + 120, 1150)]
            clicks.append(ck); f.snd("click", ck); f.snd("pluck", ck + 0.15, note=5)
        elif prop == "cap":
            nb = 28
            bars = "".join(f'<i class="bar" id="bb{i}_{k}" style="left:{k * 31}px"></i>' for k in range(nb))
            f.el(f"bars{i}", bars + f'<i class="capl" id="capl{i}"><span class="mono">{esc(bt.get("label", "CAP"))}</span></i>', 110, 900, "bars")
            f.show(f"bars{i}", bs + 0.3, out, "rise")
            capy0, capy1 = 40, 200
            for k in range(nb):
                hgt = 60 + 360 * (k / nb) ** 1.6
                f.k(f"bb{i}_{k}", "h", [(bs + 0.4 + 0.04 * k, 0, "o"), (bs + 0.9 + 0.04 * k, hgt, "o"), (bs + 1.8, hgt, "io"), (bs + 2.6, min(hgt, 460 - capy1 - 20), "io")])
            f.k(f"capl{i}", "y", [(0, capy0, "s"), (bs + 1.8, capy0, "io"), (bs + 2.6, capy1, "io")])
            cur += [(bs + 0.6, 880, 1450), (bs + 1.75, 700, 900 + capy0), (bs + 2.6, 700, 900 + capy1), (bs + 3.6, 760, 1300)]
            f.grab = getattr(f, "grab", []) + [(bs + 1.8, bs + 2.6)]
            f.snd("pick", bs + 1.8); f.snd("drop", bs + 2.6)
        f.snd("whoosh", bs - 0.25, dur=0.5)
        t += BEAT
    # ---------------- END
    E = spec.get("end", {})
    es = t
    logo = HERE / "assets" / "logo-colour.png"
    logo_html = f'<img src="{b64img(logo)}" style="max-width:430px">' if logo.exists() else '<span class="wm">Fine <b>Solves</b></span>'
    f.el("endlogo", logo_html, 0, 760, "center")
    f.show("endlogo", es + 0.1, None, "blur")
    f.el("endline", headline_html(E.get("line", ""), dot=False), 0, 900, "endline center")
    f.show("endline", es + 0.35, None, "blur")
    if E.get("tag"):
        f.el("endtag", esc(E["tag"]), 0, 1010, "mono endtag center"); f.show("endtag", es + 0.6, None, "rise")
    f.el("endsite", "finesolves.com", 0, 1080, "mono endsite center"); f.show("endsite", es + 0.8, None, "rise")
    f.snd("pluck", es + 0.1, note=0); f.snd("pluck", es + 0.35, note=4); f.snd("pluck", es + 0.6, note=7)
    total = es + 3.0
    # ---------------- cursor
    cur.sort()
    f.el("cursor", '<svg class="arrow" viewBox="0 0 24 24"><path d="M5 3l14 8.5-6.2 1.4 3.6 6.6-2.6 1.4-3.6-6.6L5 18.6z"/></svg>'
         '<svg class="hand" viewBox="0 0 24 24"><path d="M8 11V6.5a1.5 1.5 0 013 0V11m0-1.5V5a1.5 1.5 0 013 0v4.5m0 0V6.5a1.5 1.5 0 013 0V13c0 4-2.5 7-6.5 7S6 17.5 5 15l-1.3-3a1.4 1.4 0 012.4-1.3L8 13"/></svg>'
         '<i class="ripple"></i>', 0, 0, "cursor")
    f.k("cursor", "x", [(tt, x, "io") for tt, x, y in cur])
    f.k("cursor", "y", [(tt, y, "io") for tt, x, y in cur])
    f.k("cursor", "o", [(0, 1, "s"), (es, 1, "o"), (es + 0.3, 0, "o")])
    grab = [(0, 0, "s")]
    for g0, g1 in getattr(f, "grab", []):
        grab += [(g0, 1, "s"), (g1, 0, "s")]
    f.k("cursor", "on", grab)
    rip = [(0, 0, "s")]
    sc = [(0, 1, "s")]
    for ck in clicks:
        rip += [(ck, 0, "s"), (ck + 0.01, 1, "s"), (ck + 0.5, 0, "s")]
        sc += [(ck - 0.08, 1, "o"), (ck, 0.84, "o"), (ck + 0.2, 1, "o")]
        f.snd("click", ck)
    f.k("cursor", "rip", [(tt, v, "s") for tt, v, _ in rip])
    f.k("cursor", "s", sc)
    return f, total, A_END


CSS = """
@font-face{font-family:SG;font-weight:600;src:url(SG600)}
@font-face{font-family:SG;font-weight:700;src:url(SG700)}
@font-face{font-family:IN;font-weight:400;src:url(IN400)}
@font-face{font-family:IN;font-weight:500;src:url(IN500)}
@font-face{font-family:DM;font-weight:500;src:url(DM500)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:#F5F7F2}
body{font-family:IN,sans-serif;color:#092040;position:relative}
.o{position:absolute;will-change:transform,opacity,filter}
.mono{font-family:DM,monospace;font-weight:500;text-transform:uppercase;letter-spacing:.08em}
.center{width:1080px;left:0!important;text-align:center}
.bg{width:1080px;height:1920px}
.bg.dark{background:#092040}
/* act 1 */
.pill{font-size:28px;color:#F3F6ED;border:1.5px solid rgba(243,246,237,.45);border-radius:999px;padding:16px 30px;transition:none}
.pill.on{background:#09A9A5;border-color:#09A9A5;color:#080A08}
.plab{font-size:28px;color:#94A49E;display:flex;align-items:center;gap:14px}
.ldot{width:14px;height:14px;border-radius:50%;background:#2DE2C5;display:inline-block}
.pbig{font-family:SG;font-weight:600;font-size:250px;letter-spacing:-.05em;line-height:1;color:#2DE2C5;white-space:nowrap}
.grid{width:886px;height:448px}
.cell{position:absolute;width:46px;height:46px;border-radius:6px;background:rgba(243,246,237,.08)}
.cell.on{background:#09A9A5}
/* captions */
.capw{width:1080px;text-align:center}
.cap{display:inline-block;font-family:IN;font-weight:500;font-size:36px;background:#EEF2EC;color:#092040;padding:8px 18px;border-radius:4px}
/* headlines */
.h{font-family:SG;font-weight:600;font-size:116px;line-height:1.0;letter-spacing:-.055em;color:#092040;padding:0 70px}
.h.big{font-size:190px}
.dot{color:#09A9A5}
/* merge */
.mbox{border:2px dashed #C9CFD6;border-radius:6px;background:rgba(255,255,255,.6)}
.mbox.on{border:2px solid #092040;background:#fff}
.boxl{position:absolute;left:34px;top:24px;font-size:26px;color:#08545C;opacity:0}
.mbox.on .boxl{opacity:1}
.boxbar{position:absolute;left:0;top:0;bottom:0;width:8px;background:#09A9A5;transform-origin:top;transform:scaleY(0)}
.mbox.on .boxbar{transform:scaleY(1)}
.mcard{width:420px;height:110px;background:#fff;border:1.5px solid #092040;border-radius:6px;display:flex;align-items:center;padding:0 30px;font-size:30px;box-shadow:none}
/* build */
.tl{width:780px;height:80px}
.tline{position:absolute;left:0;right:0;top:52px;height:2px;background:#D5DAE0}
.tday{position:absolute;top:0;transform:translateX(-50%);font-size:26px;color:#56645F;white-space:nowrap}
.tdot{width:24px;height:24px;border-radius:50%;background:#09A9A5}
.bill{width:800px;background:#fff;border:1.5px solid #E1E4E8;border-radius:6px;overflow:hidden}
.bhead,.fhead{display:flex;justify-content:space-between;align-items:center;padding:26px 34px;background:#EEF2EC;border-bottom:1px solid #E1E4E8;font-size:24px;color:#56645F}
.chip{font-size:22px;border:1.5px solid #092040;color:#092040;border-radius:999px;padding:8px 18px}
.chip.on{background:#09A9A5;border-color:#09A9A5;color:#080A08}
.brow{position:relative;display:flex;justify-content:space-between;align-items:baseline;padding:24px 34px;border-bottom:1px solid #E1E4E8;font-size:40px;opacity:0}
.brow:last-child{border-bottom:0}
.badd{font-size:24px;color:#08545C}
/* flip */
.fcard{width:800px;background:#fff;border:1.5px solid #E1E4E8;border-radius:6px;overflow:hidden;padding-bottom:50px}
.btn{position:relative;margin:56px auto 0;width:480px;height:120px;border-radius:999px;background:#092040;color:#fff;font-family:SG;font-weight:600;font-size:52px;letter-spacing:-.03em;display:flex;align-items:center;justify-content:center}
/* choose */
.opt{width:410px;height:130px;border-radius:999px;border:2px solid #092040;color:#092040;font-family:SG;font-weight:600;font-size:46px;display:flex;align-items:center;justify-content:center;background:#fff}
.opt.on{background:#09A9A5;border-color:#09A9A5;color:#080A08}
/* cap */
.bars{width:870px;height:460px}
.bar{position:absolute;bottom:0;width:22px;height:0;background:#092040;border-radius:3px 3px 0 0}
.capl{position:absolute;left:-20px;right:-20px;top:40px;height:3px;background:#09A9A5}
.capl span{position:absolute;right:0;top:-34px;font-size:22px;color:#08545C}
/* end */
.wm{font-family:SG;font-weight:700;font-size:96px;letter-spacing:-.045em;color:#092040}
.wm b{font-weight:700;color:#08545C}
.endline{font-family:SG;font-weight:600;font-size:64px;letter-spacing:-.04em}
.endtag{font-size:28px;color:#08545C}
.endsite{font-size:30px;color:#56645F}
/* cursor */
.cursor{left:0;top:0;width:64px;height:64px;z-index:50}
.cursor svg{position:absolute;left:-4px;top:-4px;width:64px;height:64px}
.cursor .arrow path{fill:#fff;stroke:#080A08;stroke-width:1.4;stroke-linejoin:round}
.cursor .hand{display:none}
.cursor .hand path{fill:#fff;stroke:#080A08;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}
.cursor.on .arrow{display:none}.cursor.on .hand{display:block;left:-22px;top:-10px}
.ripple{position:absolute;left:-30px;top:-30px;width:60px;height:60px;border-radius:50%;border:3px solid #09A9A5;opacity:0}
#grain{position:absolute;inset:0;pointer-events:none}
"""

JS = r"""
const TR = __TRACKS__, TOTAL = __TOTAL__;
const E = { o: p => 1 - Math.pow(1 - p, 4), io: p => p < .5 ? 8*p*p*p*p : 1 - Math.pow(-2*p + 2, 4) / 2, i: p => p*p*p, l: p => p };
function val(k, t) {
  if (t <= k[0][0]) return k[0][1];
  for (let j = 1; j < k.length; j++) {
    if (t < k[j][0]) { const [t0, v0] = k[j-1], [t1, v1, e] = k[j];
      if (e === 's' || typeof v1 !== 'number') return v0;
      const p = (t - t0) / Math.max(t1 - t0, 1e-6); return v0 + (v1 - v0) * E[e](p); }
  }
  return k[k.length - 1][1];
}
window.fit = () => document.querySelectorAll('.h:not(.big)').forEach(h => {
  let fs = 116; h.style.fontSize = fs + 'px';
  while (h.scrollHeight > fs * 1.25 && fs > 84) { fs -= 4; h.style.fontSize = fs + 'px'; } });
const byId = {}; TR.forEach(tr => { (byId[tr.id] = byId[tr.id] || []).push(tr); });
const ELS = Object.keys(byId).map(id => ({ el: document.getElementById(id), tr: byId[id] })).filter(x => x.el);
window.seek = (t) => {
  for (const { el, tr } of ELS) {
    const v = { x: 0, y: 0, s: 1, r: 0, o: 1, b: 0 }; let has = {};
    for (const T of tr) { v[T.p] = val(T.k, t); has[T.p] = 1; }
    if (has.o0) v.o = 0;
    if (has.x || has.y || has.s || has.r) el.style.transform = `translate(${v.x}px,${v.y}px) rotate(${v.r}deg) scale(${v.s})`;
    if (has.o) el.style.opacity = v.o;
    if (has.b) el.style.filter = v.b > 0.05 ? `blur(${v.b}px)` : 'none';
    if (has.on) el.classList.toggle('on', v.on > 0.5);
    if (has.h) el.style.height = v.h + 'px';
    if (has.txt) el.textContent = v.txt;
    if (has.clock) { let m = Math.round(v.clock); let hh = Math.floor(m / 60), mm = m % 60; const h12 = ((hh + 11) % 12) + 1;
      el.innerHTML = `${h12}:${String(mm).padStart(2, '0')}<span style="font-size:.32em;letter-spacing:0;margin-left:.15em">${hh >= 12 ? 'PM' : 'AM'}</span>`; }
    if (has.num) el.textContent = (el.dataset.pre || '') + Math.round(v.num).toLocaleString('en-IN') + (el.dataset.suf || '');
    if (has.rip) { const rp = el.querySelector('.ripple'); /* ripple driven by time since last click */ }
  }
  // ripple: find the latest click from the cursor's rip track
  const c = byId['cursor'] && byId['cursor'].find(x => x.p === 'rip');
  if (c) { let last = -9; for (const [tt, vv] of c.k) if (vv === 1 && tt <= t) last = tt;
    const d = t - last, rp = document.querySelector('#cursor .ripple');
    if (d >= 0 && d < 0.5) { const p = d / 0.5; rp.style.opacity = 1 - p; rp.style.transform = `scale(${0.4 + 1.4 * E.o(p)})`; } else rp.style.opacity = 0; }
};
"""


def soundtrack(total, events, dark_end, out):
    n = int((total + 0.5) * SR); mix = np.zeros(n); rng = np.random.default_rng(3); t = np.arange(n) / SR

    def add(sig, at, gain):
        i = int(max(at, 0) * SR); j = min(n, i + len(sig))
        if j > i: mix[i:j] += gain * sig[:j - i]
    # dark act: low tense drone (minor, slowly swelling); light act: warm major pad
    drone = (np.sin(2 * np.pi * 110 * t) + 0.6 * np.sin(2 * np.pi * 130.81 * t) + 0.4 * np.sin(2 * np.pi * 164.81 * t + 1))
    swell = np.clip(t / dark_end, 0, 1) ** 1.5
    dmask = (t < dark_end).astype(float)
    mix += 0.03 * lowpass(drone, 700) * (0.4 + 0.6 * swell) * dmask
    w = 0.5 + 0.5 * np.cos(2 * np.pi * (t - dark_end) / 12)
    pad = sum(w * np.sin(2 * np.pi * a * t + k) + (1 - w) * np.sin(2 * np.pi * b * t + k)
              for k, (a, b) in enumerate(zip([220, 277.18, 329.63, 415.30], [246.94, 293.66, 369.99, 440])))
    lmask = np.clip((t - dark_end) / 0.6, 0, 1)
    mix += 0.02 * lowpass(pad, 1500) * lmask
    beat = 0.6
    for k in range(int((total - dark_end) / beat) + 1):      # pulse only in the light act
        bt = dark_end + 0.6 + k * beat
        if k % 2 == 0:
            kn = int(0.28 * SR); kt = np.arange(kn) / SR
            add(np.sin(2 * np.pi * (48 + 60 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 14), bt, 0.14)
        add(bandpass(rng.standard_normal(int(0.05 * SR)), 5000, 11000) * env(int(0.05 * SR), 0.002, 0.012), bt + beat / 2, 0.04)
    for kind, at, kw in events:
        if kind == "tick":       # clock tick, grows with tension
            add(bandpass(rng.standard_normal(int(0.03 * SR)), 2000, 6000) * env(int(0.03 * SR), 0.001, 0.006), at, 0.07 * kw.get("gain", 1))
        elif kind == "click":
            add(tone(2400, 0.05, 0.0005, 0.008, (1,)), at, 0.12); add(tone(900, 0.08, 0.001, 0.02, (1,)), at, 0.08)
        elif kind == "impact":
            kn = int(0.9 * SR); kt = np.arange(kn) / SR
            add(np.sin(2 * np.pi * (38 + 70 * np.exp(-kt * 18)) * kt) * np.exp(-kt * 4), at, 0.3)
            add(tone(SCALE[5] * 2, 1.6, 0.003, 0.7), at + 0.05, 0.05); add(tone(SCALE[7] * 2, 1.6, 0.003, 0.7), at + 0.05, 0.04)
        elif kind == "pick":
            add(tone(1300, 0.08, 0.001, 0.02, (1,)), at, 0.06)
        elif kind == "drop":
            add(lowpass(tone(SCALE[rng.integers(3, 7)] * 2, 0.7, 0.002, 0.22), 3500), at, 0.08)
            kn = int(0.15 * SR); kt = np.arange(kn) / SR; add(np.sin(2 * np.pi * 120 * kt) * np.exp(-kt * 30), at, 0.12)
        elif kind == "pluck":
            add(lowpass(tone(SCALE[kw.get("note", 4) % len(SCALE)] * 2, 0.9, 0.003, 0.28), 4000), at, 0.075)
        elif kind == "chime":
            add(tone(SCALE[8] * 2, 1.2, 0.002, 0.45), at, 0.06); add(tone(SCALE[5] * 2, 1.2, 0.002, 0.5), at + 0.09, 0.05)
        elif kind == "type":
            for c in range(kw.get("n", 5)):
                add(bandpass(rng.standard_normal(int(0.012 * SR)), 2500, 7000) * env(int(0.012 * SR), 0.001, 0.004), at + 0.03 * c, 0.03)
        elif kind == "whoosh":
            d = kw.get("dur", 0.5); wn = int(d * SR); wt = np.arange(wn) / SR
            add(bandpass(rng.standard_normal(wn), 400, 5000) * np.sin(np.pi * wt / d) ** 2, at, 0.08)
    # silence gap right before the pivot makes "Neither." land
    gap = (t > dark_end - 0.18) & (t < dark_end)
    mix[gap] *= np.linspace(1, 0.05, gap.sum())
    fo = int(1.5 * SR); mix[-fo:] *= np.linspace(1, 0, fo)
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.7
    wavfile.write(str(out), SR, np.stack([mix, mix], 1).astype(np.float32))


def page(f, total):
    css = CSS
    for k, (pkg, fl) in {"SG600": ("space-grotesk", "space-grotesk-latin-600-normal.woff2"), "SG700": ("space-grotesk", "space-grotesk-latin-700-normal.woff2"),
                         "IN400": ("inter", "inter-latin-400-normal.woff2"), "IN500": ("inter", "inter-latin-500-normal.woff2"),
                         "DM500": ("dm-mono", "dm-mono-latin-500-normal.woff2")}.items():
        css = css.replace(f"url({k})", f"url({font(pkg, fl)})")
    js = JS.replace("__TRACKS__", json.dumps(f.tracks)).replace("__TOTAL__", f"{total:.3f}")
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{"".join(f.els)}<script>{js}</script></body></html>'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("outdir")
    ap.add_argument("--fps", type=int, default=30); ap.add_argument("--stills", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text()); out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    f, total, dark_end = build(spec)
    html_ = page(f, total); (out / "reel.html").write_text(html_)
    beats = [3.0, dark_end + 1.2] + [dark_end + 2.05 + 4.3 * i + 3.6 for i in range(len(spec["beats"]))] + [total - 0.5]
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={"width": W, "height": H})
        pg.set_content(html_); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(250); pg.evaluate("fit()")
        for i, ts in enumerate(beats):
            pg.evaluate(f"seek({ts:.3f})"); pg.screenshot(path=str(out / f"still-{i + 1:02d}.png"))
        pg.evaluate("seek(5.6)"); pg.screenshot(path=str(out / "cover.jpg"), type="jpeg", quality=88)
        if a.stills:
            br.close(); return
        nfr = int(math.ceil(total * a.fps)); silent = out / "_v.mp4"
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        for fr in range(nfr):
            pg.evaluate(f"seek({fr / a.fps:.4f})"); ff.stdin.write(pg.screenshot(type="jpeg", quality=93))
        ff.stdin.close(); ff.wait(); br.close()
    wav = out / "_a.wav"; soundtrack(total, f.ev, dark_end, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
                    "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
    silent.unlink(); wav.unlink()
    print(f"rendered {out / 'reel.mp4'} ({total:.1f}s)")


if __name__ == "__main__":
    main()
