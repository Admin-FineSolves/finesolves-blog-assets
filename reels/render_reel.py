#!/usr/bin/env python3
"""Fine Solves reel renderer v2: script.json -> 1080x1920 30fps H.264 MP4 + cover.jpg + stills.

Usage: python3 reels/render_reel.py REEL_DIR/script.json REEL_DIR [--fps 30] [--stills]

Motion system: kinetic type (word-by-word mask reveals), chaos -> order snaps, product UI that
builds itself, before/after strikes, big-number tickers, diagonal brand-band transitions, a slow
camera push-in on every scene, a drifting dot grid, and a top progress line. The soundtrack is
synthesised and synced: a soft pulse, a thump on every cut, ticks on line reveals, plucks on
highlights and snaps, a whoosh on band transitions.

script.json
{
  "id": "2026-11-04", "brand": "finesolves|finehealth|finehr",
  "music": "pulse" | "calm",                       # optional, default pulse
  "scenes": [
    {"type": "kinetic", "dur": 3.0, "eyebrow": "OPD · 10:42 AM",
     "text": "The queue isn't\\nat the doctor.",      # \\n = authored line break; <= 10 words
     "highlight": "doctor.", "hl_style": "bar"|"block",   # optional
     "sub": "optional Inter line", "transition": "bands"}, # transition = band wipe INTO this scene
    {"type": "chaos", "dur": 5.0, "title": "Orders. Stock.\\nInvoices.",
     "chips": ["WHATSAPP", "EXCEL", "TALLY", "EMAIL", "PAPER SLIP"],   # 3-6 mono chips
     "label": "ONE SYSTEM"},                           # chips drift scattered, then snap into one card
    {"type": "ui", "dur": 5.5, "title": "Build it\\nas care happens.",
     "window": "IPD BILL · BED 12",                    # mono header
     "rows": [{"label": "Room · Day 1", "value": "ADDED"}, ...],   # 2-5 rows, values typed in
     "status": ["IN PROGRESS", "READY"]},              # status chip swaps to the second (teal) at the end
    {"type": "compare", "dur": 5.0, "before_label": "TODAY",
     "before": ["Register on paper", "GST by hand", "Re-type into system"],   # struck through one by one
     "after_label": "WITH FINEHEALTH", "after": "Register. Treat. Bill."},  # navy card rises in
    {"type": "bignum", "dur": 4.5, "label": "TIME SPENT RETYPING", "value": "3,000", "unit": "HRS / YEAR",
     "sub": "2 hrs a day × 6 people", "note": "ILLUSTRATIVE · 250 WORKING DAYS"},
    {"type": "steps", "dur": 3.6, "items": ["Register.", "Treat.", "Bill."], "numbered": false, "title": "optional"},
    {"type": "cards", "dur": 4.6, "title": "optional", "cards": [{"label": "REGISTER", "text": "..."}]},
    {"type": "counter", "dur": 5.0, "rows": ["2 HRS / DAY", "× 6 PEOPLE"], "result": "≈ 3,000 HRS / YEAR", "note": "ILLUSTRATIVE"},
    {"type": "end", "dur": 3.2, "line": "FineHealth by Fine Solves", "tag": "HOSPITAL MANAGEMENT SYSTEM"}
  ]
}
("headline" is accepted as an alias of "kinetic".) The last scene must be "end".
Logo: reels/assets/logo-colour.png and mark-colour.png are used if present; else a wordmark placeholder.
"""
import argparse, base64, html, json, math, random, re, subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FS = ROOT / "node_modules" / "@fontsource"
W, H = 1080, 1920
SR = 48000


def font(pkg, file):
    return "data:font/woff2;base64," + base64.b64encode((FS / pkg / "files" / file).read_bytes()).decode()


def b64img(p):
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def esc(s):
    return html.escape(s or "", quote=True)


class Scene:
    """Collects HTML for one scene plus timed sound events (seconds, scene-relative)."""

    def __init__(self, idx, spec):
        self.i, self.s, self.ev = idx, spec, []

    def snd(self, kind, at, **kw):
        self.ev.append((kind, at, kw))

    # ---------- building blocks
    def kinetic(self, text, at, highlight=None, hl_style="bar", cls="h", stagger=0.07):
        out, t = [], at
        for ln in (text or "").split("\n"):
            pre, hl, post = ln, "", ""
            if highlight and highlight in ln:
                a = ln.index(highlight); pre, hl, post = ln[:a], highlight, ln[a + len(highlight):]
            parts, line_start = [], t
            for chunk, is_hl in ((pre, False), (hl, True), (post, False)):
                if not chunk:
                    continue
                words = []
                for w in re.findall(r"\S+|\s+", chunk):
                    if w.isspace():
                        words.append(" "); continue
                    words.append(f'<span class="w"><span class="wi" data-a="mask" data-at="{t:.3f}">{esc(w)}</span></span>')
                    t += stagger
                inner = "".join(words)
                if is_hl:
                    hat = t + 0.15
                    fill = "hlblock" if hl_style == "block" else "hlbar"
                    inner = f'<span class="hlwrap {fill}-wrap"><i class="{fill}" data-a="bar" data-at="{hat:.3f}"></i>{inner}</span>'
                    self.snd("pluck", hat, note=4)
                parts.append(inner)
            self.snd("tick", line_start)
            out.append(f'<div class="ln">{"".join(parts)}</div>')
            t += 0.06
        return f'<div class="{cls}">{"".join(out)}</div>', t

    def typed(self, text, at, cls="mono eyebrow"):
        dur = 0.03 * len(text)
        self.snd("type", at, n=len(text))
        return f'<div class="{cls}" data-a="type" data-at="{at:.3f}" data-text="{esc(text)}"></div>', at + dur

    def countspan(self, raw, at):
        return f'<span data-a="count" data-at="{at:.3f}" data-v="{raw.replace(",", "")}" data-c="{1 if "," in raw else 0}">{esc(raw)}</span>'

    def counted(self, text, at):
        out, last = [], 0
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
            out.append(esc(text[last:m.start()])); out.append(self.countspan(m.group(0), at)); last = m.end()
        out.append(esc(text[last:]))
        return "".join(out)

    # ---------- scene types
    def build(self):
        s, t = self.s, self.s["type"]
        if t == "headline":
            t = "kinetic"
        self.kind = t
        fn = getattr(self, "b_" + t, None)
        if not fn:
            raise SystemExit(f"unknown scene type: {s['type']}")
        return fn(s)

    def b_kinetic(self, s):
        at, eb, sub = 0.12, "", ""
        if s.get("eyebrow"):
            eb, at = self.typed(s["eyebrow"], 0.05); at += 0.12
        h, at = self.kinetic(s["text"], at, s.get("highlight"), s.get("hl_style", "bar"))
        if s.get("sub"):
            sub = f'<div class="sub" data-a="rise" data-at="{at + 0.15:.3f}">{esc(s["sub"])}</div>'
        return f'<div class="content">{eb}{h}{sub}</div>'

    def b_chaos(self, s):
        title, at = self.kinetic(s.get("title", ""), 0.12, cls="h hs") if s.get("title") else ("", 0.12)
        rnd = random.Random(self.i * 7919 + len(s["chips"]))
        snap = max(at + 0.4 + 0.18 * len(s["chips"]), float(s["dur"]) * 0.5)
        rows, order = [], list(range(len(s["chips"])))
        rnd.shuffle(order)
        for k, c in enumerate(s["chips"]):
            cin = at + 0.1 + 0.18 * k
            dx = [20, 380, 140, 300, 60, 240][order[k]] + rnd.uniform(-30, 30)
            dy = [60, 190, 320, 450, 580, 700][order[k]] + rnd.uniform(-20, 20) - k * 80   # scatter below the title, inside the safe zone
            rot, ph = rnd.uniform(-14, 14), rnd.uniform(0, 6.28)
            self.snd("tick", cin)
            chk_at = snap + 0.55 + 0.12 * k
            rows.append(
                f'<div class="crow2" data-a="snap" data-in="{cin:.3f}" data-at="{snap + 0.03 * k:.3f}" '
                f'data-dx="{dx:.0f}" data-dy="{dy:.0f}" data-rot="{rot:.1f}" data-ph="{ph:.2f}">'
                f'<span class="mono chip">{esc(c)}</span>'
                f'<svg class="chk" viewBox="0 0 24 24"><path data-a="draw" data-at="{chk_at:.3f}" d="M4 12.5l5 5L20 6.5"/></svg></div>')
        self.snd("whoosh", snap - 0.05, dur=0.5); self.snd("pluck", snap + 0.55, note=2); self.snd("pluck", snap + 0.8, note=4)
        lab = s.get("label", "")
        labh = f'<div class="mono boxlabel" data-a="fade" data-at="{snap + 0.3:.3f}">{esc(lab)}</div>' if lab else ""
        return (f'<div class="content">{title}<div class="box"><i class="boxframe" data-a="fade" data-at="{snap + 0.25:.3f}"></i>'
                f'{labh}{"".join(rows)}</div></div>')

    def b_ui(self, s):
        title, at = self.kinetic(s.get("title", ""), 0.12, cls="h hs") if s.get("title") else ("", 0.12)
        win_at = at + 0.1
        st = s.get("status", ["IN PROGRESS", "READY"])
        rows, rt = [], win_at + 0.45
        for r in s["rows"]:
            rows.append(f'<div class="urow" data-a="rise" data-at="{rt:.3f}"><span class="ulab">{esc(r["label"])}</span>'
                        f'<span class="mono uval" data-a="type" data-at="{rt + 0.25:.3f}" data-text="{esc(r.get("value", ""))}"></span></div>')
            self.snd("tick", rt); self.snd("type", rt + 0.25, n=len(r.get("value", "")))
            rt += 0.55
        swap_at = max(rt + 0.2, float(s["dur"]) - 1.3)
        self.snd("chime", swap_at)
        return (f'<div class="content">{title}<div class="win" data-a="pop" data-at="{win_at:.3f}">'
                f'<div class="winhead"><span class="mono winlab">{esc(s.get("window", ""))}</span>'
                f'<span class="mono status" data-a="swap" data-at="{swap_at:.3f}"><span class="s0">{esc(st[0])}</span><span class="s1">{esc(st[-1])}</span></span></div>'
                f'<div class="winbody">{"".join(rows)}</div>'
                f'<i class="winbar" data-a="bar" data-at="{win_at + 0.4:.3f}" data-len="{swap_at - win_at - 0.4:.2f}"></i></div></div>')

    def b_compare(self, s):
        at = 0.12
        bl = f'<div class="mono clab" data-a="fade" data-at="{at:.3f}">{esc(s.get("before_label", "TODAY"))}</div>'
        items, t = [], at + 0.2
        for it in s["before"]:
            items.append(f'<div class="bitem" data-a="rise" data-at="{t:.3f}"><span>{esc(it)}</span><i class="strike" data-at-s="1"></i></div>')
            self.snd("tick", t); t += 0.35
        strike_t = t + 0.35
        out = []
        for k, it in enumerate(items):
            st = strike_t + 0.22 * k
            out.append(it.replace('data-at-s="1"', f'data-a="bar" data-at="{st:.3f}"'))
            self.snd("strike", st)
        after_at = strike_t + 0.22 * len(items) + 0.25
        self.snd("whoosh", after_at - 0.05, dur=0.4); self.snd("pluck", after_at + 0.35, note=3)
        after_h, _ = self.kinetic(s["after"], after_at + 0.25, cls="afterh", stagger=0.06)
        return (f'<div class="content">{bl}<div class="blist">{"".join(out)}</div>'
                f'<div class="after" data-a="rise" data-at="{after_at:.3f}"><div class="mono alab">{esc(s.get("after_label", ""))}</div>{after_h}</div></div>')

    def b_bignum(self, s):
        lab, at = self.typed(s.get("label", ""), 0.05) if s.get("label") else ("", 0.1)
        nat = at + 0.15
        self.snd("rise", nat, dur=1.1); self.snd("pluck", nat + 1.15, note=5)
        num = f'<div class="bignum" data-a="rise" data-at="{nat:.3f}">{self.counted(s["value"], nat)}</div>'
        unit = f'<div class="mono bigunit" data-a="rise" data-at="{nat + 0.2:.3f}"><span class="hlb2">{esc(s.get("unit", ""))}</span></div>' if s.get("unit") else ""
        sub = f'<div class="sub" data-a="rise" data-at="{nat + 0.9:.3f}">{esc(s["sub"])}</div>' if s.get("sub") else ""
        note = f'<div class="mono note" data-a="fade" data-at="{nat + 1.2:.3f}">{esc(s["note"])}</div>' if s.get("note") else ""
        return f'<div class="content">{lab}{num}{unit}{sub}{note}</div>'

    def b_steps(self, s):
        title, at = self.kinetic(s.get("title", ""), 0.12, cls="h hs") if s.get("title") else ("", 0.12)
        items = []
        for k, it in enumerate(s["items"]):
            t = at + 0.1 + 0.42 * k
            mark = (f'<span class="mono stepno">{k + 1:02d}</span>' if s.get("numbered")
                    else f'<i class="sdot" data-a="pop" data-at="{t:.3f}"></i>')
            items.append(f'<div class="step" data-st="{t:.3f}">{mark}<span class="w"><span class="wi" data-a="mask" data-at="{t:.3f}">{esc(it)}</span></span></div>')
            self.snd("pluck", t, note=[0, 2, 4, 5][k % 4])
        line = f'<i class="sline" data-a="bar" data-at="{at + 0.1:.3f}" data-len="{0.42 * (len(items) - 1) + 0.2:.2f}"></i>' if not s.get("numbered") else ""
        return f'<div class="content">{title}<div class="steps {"num" if s.get("numbered") else ""}">{line}{"".join(items)}</div></div>'

    def b_cards(self, s):
        title, at = self.kinetic(s.get("title", ""), 0.12, cls="h hs") if s.get("title") else ("", 0.12)
        cards = []
        for k, c in enumerate(s["cards"]):
            t = at + 0.1 + 0.34 * k
            lab, _ = self.typed(c["label"], t + 0.2, cls="mono clabel")
            cards.append(f'<div class="card" data-a="rise" data-at="{t:.3f}">{lab}<div class="ctext">{esc(c["text"])}</div></div>')
            self.snd("tick", t)
        return f'<div class="content">{title}<div class="cards">{"".join(cards)}</div></div>'

    def b_counter(self, s):
        rows, t = [], 0.15
        for r in s["rows"]:
            rows.append(f'<div class="mono crow" data-a="rise" data-at="{t:.3f}">{self.counted(r, t)}</div>')
            self.snd("tick", t); t += 0.5
        self.snd("pluck", t + 0.3, note=5)
        note = f'<div class="mono note" data-a="fade" data-at="{t + 0.6:.3f}">{esc(s["note"])}</div>' if s.get("note") else ""
        return (f'<div class="content">{"".join(rows)}<i class="rule" data-a="bar" data-at="{t:.3f}"></i>'
                f'<div class="result" data-a="rise" data-at="{t + 0.15:.3f}"><span class="hlb3">{self.counted(s["result"], t + 0.15)}</span></div>{note}</div>')

    def b_end(self, s):
        self.snd("pluck", 0.25, note=0); self.snd("pluck", 0.45, note=4); self.snd("pluck", 0.7, note=7)
        line, at = self.kinetic(s["line"], 0.5, cls="endline", stagger=0.06)
        tag = f'<div class="mono endtag" data-a="fade" data-at="{at + 0.15:.3f}">{esc(s["tag"])}</div>' if s.get("tag") else ""
        bands = ''.join(f'<i class="eb eb{k}" data-a="band" data-at="{0.05 + 0.09 * k:.3f}"></i>' for k in range(3))
        return (f'<div class="bandsdeco">{bands}</div><div class="content endc"><div data-a="fade" data-at="0.2">{LOGO_FULL}</div>'
                f'{line}{tag}<div class="mono site" data-a="fade" data-at="{at + 0.3:.3f}">finesolves.com</div></div>')


CSS = """
@font-face{font-family:SG;font-weight:600;src:url(SG600)}
@font-face{font-family:SG;font-weight:700;src:url(SG700)}
@font-face{font-family:SG;font-weight:600;src:url(SG600X);unicode-range:U+0100-02AF,U+20A0-20CF}
@font-face{font-family:IN;font-weight:400;src:url(IN400)}
@font-face{font-family:IN;font-weight:400;src:url(IN400X);unicode-range:U+0100-02AF,U+20A0-20CF}
@font-face{font-family:DM;font-weight:500;src:url(DM500)}
@font-face{font-family:DM;font-weight:500;src:url(DM500X);unicode-range:U+0100-02AF,U+20A0-20CF}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;background:#fff;overflow:hidden}
body{color:#092040;font-family:IN,'DejaVu Sans',sans-serif;position:relative}
.mono{font-family:DM,'DejaVu Sans Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.08em}
#grid{position:absolute;left:-60px;right:-60px;top:-120px;height:2200px;
  background-image:radial-gradient(circle,#E1E4E8 2.2px,transparent 2.8px);background-size:54px 54px;opacity:.55}
#prog{position:absolute;left:0;top:0;height:6px;width:1080px;background:#09A9A5;transform-origin:left;transform:scaleX(0)}
.scene{position:absolute;inset:0;visibility:hidden}
.content{position:absolute;left:96px;right:96px;top:300px;bottom:500px;display:flex;flex-direction:column;justify-content:center;gap:36px;transform-origin:20% 50%}
[data-a]{will-change:transform,opacity}
.eyebrow{color:#08545C;font-size:32px;min-height:40px}
.h{font-family:SG,'DejaVu Sans',sans-serif;font-weight:600;font-size:118px;line-height:1.0;letter-spacing:-.055em;color:#092040}
.hs{font-size:84px}
.ln{display:block;white-space:nowrap}
.w{display:inline-block;overflow:hidden;vertical-align:bottom;padding:0 .02em .12em;margin:0 -.02em -.12em}
.wi{display:inline-block;transform:translateY(110%)}
.hlwrap{position:relative;display:inline-block}
.hlbar{position:absolute;left:0;right:0;bottom:-.13em;height:12px;background:#09A9A5;transform-origin:left;transform:scaleX(0)}
.hlblock{position:absolute;left:-.08em;right:-.08em;top:.1em;bottom:.02em;background:#09A9A5;transform-origin:left;transform:scaleX(0)}
.hlblock-wrap .wi{color:#080A08}
.sub{font-size:44px;line-height:1.35;color:#56645F;max-width:860px}
/* chaos */
.box{position:relative;display:flex;flex-direction:column;gap:18px;padding:40px 40px 36px}
.boxframe{position:absolute;inset:0;border:1px solid #E1E4E8;border-radius:4px;background:#fff;opacity:0}
.boxlabel{position:relative;font-size:28px;color:#08545C;margin-bottom:6px}
.crow2{position:relative;display:flex;justify-content:space-between;align-items:center;opacity:0}
.chip{display:inline-block;font-size:34px;color:#092040;border:1px solid #092040;border-radius:999px;padding:14px 30px;background:#fff}
.chk{width:56px;height:56px}
.chk path{fill:none;stroke:#09A9A5;stroke-width:2.6;stroke-linecap:round;stroke-linejoin:round}
/* ui */
.win{border:1px solid #E1E4E8;border-radius:4px;background:#fff;position:relative;overflow:hidden;opacity:0}
.winhead{display:flex;justify-content:space-between;align-items:center;padding:26px 36px;border-bottom:1px solid #E1E4E8;background:#F5F7F2}
.winlab{font-size:26px;color:#56645F}
.status{position:relative;font-size:24px;border:1px solid #092040;border-radius:999px;padding:10px 22px;color:#092040;overflow:hidden;display:inline-grid}
.status span{grid-area:1/1}
.status .s1{opacity:0}
.status.on{background:#09A9A5;border-color:#09A9A5;color:#080A08}
.winbody{padding:12px 36px 30px}
.urow{display:flex;justify-content:space-between;align-items:baseline;padding:22px 0;border-bottom:1px solid #E1E4E8;opacity:0}
.urow:last-child{border-bottom:0}
.ulab{font-size:42px;color:#092040}
.uval{font-size:30px;color:#08545C;min-width:10px}
.winbar{position:absolute;left:0;bottom:0;height:6px;width:100%;background:#09A9A5;transform-origin:left;transform:scaleX(0)}
/* compare */
.clab{font-size:30px;color:#56645F;opacity:0}
.blist{display:flex;flex-direction:column;gap:22px}
.bitem{position:relative;align-self:flex-start;font-size:52px;color:#56645F;opacity:0}
.bitem span{position:relative}
.strike{position:absolute;left:-6px;right:-6px;top:55%;height:5px;background:#092040;transform-origin:left;transform:scaleX(0)}
.after{background:#092040;border-radius:4px;padding:40px 44px 46px;opacity:0;margin-top:16px}
.alab{font-size:26px;color:#9FB0C3;margin-bottom:18px}
.afterh{font-family:SG;font-weight:600;font-size:84px;line-height:1;letter-spacing:-.05em;color:#FFFFFF}
/* bignum */
.bignum{font-family:SG;font-weight:600;font-size:300px;line-height:.9;letter-spacing:-.06em;color:#092040;opacity:0;white-space:nowrap}
.bigunit{font-size:46px;opacity:0}
.hlb2,.hlb3{background:#09A9A5;color:#080A08;padding:6px 18px}
.note{font-size:28px;color:#56645F;opacity:0}
/* steps */
.steps{position:relative;display:flex;flex-direction:column;gap:34px;padding-left:76px}
.steps.num{padding-left:0}
.sline{position:absolute;left:13px;top:60px;bottom:60px;width:2px;background:#E1E4E8;transform-origin:top;transform:scaleY(0)}
.step{position:relative;font-family:SG;font-weight:600;font-size:118px;line-height:1;letter-spacing:-.055em;display:flex;align-items:center;gap:30px}
.steps.num .step{font-size:84px}
.sdot{position:absolute;left:-76px;width:28px;height:28px;border-radius:50%;background:#fff;border:2px solid #E1E4E8;opacity:0}
.sdot.on{background:#09A9A5;border-color:#09A9A5}
.stepno{font-family:DM;font-size:40px;color:#08545C;letter-spacing:.04em;min-width:70px}
/* cards & counter */
.cards{display:flex;flex-direction:column;gap:24px}
.card{border:1px solid #E1E4E8;border-radius:4px;padding:34px 40px;background:#fff;opacity:0}
.clabel{font-size:28px;color:#08545C;margin-bottom:14px;min-height:34px}
.ctext{font-size:46px;line-height:1.25}
.crow{font-size:56px;letter-spacing:.04em;opacity:0}
.rule{display:block;height:2px;background:#092040;transform-origin:left;transform:scaleX(0)}
.result{font-family:SG;font-weight:600;font-size:94px;letter-spacing:-.04em;line-height:1.15;opacity:0}
/* end */
.endc{justify-content:center;gap:34px}
.endline{font-family:SG;font-weight:600;font-size:70px;line-height:1.05;letter-spacing:-.045em}
.endtag{font-size:30px;color:#08545C;opacity:0}
.site{font-size:32px;color:#56645F;opacity:0}
.bandsdeco{position:absolute;inset:0;overflow:hidden}
.eb{position:absolute;right:-900px;width:2400px;transform:rotate(-35deg) translateX(2200px);transform-origin:center}
.eb0{height:56px;background:#09A9A5;bottom:330px}
.eb1{height:210px;background:#092040;bottom:60px}
.eb2{height:40px;background:#09A9A5;bottom:-90px}
.wm{font-family:SG;font-weight:700;font-size:88px;letter-spacing:-.04em;color:#092040}
.wm b{font-weight:700;color:#08545C}
.wm.sm{font-size:36px}
#mark{position:absolute;left:96px;top:1440px;opacity:0}
#wipe{position:absolute;inset:0;pointer-events:none;overflow:hidden}
#wipe i{position:absolute;left:50%;top:50%;width:4200px;transform-origin:center}
.wt1{height:90px;background:#09A9A5;margin-top:-1360px}
.wn{height:2600px;background:#092040;margin-top:-1300px}
.wt2{height:90px;background:#09A9A5;margin-top:1300px}
"""

JS = r"""
const E = p => 1 - Math.pow(1 - Math.min(Math.max(p, 0), 1), 4);        // easeOutQuart, no overshoot
const IO = p => { p = Math.min(Math.max(p, 0), 1); return p < .5 ? 8*p*p*p*p : 1 - Math.pow(-2*p + 2, 4) / 2; };
const C = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
const TOTAL = __TOTAL__;
const fmt = (v, comma, target) => comma ? Math.round(v).toLocaleString('en-IN') : (Number.isInteger(target) ? String(Math.round(v)) : v.toFixed(1));
window.fit = () => {
  document.querySelectorAll('.h,.afterh,.endline').forEach(h => {
    let fs = parseFloat(getComputedStyle(h).fontSize);
    const max = h.closest('.after') ? 800 : 888;
    const over = () => [...h.querySelectorAll('.ln')].some(l => l.scrollWidth > max);
    while (over() && fs > 56) { fs -= 4; h.style.fontSize = fs + 'px'; }
  });
  document.querySelectorAll('.bignum').forEach(b => { let fs = 300; while (b.scrollWidth > 888 && fs > 120) { fs -= 10; b.style.fontSize = fs + 'px'; } });
  document.querySelectorAll('path[data-a=draw]').forEach(p => { const L = p.getTotalLength(); p.style.strokeDasharray = L; p.dataset.len = L; });
};
const SCENES = [...document.querySelectorAll('.scene')].map(sc => ({ sc, st: +sc.dataset.start, du: +sc.dataset.dur,
  end: sc.classList.contains('t-end'), trans: sc.dataset.trans, content: sc.querySelector('.content'),
  els: [...sc.querySelectorAll('[data-a]')] }));
window.seek = (t) => {
  let showMark = false;
  document.getElementById('grid').style.transform = `translateY(${-t * 9}px)`;
  document.getElementById('prog').style.transform = `scaleX(${C(t / TOTAL)})`;
  for (const S of SCENES) {
    const lt = t - S.st;
    if (lt < 0 || lt >= S.du) { S.sc.style.visibility = 'hidden'; continue; }
    S.sc.style.visibility = 'visible';
    if (!S.end) showMark = true;
    const ex = S.end ? 1 : C((S.du - lt) / 0.32);           // 1 -> 0 over the last 0.32s
    const exE = 1 - E(1 - ex);
    if (S.content) S.content.style.transform = `scale(${1 + 0.035 * IO(lt / S.du)})`;   // slow camera push-in
    for (const el of S.els) {
      const a = el.dataset.a, at = +el.dataset.at;
      if (a === 'mask') {
        const p = E((lt - at) / 0.55);
        el.style.transform = `translateY(${110 * (1 - p) - 110 * (1 - exE)}%)`;
      } else if (a === 'rise') {
        const p = E((lt - at) / 0.55);
        el.style.opacity = p * ex; el.style.transform = `translateY(${40 * (1 - p) - 30 * (1 - exE)}px)`;
      } else if (a === 'fade') {
        el.style.opacity = E((lt - at) / 0.45) * ex;
      } else if (a === 'pop') {
        const p = E((lt - at) / 0.5);
        el.style.opacity = p * ex; el.style.transform = `scale(${0.94 + 0.06 * p})`;
        if (el.classList.contains('sdot')) el.classList.toggle('on', lt >= at + 0.15);
      } else if (a === 'bar') {
        const len = +(el.dataset.len || 0.5);
        const p = len > 0.6 ? C((lt - at) / len) : E((lt - at) / len);
        el.style.transform = el.classList.contains('sline') ? `scaleY(${p})` : `scaleX(${p})`;
        el.style.opacity = ex;
      } else if (a === 'draw') {
        const L = +el.dataset.len; el.style.strokeDashoffset = L * (1 - E((lt - at) / 0.45));
      } else if (a === 'type') {
        const txt = el.dataset.text; const n = Math.floor(C((lt - at) / (0.03 * txt.length + 0.001)) * txt.length);
        el.textContent = lt < at ? '' : txt.slice(0, n); el.style.opacity = ex;
      } else if (a === 'count') {
        const v = +el.dataset.v; el.textContent = fmt(v * IO((lt - at) / 1.1), el.dataset.c === '1', v);
      } else if (a === 'swap') {
        const p = E((lt - at) / 0.35);
        el.querySelector('.s0').style.opacity = 1 - p; el.querySelector('.s1').style.opacity = p;
        el.querySelector('.s0').style.transform = `translateY(${-30 * p}px)`; el.querySelector('.s1').style.transform = `translateY(${30 * (1 - p)}px)`;
        el.classList.toggle('on', p > 0.5);
      } else if (a === 'snap') {
        const pin = E((lt - +el.dataset.in) / 0.45), p = IO((lt - at) / 0.75);
        const ph = +el.dataset.ph, dx = +el.dataset.dx, dy = +el.dataset.dy, rot = +el.dataset.rot;
        const fx = dx + Math.sin(lt * 1.3 + ph) * 18, fy = dy + Math.cos(lt * 1.1 + ph) * 14, fr = rot + Math.sin(lt * .9 + ph) * 4;
        el.style.opacity = pin * ex;
        el.style.transform = `translate(${fx * (1 - p)}px, ${fy * (1 - p) - 30 * (1 - exE)}px) rotate(${fr * (1 - p)}deg) scale(${0.92 + 0.08 * pin})`;
      } else if (a === 'band') {
        const p = E((lt - at) / 0.8);
        el.style.transform = `rotate(-35deg) translateX(${2200 * (1 - p)}px)`;
      }
    }
  }
  // band wipe across cuts into scenes marked transition=bands
  const wipe = document.getElementById('wipe'); let wp = -1;
  for (const S of SCENES) if (S.trans === 'bands' && Math.abs(t - S.st) < 0.42) wp = (t - S.st + 0.42) / 0.84;
  if (wp >= 0) { wipe.style.visibility = 'visible';
    wipe.querySelectorAll('i').forEach((b, j) => { const k = C(wp * 1.08 - (2 - j) * 0.04);
      const off = k < 0.5 ? 3400 * (1 - E(k * 2)) : -3400 * Math.pow((k - 0.5) * 2, 2.2);   // glide in, settle, leave
      b.style.transform = `translate(-50%,0) rotate(-35deg) translateY(${-off}px)`; }); }
  else wipe.style.visibility = 'hidden';
  const m = document.getElementById('mark'); m.style.opacity = showMark ? C(t / 0.5) : 0;
};
"""


def build_page(script):
    global LOGO_FULL
    logo, mark = HERE / "assets" / "logo-colour.png", HERE / "assets" / "mark-colour.png"
    LOGO_FULL = (f'<img src="{b64img(logo)}" style="max-width:430px;height:auto">' if logo.exists()
                 else '<span class="wm">Fine <b>Solves</b></span>')
    MARK = (f'<img src="{b64img(mark)}" style="height:64px">' if mark.exists() else '<span class="wm sm">Fine <b>Solves</b></span>')
    secs, events, t0 = [], [], 0.0
    for i, s in enumerate(script["scenes"]):
        sc = Scene(i, s); body = sc.build()
        secs.append(f'<section class="scene t-{sc.kind}" data-start="{t0:.3f}" data-dur="{s["dur"]}" '
                    f'data-trans="{esc(s.get("transition", ""))}">{body}</section>')
        events.append(("thump", t0, {}))
        if s.get("transition") == "bands":
            events.append(("whoosh", t0 - 0.5, {"dur": 1.0}))
        events += [(k, t0 + a, kw) for k, a, kw in sc.ev]
        t0 += float(s["dur"])
    css = CSS
    for k, (pkg, f) in {"SG600X": ("space-grotesk", "space-grotesk-latin-ext-600-normal.woff2"),
                        "SG600": ("space-grotesk", "space-grotesk-latin-600-normal.woff2"),
                        "SG700": ("space-grotesk", "space-grotesk-latin-700-normal.woff2"),
                        "IN400X": ("inter", "inter-latin-ext-400-normal.woff2"), "IN400": ("inter", "inter-latin-400-normal.woff2"),
                        "DM500X": ("dm-mono", "dm-mono-latin-ext-500-normal.woff2"), "DM500": ("dm-mono", "dm-mono-latin-500-normal.woff2")}.items():
        css = css.replace(f"url({k})", f"url({font(pkg, f)})")
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'<div id="grid"></div>{"".join(secs)}<div id="mark">{MARK}</div>'
            f'<div id="wipe"><i class="wt1"></i><i class="wn"></i><i class="wt2"></i></div><div id="prog"></div>'
            f'<script>{JS.replace("__TOTAL__", f"{t0:.3f}")}</script></body></html>')
    return page, t0, events


# ---------------------------------------------------------------- sound design
SCALE = [220.00, 246.94, 277.18, 329.63, 369.99, 440.00, 493.88, 554.37, 659.25, 739.99]   # A major pentatonic


def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1) * np.exp(-t / d)


def tone(f, dur, a=0.004, d=0.35, harm=(1, .35, .12)):
    n = int(dur * SR); t = np.arange(n) / SR
    w = sum(h * np.sin(2 * np.pi * f * (k + 1) * t) for k, h in enumerate(harm))
    return w * env(n, a, d)


def lowpass(x, cutoff):
    from scipy.signal import butter, lfilter
    b, a = butter(2, cutoff / (SR / 2)); return lfilter(b, a, x)


def bandpass(x, lo, hi):
    from scipy.signal import butter, lfilter
    b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band"); return lfilter(b, a, x)


def soundtrack(total, events, style, out):
    n = int((total + 0.5) * SR); mix = np.zeros(n); rng = np.random.default_rng(7)
    t = np.arange(n) / SR

    def add(sig, at, gain):
        i = int(max(at, 0) * SR); j = min(n, i + len(sig))
        if j > i: mix[i:j] += gain * sig[:j - i]

    # pad: two chords crossfading every 8s, slow attack
    chA, chB = [220, 277.18, 329.63, 415.30], [185, 233.08, 277.18, 369.99]
    w = 0.5 + 0.5 * np.cos(2 * np.pi * t / 16)
    pad = sum((w * np.sin(2 * np.pi * a * t + k) + (1 - w) * np.sin(2 * np.pi * b * t + k)) for k, (a, b) in enumerate(zip(chA, chB)))
    pad = lowpass(pad * (0.8 + 0.2 * np.sin(2 * np.pi * 0.2 * t)), 1400)
    mix += 0.018 * pad * np.minimum(t / 1.5, 1)
    if style == "pulse":                      # 100 bpm: soft kick on beats 1 & 3, shaker on off-beats
        beat = 0.6
        for k in range(int(total / beat) + 1):
            bt = k * beat
            if k % 2 == 0:
                kn = int(0.28 * SR); kt = np.arange(kn) / SR
                kick = np.sin(2 * np.pi * (48 + 60 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 14)
                add(kick, bt, 0.16)
            sh = bandpass(rng.standard_normal(int(0.05 * SR)), 5000, 11000) * env(int(0.05 * SR), 0.002, 0.012)
            add(sh, bt + beat / 2, 0.05)
    for kind, at, kw in events:
        if kind == "thump":
            kn = int(0.35 * SR); kt = np.arange(kn) / SR
            add(np.sin(2 * np.pi * (42 + 50 * np.exp(-kt * 25)) * kt) * np.exp(-kt * 9), at, 0.22)
        elif kind == "tick":
            add(tone(1800, 0.06, 0.001, 0.012, (1,)), at, 0.05)
        elif kind == "type":
            for c in range(min(kw.get("n", 6), 30)):
                add(bandpass(rng.standard_normal(int(0.012 * SR)), 2500, 7000) * env(int(0.012 * SR), 0.001, 0.004), at + 0.03 * c, 0.035)
        elif kind == "pluck":
            f = SCALE[kw.get("note", 4) % len(SCALE)] * 2
            add(lowpass(tone(f, 0.9, 0.003, 0.28), 4000), at, 0.075)
        elif kind == "chime":
            add(tone(SCALE[8] * 2, 1.2, 0.002, 0.45), at, 0.06); add(tone(SCALE[5] * 2, 1.2, 0.002, 0.5), at + 0.09, 0.05)
        elif kind == "strike":
            add(bandpass(rng.standard_normal(int(0.16 * SR)), 900, 3500) * env(int(0.16 * SR), 0.03, 0.05), at, 0.09)
        elif kind == "whoosh":
            d = kw.get("dur", 0.5); wn = int(d * SR); wt = np.arange(wn) / SR
            nz = bandpass(rng.standard_normal(wn), 400, 5000) * np.sin(np.pi * wt / d) ** 2
            add(nz, at, 0.12)
        elif kind == "rise":
            d = kw.get("dur", 1.0); rn = int(d * SR); rt = np.arange(rn) / SR
            add(np.sin(2 * np.pi * (300 * rt + 300 * rt ** 2 / d)) * (rt / d) ** 2 * 0.5, at, 0.05)
    fade = np.ones(n); fo = int(1.5 * SR); fade[-fo:] = np.linspace(1, 0, fo)
    mix = mix * fade; mix = mix / max(1e-6, np.abs(mix).max()) * 0.7
    wavfile.write(str(out), SR, np.stack([mix, mix], 1).astype(np.float32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("outdir")
    ap.add_argument("--fps", type=int, default=30); ap.add_argument("--stills", action="store_true")
    a = ap.parse_args()
    script = json.loads(Path(a.script).read_text())
    assert script["scenes"][-1]["type"] == "end", "last scene must be type end"
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    page_html, total, events = build_page(script)
    (out / "reel.html").write_text(page_html)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.set_content(page_html); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(250); pg.evaluate("fit()")
        t0 = 0.0
        for i, s in enumerate(script["scenes"]):
            pg.evaluate(f"seek({t0 + max(float(s['dur']) - 0.4, 0):.3f})")
            pg.screenshot(path=str(out / f"still-{i + 1:02d}.png")); t0 += float(s["dur"])
        pg.evaluate(f"seek({max(float(script['scenes'][0]['dur']) - 0.4, 0):.3f})")
        pg.screenshot(path=str(out / "cover.jpg"), type="jpeg", quality=88)
        if a.stills:
            br.close(); return
        nfr = int(math.ceil(total * a.fps)); silent = out / "_video.mp4"
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-c:v", "mjpeg",
                               "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                               "-r", str(a.fps), str(silent)], stdin=subprocess.PIPE)
        for f in range(nfr):
            pg.evaluate(f"seek({f / a.fps:.4f})"); ff.stdin.write(pg.screenshot(type="jpeg", quality=93))
        ff.stdin.close(); ff.wait(); br.close()
    wav = out / "_audio.wav"; soundtrack(total, events, script.get("music", "pulse"), wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
                    "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
    silent.unlink(); wav.unlink()
    print(f"rendered {out / 'reel.mp4'} ({total:.1f}s, {nfr} frames, {len(events)} sound events)")


if __name__ == "__main__":
    main()
