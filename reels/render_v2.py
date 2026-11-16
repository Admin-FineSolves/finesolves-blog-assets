#!/usr/bin/env python3
"""Fine Solves reel renderer v2 ("story" format): script.json (version 2) -> 1080x1920 30fps MP4 + cover + stills.

Why v2: v1 reels were type on white. v2 tells the story with full-bleed colour, big type, detailed props
(phone, calendar, call cards, product window, module tiles), a cursor that clicks, scene transitions,
burned-in captions and an optional ElevenLabs voiceover mixed over a ducked music bed.

Usage:
  python3 reels/render_v2.py DIR/script.json DIR [--fps 30] [--stills]
Voiceover: put one file per scene in DIR/vo/NN.mp3 (NN = scene number, 01..). Scenes with a VO file take
their length from it (VO + padding). Scenes without one use "dur" (or an estimate from the caption text).

script.json (version 2)
{
 "version": 2, "id": "2026-11-17", "brand": "finehr|finesolves", "music": "pulse|calm",
 "scenes": [
  # every scene: "bg": "navy"|"cream"|"teal", "vo": "spoken line (also the burned-in caption)",
  #              "headline": "Big line\\nbreak", "highlight": "phrase", "eyebrow": "MONO CHIP",
  #              "dur": 3.0 (used when there is no VO), "trans": "push"|"zoom"|"wipe"|"cut" (transition INTO the scene)
  {"type": "phone", "mode": "notifs", "clock": "9:41",
   "items": [{"app": "Calendar", "title": "Intro call?", "body": "Can we do 15 mins today?"}]},
  {"type": "phone", "mode": "chat", "contact": "Candidate", "items": [{"from": "them|me", "text": "..."}]},
  {"type": "calendar", "mode": "fill"|"clear", "label": "Intro call", "stamp": "FULL",
   "keep": [{"day": 1, "slot": 2, "label": "Final round"}]},
  {"type": "calls", "question": "So, tell me about yourself?", "names": ["Aarav S.", "Diya M.", "Kabir R.", "Meera P."]},
  {"type": "statement", "sub": "optional smaller line"},
  {"type": "app", "product": "FineHR", "nav": ["AI interviewer", "Attendance", "Leave", "Payroll"], "active": 0,
   "title": "AI interviewer · Frontend developer",
   "rows": [{"name": "Aarav S.", "from": "INVITED", "to": "DONE"}], "button": "Review answers", "toast": "First round done"},
  {"type": "modules", "title": "FineHR", "modules": ["AI interviewer", "Attendance", "Leave", "Payroll"]},
  {"type": "sheet", "title": "attendance_nov_FINAL_v3.xlsx", "cols": ["Name", "Present", "Leave", "OT"],
   "rows": [["Ravi", "24", "?", "6"]], "flags": [[0, 2]], "note": "Who updated this?"},
  {"type": "end", "line": "FineHR by Fine Solves", "tag": "HRMS · AI INTERVIEWER", "cta": "Book a demo"}
 ]
}
Rules the audit enforces: headline ≤ 3 lines of ≤ 18 chars; every prop string ≤ 32 chars; VO ≤ 22 words per scene.
"""
import argparse, base64, html, json, math, random, re, subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FS = ROOT / "node_modules" / "@fontsource"
W, H, SR = 1080, 1920, 48000
NAVY, TEAL, TEALB, CORAL = "#092040", "#09A9A5", "#2DE2C5", "#E2554F"
TRANS = 0.5


def font(pkg, w):
    f = FS / pkg / "files" / f"{pkg}-latin-{w}-normal.woff2"
    return "data:font/woff2;base64," + base64.b64encode(f.read_bytes()).decode()


def esc(s):
    return html.escape(str(s or ""), quote=True)


def ffdur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


ICONS = {
    "AI interviewer": '<path d="M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "Attendance": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "Leave": '<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
    "Payroll": '<rect x="3" y="6" width="18" height="12" rx="2.5"/><circle cx="12" cy="12" r="2.6"/><path d="M6.5 9.5v5M17.5 9.5v5"/>',
    "Hiring": '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><path d="M17 8v6M14 11h6"/>',
    "default": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12h8"/>',
}


def icon(name, cls="ic"):
    return f'<svg class="{cls}" viewBox="0 0 24 24">{ICONS.get(name, ICONS["default"])}</svg>'


class Scene:
    def __init__(self, i, s, dur):
        self.i, self.s, self.dur, self.ev = i, s, dur, []
        self.bg = s.get("bg", "cream")

    def snd(self, kind, at, **kw):
        self.ev.append((kind, at, kw))

    # ---------------------------------------------------------------- shared pieces
    def head(self, at=0.15, size=None, slam=False):
        s = self.s
        if not s.get("headline"):
            return "", at
        lines = s["headline"].split("\n")
        longest = max(len(l) for l in lines)
        size = size or (124 if longest <= 12 else 108 if longest <= 15 else 94)
        hl = s.get("highlight") or ""
        out, t = [], at
        for ln in lines:
            words = re.findall(r"\S+", ln)
            spans = []
            for w in words:
                is_hl = bool(hl) and w.strip(".,?!:") in hl.split() and hl in s["headline"]
                kind = "slam" if slam else "mask"
                cls = "w hl" if is_hl else "w"
                spans.append(f'<span class="wm"><span class="{cls}" data-a="{kind}" data-at="{t:.3f}">{esc(w)}</span></span>')
                t += 0.09 if slam else 0.07
            out.append(f'<div class="hln">{" ".join(spans)}</div>')
            self.snd("thump" if slam else "tick", t - 0.05)
            t += 0.05
        eb = ""
        if s.get("eyebrow"):
            eb = f'<div class="eyebrow" data-a="rise" data-at="{max(at - 0.1, 0):.3f}"><i></i>{esc(s["eyebrow"])}</div>'
        return f'<div class="head">{eb}<div class="h" style="font-size:{size}px">{"".join(out)}</div></div>', t

    def cursor(self, path):
        """path: [[t, '#id' | [x, y], click?], ...] in scene time; coordinates are resolved in JS."""
        for k in path:
            if len(k) > 2 and k[2]:
                self.snd("click", k[0])
        return f'<div class="cur" data-path=\'{esc(json.dumps(path))}\'><svg viewBox="0 0 32 32"><path d="M6 3l20 12.5-8.6 1.9 4.9 9.3-3.9 2-4.9-9.4L6 26z"/></svg><i class="rip"></i></div>'

    # ---------------------------------------------------------------- scene types
    def build(self):
        fn = getattr(self, "b_" + self.s["type"], None)
        if not fn:
            raise SystemExit(f"unknown scene type: {self.s['type']}")
        return fn(self.s)

    def b_statement(self, s):
        h, t = self.head(0.2, size=132)
        sub = f'<div class="sub" data-a="rise" data-at="{t + 0.25:.3f}">{esc(s["sub"])}</div>' if s.get("sub") else ""
        rings = "".join(f'<i class="ring" style="--k:{k}" data-a="ring" data-at="{0.05 + 0.18 * k:.3f}"></i>' for k in range(4))
        self.snd("rise", 0.0, dur=0.6); self.snd("pluck", 0.35, note=4)
        return f'<div class="rings">{rings}</div><div class="center">{h}{sub}</div>'

    def b_phone(self, s):
        h, t = self.head(0.15, slam=(self.i == 0))
        body, n = "", len(s.get("items", []))
        if s.get("mode", "notifs") == "notifs":
            st = t + 0.15
            gap = max(0.16, min(0.42, (self.dur - st - 0.8) / max(n, 1)))
            cards = []
            for k, it in enumerate(s["items"]):
                at = st + k * gap * (1 - 0.03 * k)
                letter = esc((it.get("app") or "?")[0])
                cards.append(f'<div class="notif" style="--k:{n - 1 - k}" data-a="drop" data-at="{at:.3f}">'
                             f'<div class="nap"><b>{letter}</b><span>{esc(it.get("app", ""))}</span><em>now</em></div>'
                             f'<div class="nti">{esc(it.get("title", ""))}</div><div class="nbo">{esc(it.get("body", ""))}</div></div>')
                self.snd("pop", at, note=k)
            body = (f'<div class="lock"><div class="ltime">{esc(s.get("clock", "9:41"))}</div><div class="ldate">Monday</div></div>'
                    f'<div class="nstack">{"".join(reversed(cards))}</div>')
        else:
            st, msgs = t + 0.2, []
            for k, it in enumerate(s["items"]):
                at = st + k * 0.75
                who = "me" if it.get("from") == "me" else "them"
                if who == "them":
                    msgs.append(f'<div class="typing" data-a="blip" data-at="{at - 0.45:.3f}" data-d="0.45"><i></i><i></i><i></i></div>')
                msgs.append(f'<div class="bub {who}" data-a="bub" data-at="{at:.3f}">{esc(it["text"])}</div>')
                self.snd("pop", at, note=2 if who == "me" else 5)
            body = (f'<div class="chead"><span class="cav">{esc(s.get("contact", "C")[0])}</span>'
                    f'<b>{esc(s.get("contact", "Chat"))}</b></div><div class="cbody">{"".join(msgs)}</div>')
        self.snd("whoosh", 0.05, dur=0.4)
        return (f'{h}<div class="phonewrap" data-a="phonein" data-at="0.05"><div class="phone" data-float="1">'
                f'<i class="notch"></i><div class="screen {s.get("mode", "notifs")}">{body}</div></div></div>')

    def b_calendar(self, s):
        h, t = self.head(0.15)
        days = s.get("days", ["MON", "TUE", "WED", "THU", "FRI", "SAT"])
        hours = s.get("hours", ["10", "11", "12", "1", "2", "3", "4", "5"])
        nd, nh = len(days), len(hours)
        keep = {(k["day"], k["slot"]): k.get("label", "") for k in s.get("keep", [])}
        rnd = random.Random(17 + self.i)
        cells = [(d, r) for d in range(nd) for r in range(nh)]
        rnd.shuffle(cells)
        mode = s.get("mode", "fill")
        fill_cells = [c for c in cells if rnd.random() < 0.86 or c in keep]
        blocks, st = [], t + 0.2
        span = max(1.2, self.dur - st - 1.3)
        for k, (d, r) in enumerate(fill_cells):
            frac = k / max(len(fill_cells) - 1, 1)
            at = st + span * (frac ** 0.75)
            kept = (d, r) in keep
            pos = f"left:{d / nd * 100:.4f}%;top:{r / nh * 100:.4f}%;width:{100 / nd:.4f}%;height:{100 / nh:.4f}%"
            if mode == "fill":
                blocks.append(f'<div class="blk" style="{pos}" data-a="pop" data-at="{at:.3f}"><span>{esc(s.get("label", "Call"))}</span></div>')
                if k % 3 == 0:
                    self.snd("tick", at)
            else:
                if kept:
                    flip = st + span * 0.85
                    blocks.append(f'<div class="blk keep" style="{pos}" data-a="flipon" data-at="{flip:.3f}">'
                                  f'<span class="b0">{esc(s.get("label", "Call"))}</span><span class="b1">{esc(keep[(d, r)])}</span></div>')
                else:
                    blocks.append(f'<div class="blk" style="{pos}" data-a="vanish" data-at="{at * 0.8:.3f}"><span>{esc(s.get("label", "Call"))}</span></div>')
                    if k % 4 == 0:
                        self.snd("tick", at * 0.8)
        if mode == "clear":
            self.snd("chime", st + span * 0.85)
        stamp = ""
        if s.get("stamp"):
            sat = self.dur - 1.0
            stamp = f'<div class="stamp {"good" if mode == "clear" else ""}" data-a="stamp" data-at="{sat:.3f}">{esc(s["stamp"])}</div>'
            self.snd("thump", sat + 0.08)
        dh = "".join(f'<div>{esc(d)}</div>' for d in days)
        hh = "".join(f'<div>{esc(x)}</div>' for x in hours)
        return (f'{h}<div class="cal" data-a="rise" data-at="0.05" data-float="1"><div class="calhead"><span>THIS WEEK</span><i></i></div>'
                f'<div class="calgrid"><div class="days">{dh}</div><div class="hours">{hh}</div>'
                f'<div class="cells" style="--nd:{nd};--nh:{nh}">{"".join(blocks)}</div></div>{stamp}</div>')

    def b_calls(self, s):
        h, t = self.head(0.15)
        names = s.get("names", ["Candidate 1", "Candidate 2", "Candidate 3", "Candidate 4"])
        n = len(names)
        st = t + 0.1
        gap = max(0.45, (self.dur - st - 0.9) / n)
        cards = []
        for k, nm in enumerate(names):
            at = st + k * gap
            cards.append(f'<div class="call" style="--k:{k};--n:{n}" data-a="callin" data-at="{at:.3f}">'
                         f'<div class="cbar"><i></i><i></i><i></i><span>{esc(nm)}</span><em>REC</em></div>'
                         f'<div class="ctile"><span class="av">{esc(nm[0])}</span><div class="you"><span class="av sm">Y</span></div></div>'
                         f'<div class="q" data-a="type" data-at="{at + 0.25:.3f}" data-text="{esc(s["question"])}"></div></div>')
            self.snd("whoosh", at - 0.05, dur=0.3); self.snd("type", at + 0.25, n=len(s["question"]))
        return f'{h}<div class="calls">{"".join(cards)}</div>'

    def b_app(self, s):
        h, t = self.head(0.15, size=96)
        nav = "".join(f'<div class="nv {"on" if k == s.get("active", 0) else ""}">{icon(m)}<span>{esc(m)}</span></div>'
                      for k, m in enumerate(s.get("nav", [])))
        rows, at = [], t + 0.35
        rows_n = len(s["rows"])
        flip0 = at + 0.5 * rows_n + 0.2
        flip_end = self.dur - 1.6
        for k, r in enumerate(s["rows"]):
            rat = at + 0.22 * k
            ft = flip0 + (flip_end - flip0) * (k / max(rows_n - 1, 1)) * 0.75
            rows.append(f'<div class="arow" id="r{self.i}_{k}" data-a="rise" data-at="{rat:.3f}"><span class="av">{esc(r["name"][0])}</span>'
                        f'<div class="anm"><b>{esc(r["name"])}</b><span>{esc(r.get("sub", ""))}</span></div>'
                        f'<div class="prog"><i data-a="bar" data-at="{rat + 0.2:.3f}" data-d="{max(ft - rat - 0.2, 0.3):.2f}"></i></div>'
                        f'<span class="chip" data-a="swap" data-at="{ft:.3f}"><span class="s0">{esc(r.get("from", ""))}</span><span class="s1">{esc(r.get("to", ""))}</span></span></div>')
            self.snd("tick", rat); self.snd("chime" if k == rows_n - 1 else "pluck", ft, note=3 + k)
        btn_id = f"btn{self.i}"
        click_t = self.dur - 1.25
        toast = ""
        if s.get("toast"):
            toast = (f'<div class="toast" data-a="toast" data-at="{click_t + 0.15:.3f}"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
                     f'{esc(s["toast"])}</div>')
        cur = self.cursor([[0.0, [980, 1500]], [flip0 - 0.2, [880, 1250]], [click_t - 0.35, f"#{btn_id}"], [click_t, f"#{btn_id}", 1], [self.dur, f"#{btn_id}"]])
        win = (f'<div class="win" data-a="winin" data-at="0.08"><div class="wtop"><i></i><i></i><i></i>'
               f'<span class="wprod"><b>{esc(s.get("product", ""))}</b> by Fine Solves</span></div>'
               f'<div class="wbody"><div class="side">{nav}</div><div class="main"><div class="mtitle">{esc(s.get("title", ""))}</div>'
               f'<div class="rowsw">{"".join(rows)}</div>'
               f'<div class="btn" id="{btn_id}" data-a="press" data-at="{click_t:.3f}">{esc(s.get("button", "Review"))}</div></div></div>'
               f'{cur}</div>')
        return f'{h}{win}{toast}'

    def b_modules(self, s):
        h, t = self.head(0.15)
        mods = s["modules"]
        snap = max(t + 0.6, self.dur * 0.45)
        tiles = []
        dirs = [(-700, -300, -18), (700, -260, 14), (-680, 420, 12), (720, 380, -16), (0, 900, 8), (0, -900, -8)]
        for k, m in enumerate(mods):
            dx, dy, rot = dirs[k % len(dirs)]
            tiles.append(f'<div class="tile" data-a="assemble" data-in="{0.1 + 0.12 * k:.3f}" data-at="{snap + 0.06 * k:.3f}" '
                         f'data-dx="{dx}" data-dy="{dy}" data-rot="{rot}">{icon(m)}<span>{esc(m)}</span>'
                         f'<svg class="tk" viewBox="0 0 24 24"><path data-a="draw" data-at="{snap + 0.6 + 0.12 * k:.3f}" d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>')
            self.snd("tick", t + 0.15 * k)
        self.snd("whoosh", snap - 0.1, dur=0.5); self.snd("chime", snap + 0.6)
        return (f'{h}<div class="mods"><div class="mframe" data-a="fade" data-at="{snap:.3f}"><div class="mtop"><b>{esc(s.get("title", ""))}</b>'
                f'<span>ONE SYSTEM</span></div></div><div class="tgrid n{len(mods)}">{"".join(tiles)}</div></div>')

    def b_sheet(self, s):
        h, t = self.head(0.15)
        cols = s["cols"]
        flags = {tuple(f) for f in s.get("flags", [])}
        head = "".join(f'<div class="sh">{esc(c)}</div>' for c in cols)
        rows, at = [], t + 0.2
        for r, row in enumerate(s["rows"]):
            cells = []
            for c, v in enumerate(row):
                fl = (r, c) in flags
                cells.append(f'<div class="sc {"flag" if fl else ""}" data-a="{"flag" if fl else "type"}" data-at="{at + 0.05 * c:.3f}" data-text="{esc(v)}">{esc(v) if fl else ""}</div>')
            rows.append(f'<div class="sr" style="grid-template-columns:repeat({len(cols)},1fr)">{"".join(cells)}</div>')
            self.snd("type", at, n=6); at += 0.28
        note = ""
        if s.get("note"):
            na = min(at + 0.3, self.dur - 1.0)
            note = f'<div class="sticky" data-a="stick" data-at="{na:.3f}">{esc(s["note"])}</div>'
            self.snd("thump", na + 0.1)
        return (f'{h}<div class="sheet" data-a="rise" data-at="0.05" data-float="1"><div class="stitle"><i></i>{esc(s.get("title", "sheet.xlsx"))}</div>'
                f'<div class="sr shr" style="grid-template-columns:repeat({len(cols)},1fr)">{head}</div>{"".join(rows)}{note}</div>')

    def b_end(self, s):
        self.snd("pluck", 0.2, note=0); self.snd("pluck", 0.4, note=4); self.snd("pluck", 0.62, note=7)
        line = s.get("line", "")
        if " by Fine Solves" in line:
            prod = line.replace(" by Fine Solves", "")
            lh = f'<div class="eprod" data-a="rise" data-at="0.3">{esc(prod)}</div><div class="eby" data-a="rise" data-at="0.45">by Fine <b>Solves</b></div>'
        else:
            lh = (f'<div class="wmk" data-a="rise" data-at="0.25">Fine <b>Solves</b></div>'
                  f'<div class="eline" data-a="rise" data-at="0.45">{esc(line).replace(chr(10), "<br>")}</div>')
        tag = f'<div class="etag" data-a="fade" data-at="0.7">{esc(s.get("tag", ""))}</div>' if s.get("tag") else ""
        click = 1.55
        cta = (f'<div class="cta" id="cta{self.i}" data-a="ctain" data-at="0.9"><span data-a="press" data-at="{click:.3f}">{esc(s.get("cta", "Book a demo"))} →</span></div>'
               f'<div class="site" data-a="fade" data-at="1.1">finesolves.com</div>')
        cur = self.cursor([[0.6, [900, 1560]], [click - 0.3, f"#cta{self.i}"], [click, f"#cta{self.i}", 1], [self.dur, f"#cta{self.i}"]])
        bands = "".join(f'<i class="eb eb{k}" data-a="band" data-at="{0.05 + 0.09 * k:.3f}"></i>' for k in range(3))
        return f'<div class="bands">{bands}</div><div class="center endc">{lh}{tag}{cta}</div>{cur}'


CSS = """
@font-face{font-family:SG;font-weight:500;src:url(SG500)}
@font-face{font-family:SG;font-weight:700;src:url(SG700)}
@font-face{font-family:IN;font-weight:400;src:url(IN400)}
@font-face{font-family:IN;font-weight:500;src:url(IN500)}
@font-face{font-family:IN;font-weight:600;src:url(IN600)}
@font-face{font-family:DM;font-weight:500;src:url(DM500)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:#092040}
body{font-family:IN,sans-serif;-webkit-font-smoothing:antialiased}
.scene{position:absolute;inset:0;overflow:hidden;visibility:hidden;will-change:transform}
.cam{position:absolute;inset:0;transform-origin:50% 45%}
.bg{position:absolute;inset:-60px}
.bg-navy .bg{background:radial-gradient(1200px 900px at 50% 28%,#12346a 0%,#0b2650 38%,#071a38 100%)}
.bg-cream .bg{background:radial-gradient(1100px 900px at 50% 30%,#ffffff 0%,#f4f6f1 55%,#e9ede6 100%)}
.bg-teal .bg{background:radial-gradient(1200px 1000px at 50% 35%,#16c1bb 0%,#09A9A5 45%,#078a87 100%)}
.grid{position:absolute;inset:-60px;opacity:.5;background-image:radial-gradient(circle,rgba(9,32,64,.10) 1.6px,transparent 2px);background-size:44px 44px}
.bg-navy .grid,.bg-teal .grid{background-image:radial-gradient(circle,rgba(255,255,255,.08) 1.6px,transparent 2px)}
.grain{position:absolute;inset:-100px;opacity:.10;mix-blend-mode:overlay;background-image:url(GRAIN);background-size:300px 300px}
.head{position:absolute;left:90px;right:90px;top:250px}
.center{position:absolute;left:90px;right:90px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;padding-bottom:200px}
.h{font-family:SG;font-weight:700;letter-spacing:-.035em;line-height:1.0;color:#092040}
.bg-navy .h,.bg-teal .h{color:#fff}
.hln{display:block}
.wm{display:inline-block;overflow:hidden;vertical-align:top;padding:0 .02em .08em;margin-bottom:-.08em}
.w{display:inline-block;will-change:transform}
.w.hl{color:#09A9A5}.bg-navy .w.hl{color:#2DE2C5}.bg-teal .w.hl{color:#092040}
.eyebrow{display:inline-flex;align-items:center;gap:14px;font-family:DM;font-weight:500;font-size:30px;letter-spacing:.14em;color:#092040;
  background:rgba(9,32,64,.07);border:1.5px solid rgba(9,32,64,.14);padding:12px 22px;border-radius:40px;margin-bottom:30px}
.eyebrow i{width:12px;height:12px;border-radius:50%;background:#09A9A5;box-shadow:0 0 0 6px rgba(9,169,165,.18)}
.bg-navy .eyebrow{color:#cfe9ea;background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.16)}
.bg-navy .eyebrow i{background:#2DE2C5}
.sub{font-family:IN;font-weight:500;font-size:44px;line-height:1.3;color:rgba(255,255,255,.9);margin-top:34px}
.rings{position:absolute;left:50%;top:44%;width:0;height:0}
.ring{position:absolute;left:0;top:0;width:calc(520px + var(--k)*300px);height:calc(520px + var(--k)*300px);border-radius:50%;
  border:2px solid rgba(255,255,255,.22);transform:translate(-50%,-50%)}
/* phone */
.phonewrap{position:absolute;left:50%;top:700px;width:620px;margin-left:-310px;perspective:2400px}
.phone{position:relative;width:620px;height:1240px;border-radius:84px;background:#0b0f17;padding:18px;
  box-shadow:0 60px 120px rgba(0,0,0,.45),0 0 0 3px #2a3140 inset,0 0 0 2px rgba(255,255,255,.08)}
.notch{position:absolute;left:50%;top:34px;width:170px;height:46px;margin-left:-85px;border-radius:30px;background:#000;z-index:3}
.screen{position:relative;width:100%;height:100%;border-radius:68px;overflow:hidden}
.screen.notifs{background:linear-gradient(170deg,#2d4f7c 0%,#1a3358 45%,#0e1f3b 100%)}
.screen.chat{background:#eef1f5}
.lock{text-align:center;color:#fff;padding-top:96px}
.ltime{font-family:SG;font-weight:500;font-size:130px;letter-spacing:-.04em;line-height:1}
.ldate{font-family:IN;font-weight:500;font-size:34px;opacity:.8;margin-top:6px}
.nstack{position:absolute;left:22px;right:22px;top:330px}
.notif{position:absolute;left:0;right:0;top:calc(var(--k)*168px);background:rgba(245,247,250,.94);border-radius:36px;padding:22px 26px 24px;
  box-shadow:0 14px 34px rgba(0,0,0,.28)}
.nap{display:flex;align-items:center;gap:12px;font-family:IN;font-weight:500;font-size:22px;color:#5b6573;letter-spacing:.02em}
.nap b{width:38px;height:38px;border-radius:10px;background:#092040;color:#fff;font-family:SG;font-size:22px;display:flex;align-items:center;justify-content:center}
.nap em{margin-left:auto;font-style:normal}
.nti{font-family:IN;font-weight:600;font-size:31px;color:#0d1522;margin-top:10px}
.nbo{font-family:IN;font-weight:400;font-size:29px;color:#2b3442;margin-top:4px;line-height:1.3}
.chead{display:flex;align-items:center;gap:18px;padding:110px 34px 24px;background:#fff;border-bottom:1px solid #e1e5ea;font-family:IN;font-size:32px;color:#0d1522}
.cav{width:64px;height:64px;border-radius:50%;background:#09A9A5;color:#fff;display:flex;align-items:center;justify-content:center;font-family:SG;font-weight:700;font-size:30px}
.cbody{padding:30px 28px;display:flex;flex-direction:column;gap:18px}
.bub{max-width:80%;font-family:IN;font-size:33px;line-height:1.35;padding:20px 26px;border-radius:30px}
.bub.them{align-self:flex-start;background:#fff;color:#0d1522;border-bottom-left-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,.06)}
.bub.me{align-self:flex-end;background:#092040;color:#fff;border-bottom-right-radius:8px}
.typing{align-self:flex-start;background:#fff;border-radius:30px;padding:24px 26px;display:flex;gap:9px}
.typing i{width:13px;height:13px;border-radius:50%;background:#9aa3ae}
/* calendar */
.cal{position:absolute;left:70px;right:70px;top:650px;height:620px;background:#fff;border-radius:34px;padding:26px 26px 30px;
  box-shadow:0 40px 90px rgba(9,32,64,.20),0 0 0 1.5px rgba(9,32,64,.06)}
.calhead{display:flex;align-items:center;justify-content:space-between;font-family:DM;font-weight:500;font-size:24px;letter-spacing:.14em;color:#56645F;margin-bottom:16px}
.calhead i{width:120px;height:12px;border-radius:6px;background:#e7ebee}
.calgrid{position:relative;height:520px;display:grid;grid-template-columns:62px 1fr;grid-template-rows:40px 1fr}
.days{grid-column:2;display:grid;grid-template-columns:repeat(6,1fr);font-family:DM;font-weight:500;font-size:22px;color:#56645F;text-align:center;letter-spacing:.08em}
.hours{grid-column:1;grid-row:2;display:grid;font-family:DM;font-size:22px;color:#9aa3ae}
.cells{grid-column:2;grid-row:2;position:relative;background-image:linear-gradient(#edf0f2 1.5px,transparent 1.5px),linear-gradient(90deg,#edf0f2 1.5px,transparent 1.5px);
  background-size:calc(100%/var(--nd)) calc(100%/var(--nh));border-radius:10px}
.blk{position:absolute;padding:3px}
.blk span,.blk .b0,.blk .b1{display:flex;align-items:center;width:100%;height:100%;border-radius:10px;background:#dfe6f1;border-left:6px solid #092040;
  font-family:IN;font-weight:600;font-size:17px;color:#092040;padding:0 8px;white-space:nowrap;overflow:hidden}
.blk.keep{}
.blk.keep .b1{position:absolute;inset:3px;width:auto;height:auto;background:#09A9A5;border-left-color:#076e6b;color:#fff;opacity:0}
.stamp{position:absolute;right:40px;bottom:60px;font-family:SG;font-weight:700;font-size:84px;letter-spacing:.04em;color:#E2554F;
  border:8px solid #E2554F;border-radius:20px;padding:6px 28px;transform:rotate(-9deg);background:rgba(255,255,255,.85)}
.stamp.good{color:#078a87;border-color:#09A9A5}
/* call cards */
.calls{position:absolute;left:90px;right:90px;top:600px;height:700px}
.call{position:absolute;left:0;right:0;top:calc(var(--k)*92px);height:470px;border-radius:30px;background:#111a2b;overflow:hidden;
  box-shadow:0 30px 70px rgba(0,0,0,.40);border:1.5px solid rgba(255,255,255,.08)}
.cbar{display:flex;align-items:center;gap:10px;padding:18px 24px;background:#0c1422;font-family:IN;font-weight:500;font-size:24px;color:#c9d2de}
.cbar i{width:13px;height:13px;border-radius:50%;background:#2e3a4e}
.cbar span{margin-left:12px}
.cbar em{margin-left:auto;font-style:normal;font-family:DM;font-size:20px;color:#E2554F;letter-spacing:.12em}
.ctile{position:relative;height:250px;display:flex;align-items:center;justify-content:center;background:radial-gradient(circle at 50% 40%,#25365a,#141f33)}
.av{width:120px;height:120px;border-radius:50%;background:#09A9A5;color:#fff;font-family:SG;font-weight:700;font-size:54px;display:flex;align-items:center;justify-content:center}
.av.sm{width:64px;height:64px;font-size:28px;background:#56645F}
.you{position:absolute;right:22px;bottom:18px;width:150px;height:96px;border-radius:14px;background:#2a3953;display:flex;align-items:center;justify-content:center}
.q{margin:22px 26px 0;min-height:60px;font-family:IN;font-weight:500;font-size:34px;color:#fff;background:rgba(255,255,255,.08);border-radius:16px;padding:14px 20px}
/* product window */
.win{position:absolute;left:60px;right:60px;top:640px;height:700px;background:#fff;border-radius:30px;overflow:hidden;
  box-shadow:0 50px 110px rgba(9,32,64,.28),0 0 0 1.5px rgba(9,32,64,.07)}
.wtop{height:64px;display:flex;align-items:center;gap:10px;padding:0 24px;background:#092040}
.wtop i{width:14px;height:14px;border-radius:50%;background:rgba(255,255,255,.22)}
.wprod{margin-left:16px;font-family:IN;font-size:24px;color:rgba(255,255,255,.7)}
.wprod b{font-family:SG;font-weight:700;color:#fff;font-size:27px}
.wbody{display:flex;height:636px}
.side{width:250px;background:#f4f6f1;padding:22px 14px;display:flex;flex-direction:column;gap:6px;border-right:1.5px solid #e6eae4}
.nv{display:flex;align-items:center;gap:12px;padding:14px 14px;border-radius:14px;font-family:IN;font-weight:500;font-size:22px;color:#56645F}
.nv.on{background:#092040;color:#fff}
.ic{width:30px;height:30px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;flex:none}
.main{flex:1;padding:26px 26px;position:relative}
.mtitle{font-family:SG;font-weight:700;font-size:32px;color:#092040;letter-spacing:-.01em;margin-bottom:18px}
.rowsw{display:flex;flex-direction:column;gap:12px}
.arow{display:grid;grid-template-columns:62px 1fr 110px auto;align-items:center;gap:14px;padding:16px 14px;border-radius:16px;background:#f7f9f6;border:1.5px solid #eceee9}
.arow .av{width:58px;height:58px;font-size:26px;background:#092040}
.anm b{display:block;font-family:IN;font-weight:600;font-size:27px;color:#0d1522}
.anm span{font-family:IN;font-size:19px;color:#56645F}
.prog{height:10px;border-radius:5px;background:#e3e8e4;overflow:hidden}
.prog i{display:block;height:100%;background:#09A9A5;transform-origin:0 50%;transform:scaleX(0)}
.chip{position:relative;display:inline-grid;font-family:DM;font-weight:500;font-size:18px;letter-spacing:.08em;border-radius:20px;overflow:hidden;min-width:150px;text-align:center}
.chip span{grid-area:1/1;padding:10px 14px;border-radius:20px}
.chip .s0{background:#eceff2;color:#56645F}
.chip .s1{background:#09A9A5;color:#fff;opacity:0}
.btn{position:absolute;right:26px;bottom:26px;font-family:IN;font-weight:600;font-size:26px;color:#fff;background:#092040;padding:20px 34px;border-radius:18px}
.toast{position:absolute;left:50%;top:1318px;z-index:5;transform:translateX(-50%);display:flex;align-items:center;gap:14px;background:#0d1522;color:#fff;
  font-family:IN;font-weight:600;font-size:27px;padding:18px 30px;border-radius:40px;box-shadow:0 18px 40px rgba(0,0,0,.3);white-space:nowrap;opacity:0}
.toast svg{width:34px;height:34px;fill:none;stroke:#2DE2C5;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}
/* modules */
.mods{position:absolute;left:70px;right:70px;top:640px;height:640px}
.mframe{position:absolute;inset:0;border-radius:34px;background:rgba(255,255,255,.06);border:2px solid rgba(255,255,255,.22);opacity:0}
.mtop{display:flex;align-items:center;justify-content:space-between;padding:24px 30px;font-family:SG;font-weight:700;font-size:34px;color:#fff}
.mtop span{font-family:DM;font-weight:500;font-size:22px;letter-spacing:.14em;color:#2DE2C5}
.tgrid{position:absolute;left:30px;right:30px;top:100px;bottom:30px;display:grid;grid-template-columns:1fr 1fr;gap:22px}
.tile{position:relative;background:#fff;border-radius:26px;padding:30px;display:flex;flex-direction:column;justify-content:space-between;color:#092040;
  box-shadow:0 24px 50px rgba(0,0,0,.25)}
.tile .ic{width:64px;height:64px;stroke:#09A9A5;stroke-width:1.7}
.tile span{font-family:SG;font-weight:700;font-size:38px;letter-spacing:-.01em}
.tk{position:absolute;right:24px;top:24px;width:44px;height:44px;fill:none;stroke:#09A9A5;stroke-width:3.2;stroke-linecap:round;stroke-linejoin:round}
/* sheet */
.sheet{position:absolute;left:70px;right:70px;top:650px;background:#fff;border-radius:24px;overflow:visible;box-shadow:0 40px 90px rgba(9,32,64,.20)}
.stitle{display:flex;align-items:center;gap:12px;padding:20px 24px;font-family:DM;font-size:23px;color:#56645F;border-bottom:1.5px solid #e6eae4}
.stitle i{width:26px;height:26px;border-radius:6px;background:#1f7a4d}
.sr{display:grid;border-bottom:1.5px solid #eef0ec}
.sh{font-family:IN;font-weight:600;font-size:22px;color:#56645F;padding:14px 18px;background:#f4f6f1}
.sc{font-family:DM;font-size:26px;color:#0d1522;padding:16px 18px;border-right:1.5px solid #eef0ec;min-height:62px}
.sc.flag{background:rgba(226,85,79,.0);color:#E2554F;font-weight:500}
.sticky{position:absolute;right:-10px;bottom:-70px;width:330px;padding:26px 24px;background:#ffe58a;color:#3b3000;font-family:IN;font-weight:600;font-size:30px;
  line-height:1.25;transform:rotate(5deg);box-shadow:0 18px 30px rgba(0,0,0,.18)}
/* end */
.bands{position:absolute;right:-300px;bottom:-200px;width:1100px;height:900px}
.eb{position:absolute;left:0;top:0;width:1600px;height:120px;transform-origin:0 0}
.eb0{background:#09A9A5;top:520px}.eb1{background:#092040;top:660px;height:160px}.eb2{background:#09A9A5;top:860px;height:70px}
.endc{align-items:flex-start}
.eprod{font-family:SG;font-weight:700;font-size:170px;letter-spacing:-.05em;color:#092040;line-height:.95}
.eby{font-family:SG;font-weight:500;font-size:54px;color:#092040;margin-top:14px}
.eby b,.wmk b{color:#09A9A5;font-weight:700}
.wmk{font-family:SG;font-weight:700;font-size:64px;color:#092040;margin-bottom:30px}
.eline{font-family:SG;font-weight:700;font-size:96px;letter-spacing:-.04em;color:#092040;line-height:1.02}
.etag{font-family:DM;font-weight:500;font-size:28px;letter-spacing:.16em;color:#56645F;margin-top:40px}
.cta{margin-top:70px}
.cta span{display:inline-block;font-family:SG;font-weight:700;font-size:46px;color:#fff;background:#092040;padding:30px 50px;border-radius:60px;box-shadow:0 20px 40px rgba(9,32,64,.25)}
.site{font-family:DM;font-weight:500;font-size:30px;color:#092040;margin-top:30px;letter-spacing:.06em}
/* cursor + captions + chrome */
.cur{position:absolute;left:0;top:0;width:56px;height:56px;z-index:20;pointer-events:none}
.cur svg{width:56px;height:56px;fill:#fff;stroke:#092040;stroke-width:2;filter:drop-shadow(0 6px 10px rgba(0,0,0,.35))}
.rip{position:absolute;left:-30px;top:-30px;width:60px;height:60px;border-radius:50%;border:4px solid #2DE2C5;opacity:0}
#cap{position:absolute;left:70px;right:70px;top:1430px;display:flex;justify-content:center;z-index:50}
#cap div{font-family:SG;font-weight:700;font-size:54px;line-height:1.15;color:#fff;background:rgba(9,32,64,.92);padding:16px 28px;border-radius:22px;
  text-align:center;max-width:920px;box-shadow:0 14px 30px rgba(0,0,0,.25)}
#cap b{color:#2DE2C5;font-weight:700}
#prog{position:absolute;left:0;top:0;height:8px;background:#09A9A5;z-index:60}
#wipe{position:absolute;inset:0;z-index:40;visibility:hidden}
#wipe i{position:absolute;left:50%;top:50%;width:3400px;height:1100px;margin:-550px 0 0 -1700px;background:#09A9A5}
#wipe i+i{background:#092040;height:700px;margin-top:-350px}
"""

JS = r"""
const C = x => Math.max(0, Math.min(1, x));
const E = x => 1 - Math.pow(1 - C(x), 3);
const IO = x => { x = C(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const B = x => { x = C(x); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
function center(el, root) { let x = el.offsetWidth / 2, y = el.offsetHeight / 2, n = el;
  while (n && n !== root) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; } return [x, y]; }
const SC = [...document.querySelectorAll('.scene')];
SC.forEach(el => { el._els = [...el.querySelectorAll('[data-a]')]; el._fl = [...el.querySelectorAll('[data-float]')];
  el._cur = el.querySelector('.cur'); });
function anim(el, a, lt, at) {
  const p = lt - at;
  if (a === 'fade') el.style.opacity = E(p / 0.45);
  else if (a === 'rise') { const k = E(p / 0.55); el.style.opacity = k; el.style.transform = `translateY(${50 * (1 - k)}px)`; }
  else if (a === 'mask') { const k = E(p / 0.5); el.style.transform = `translateY(${105 * (1 - k)}%)`; }
  else if (a === 'slam') { const k = E(p / 0.32); el.style.transform = `scale(${1 + 0.6 * (1 - k)})`; el.style.opacity = C(p / 0.12);
    el.style.filter = `blur(${10 * (1 - k)}px)`; }
  else if (a === 'pop') { const k = B(p / 0.32); el.style.transform = `scale(${0.4 + 0.6 * k})`; el.style.opacity = C(p / 0.12); }
  else if (a === 'vanish') { const k = E(p / 0.3); el.style.transform = `scale(${1 - 0.6 * k})`; el.style.opacity = 1 - k; }
  else if (a === 'flipon') { const k = E(p / 0.4); const b1 = el.querySelector('.b1'); b1.style.opacity = k;
    el.style.transform = `scale(${1 + 0.12 * Math.sin(Math.PI * C(p / 0.4))})`; }
  else if (a === 'stamp') { const k = E(p / 0.22); el.style.opacity = C(p / 0.08); el.style.transform = `rotate(-9deg) scale(${1 + 1.4 * (1 - k)})`; }
  else if (a === 'drop') { const k = B(p / 0.42); el.style.opacity = C(p / 0.12);
    el.style.transform = `translateY(${-260 * (1 - k)}px) scale(${0.9 + 0.1 * k})`; }
  else if (a === 'bub') { const k = B(p / 0.36); el.style.opacity = C(p / 0.1); el.style.transform = `scale(${0.6 + 0.4 * k})`;
    el.style.transformOrigin = el.classList.contains('me') ? '100% 100%' : '0 100%'; el.style.display = p < 0 ? 'none' : ''; }
  else if (a === 'blip') { const d = +el.dataset.d; el.style.display = (p >= 0 && p < d) ? 'flex' : 'none';
    el.querySelectorAll('i').forEach((d2, j) => d2.style.transform = `translateY(${-8 * Math.max(0, Math.sin(lt * 9 - j * .7))}px)`); }
  else if (a === 'phonein') { const k = E(p / 0.8); el.style.transform = `translateY(${700 * (1 - k)}px) rotateX(${14 * (1 - k)}deg)`; }
  else if (a === 'callin') { const k = B(p / 0.45); el.style.opacity = C(p / 0.15); el.style.transform = `translateY(${120 * (1 - k)}px) scale(${0.92 + 0.08 * k})`; }
  else if (a === 'type') { const t = el.dataset.text || ''; const n = Math.floor(C(p / (0.035 * t.length + 0.01)) * t.length);
    el.textContent = p < 0 ? '' : t.slice(0, n); }
  else if (a === 'flag') { const k = C(p / 0.2); el.style.opacity = k; el.style.background = `rgba(226,85,79,${0.16 * k + 0.1 * Math.max(0, Math.sin(lt * 7)) * k})`; }
  else if (a === 'stick') { const k = B(p / 0.4); el.style.opacity = C(p / 0.1); el.style.transform = `rotate(${5 + 20 * (1 - k)}deg) scale(${1.6 - 0.6 * k})`; }
  else if (a === 'bar') { const d = +(el.dataset.d || 0.5); el.style.transform = `scaleX(${IO(p / d)})`; }
  else if (a === 'swap') { const k = E(p / 0.3); el.querySelector('.s0').style.opacity = 1 - k; el.querySelector('.s1').style.opacity = k;
    el.style.transform = `scale(${1 + 0.15 * Math.sin(Math.PI * C(p / 0.3))})`; }
  else if (a === 'winin') { const k = E(p / 0.7); el.style.opacity = C(p / 0.2); el.style.transform = `translateY(${160 * (1 - k)}px) scale(${0.94 + 0.06 * k})`; }
  else if (a === 'press') { const k = Math.sin(Math.PI * C(p / 0.22)); el.style.transform = `scale(${1 - 0.07 * k})`;
    if (p > 0.1) el.style.background = '#09A9A5'; else el.style.background = ''; }
  else if (a === 'toast') { const k = B(p / 0.45); el.style.opacity = C(p / 0.12); el.style.transform = `translate(-50%, ${60 * (1 - k)}px)`; }
  else if (a === 'assemble') { const pin = E((lt - +el.dataset.in) / 0.5), k = IO(p / 0.7), dx = +el.dataset.dx, dy = +el.dataset.dy, r = +el.dataset.rot;
    const f = 1 - k, wob = Math.sin(lt * 1.6 + dx) * 10 * f; el.style.opacity = pin;
    el.style.transform = `translate(${dx * f * (0.55 + 0.45 * (1 - pin)) + wob}px, ${dy * f * (0.55 + 0.45 * (1 - pin))}px) rotate(${r * f}deg) scale(${0.85 + 0.15 * k})`; }
  else if (a === 'draw') { const L = 30; el.style.strokeDasharray = L; el.style.strokeDashoffset = L * (1 - E(p / 0.35)); }
  else if (a === 'ring') { const k = E(p / 1.2); el.style.opacity = 0.9 * k; el.style.transform = `translate(-50%,-50%) scale(${0.6 + 0.4 * k + 0.02 * Math.sin(lt * 2 + at)})`; }
  else if (a === 'band') { const k = E(p / 0.8); el.style.transform = `rotate(-32deg) translateX(${1800 * (1 - k)}px)`; }
  else if (a === 'ctain') { const k = B(p / 0.5); el.style.opacity = C(p / 0.15); el.style.transform = `scale(${0.7 + 0.3 * k})`; }
}
function cursor(cur, root, lt) {
  const P = JSON.parse(cur.dataset.path).map(k => { let xy = k[1];
    if (typeof xy === 'string') { const t = root.querySelector(xy); xy = center(t, root); xy = [xy[0] + t.offsetWidth * 0.22, xy[1] + t.offsetHeight * 0.12]; } return [k[0], xy, k[2]]; });
  let x = P[0][1][0], y = P[0][1][1];
  for (let j = 0; j < P.length - 1; j++) if (lt >= P[j][0]) { const k = IO((lt - P[j][0]) / Math.max(P[j + 1][0] - P[j][0], 0.01));
    x = P[j][1][0] + (P[j + 1][1][0] - P[j][1][0]) * k; y = P[j][1][1] + (P[j + 1][1][1] - P[j][1][1]) * k; }
  if (lt >= P[P.length - 1][0]) { x = P[P.length - 1][1][0]; y = P[P.length - 1][1][1]; }
  let rip = 0, dip = 0; for (const k of P) if (k[2] && lt >= k[0] && lt < k[0] + 0.6) { rip = (lt - k[0]) / 0.6; dip = Math.sin(Math.PI * C((lt - k[0]) / 0.2)); }
  cur.style.transform = `translate(${x}px, ${y}px) scale(${1 - 0.15 * dip})`;
  cur.style.opacity = C(lt / 0.3);
  const r = cur.querySelector('.rip'); r.style.opacity = rip > 0 ? 1 - rip : 0; r.style.transform = `scale(${0.3 + 1.6 * rip})`;
}
window.seek = function (t) {
  for (let i = 0; i < SC.length; i++) {
    const el = SC[i], st = +el.dataset.st, dur = +el.dataset.dur, lt = t - st;
    const nx = SC[i + 1], tin = el.dataset.trans, TR = TRANS;
    const vis = lt >= 0 && (lt < dur + (nx && nx.dataset.trans !== 'cut' ? TR : 0) || !nx);
    el.style.visibility = vis ? 'visible' : 'hidden';
    if (!vis) continue;
    // camera: slow push-in
    el.querySelector('.cam').style.transform = `scale(${1 + 0.045 * C(lt / (dur + TR))})`;
    // transition into this scene
    let tf = '', op = 1;
    if (i > 0 && lt < TR) { const k = E(lt / TR);
      if (tin === 'push') tf = `translateY(${H * (1 - k)}px)`;
      else if (tin === 'zoom') { tf = `scale(${1.35 - 0.35 * k})`; op = C(lt / (TR * 0.6)); }
      else if (tin === 'wipe') tf = ''; }
    // transition out (next scene is arriving)
    if (nx && lt >= dur) { const k = E((lt - dur) / TR), nt = nx.dataset.trans;
      if (nt === 'push') tf = `translateY(${-H * 0.35 * k}px) scale(${1 - 0.08 * k})`;
      else if (nt === 'zoom') tf = `scale(${1 - 0.12 * k})`; op = nt === 'zoom' ? 1 - 0.6 * k : 1; }
    el.style.transform = tf; el.style.opacity = op; el.style.zIndex = i;
    el.querySelector('.grain').style.transform = `translate(${(Math.floor(t * 12) * 37) % 100}px, ${(Math.floor(t * 12) * 53) % 100}px)`;
    for (const e of el._els) anim(e, e.dataset.a, lt, +e.dataset.at);
    for (const f of el._fl) f.style.translate = `0 ${Math.sin(lt * 1.3) * 8}px`;
    if (el._cur) cursor(el._cur, el.querySelector('.cam'), lt);
  }
  // wipe overlay for scenes entering with trans=wipe
  const wipe = document.getElementById('wipe'); let wp = -1;
  for (const el of SC) if (el.dataset.trans === 'wipe' && Math.abs(t - +el.dataset.st) < 0.4) wp = (t - +el.dataset.st + 0.4) / 0.8;
  if (wp >= 0) { wipe.style.visibility = 'visible'; wipe.querySelectorAll('i').forEach((b, j) => { const k = C(wp * 1.1 - j * 0.06);
    const off = k < 0.5 ? 3000 * (1 - E(k * 2)) : -3000 * Math.pow((k - 0.5) * 2, 2.2); b.style.transform = `rotate(-32deg) translateY(${-off}px)`; }); }
  else wipe.style.visibility = 'hidden';
  // captions
  const cap = document.getElementById('cap'); let html = '';
  for (const c of CAPS) if (t >= c.s && t < c.e) { html = '<div>' + c.w.map(w => (t >= w[1] && t < w[2]) ? `<b>${w[0]}</b>` : w[0]).join(' ') + '</div>';
    const k = E((t - c.s) / 0.18); cap.style.transform = `translateY(${16 * (1 - k)}px)`; cap.style.opacity = k; }
  cap.innerHTML = html;
  document.getElementById('prog').style.width = (100 * C(t / TOTAL)) + '%';
};
"""


def grain_uri():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><filter id="n"><feTurbulence type="fractalNoise" '
           'baseFrequency=".85" numOctaves="3" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .5 0 0 0 0 .5 0 0 0 0 .5 0 0 0 .9 0"/></filter>'
           '<rect width="100%" height="100%" filter="url(#n)"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def captions(scenes_t):
    """scenes_t: [(st, vo_start, vo_len, text)] -> list of caption chunks with per-word timing."""
    caps = []
    for st, vs, vl, text in scenes_t:
        words = text.split()
        if not words:
            continue
        weights = [len(w) + 2 for w in words]
        tot = sum(weights)
        t0, timed = st + vs, []
        for w, wt in zip(words, weights):
            d = vl * wt / tot
            timed.append([esc(w), round(t0, 3), round(t0 + d, 3)]); t0 += d
        chunk = []
        for w in timed:
            if chunk and (len(chunk) >= 4 or sum(len(x[0]) + 1 for x in chunk) + len(w[0]) > 24):
                caps.append({"s": chunk[0][1], "e": w[1], "w": chunk}); chunk = []
            chunk.append(w)
        if chunk:
            caps.append({"s": chunk[0][1], "e": chunk[-1][2] + 0.25, "w": chunk})
    return caps


def plan(script, outdir):
    """Decide each scene's duration (from VO files when present) and VO placement."""
    vodir = Path(outdir) / "vo"
    rows, t = [], 0.0
    for i, s in enumerate(script["scenes"]):
        vo = vodir / f"{i + 1:02d}.mp3"
        lead = 0.25 if i > 0 else 0.15
        if vo.exists():
            vl = ffdur(vo)
            dur = max(float(s.get("min_dur", 2.0)), lead + vl + (1.4 if s["type"] == "end" else 0.35))
        else:
            dur, vl = float(s.get("dur") or 3.0), 0.0
        rows.append({"st": t, "dur": dur, "vo": str(vo) if vo.exists() else None, "lead": lead, "vl": vl})
        t += dur
    return rows, t


def build_page(script, rows, total):
    scenes, events, caps_in = [], [], []
    for i, (s, r) in enumerate(zip(script["scenes"], rows)):
        sc = Scene(i, s, r["dur"])
        inner = sc.build()
        trans = s.get("trans", "push" if i else "cut")
        bg = s.get("bg", "cream")
        scenes.append(f'<div class="scene bg-{bg}" data-st="{r["st"]:.3f}" data-dur="{r["dur"]:.3f}" data-trans="{trans}">'
                      f'<div class="cam"><div class="bg"></div><div class="grid"></div>{inner}</div><div class="grain"></div></div>')
        if i and trans in ("push", "zoom", "wipe"):
            events.append(("whoosh", r["st"] - 0.12, {"dur": 0.45}))
        events += [(k, r["st"] + at, kw) for k, at, kw in sc.ev]
        if s.get("vo") and s["type"] != "end" and r["vo"]:   # captions only when the line is actually spoken
            caps_in.append((r["st"], r["lead"], r["vl"], s["vo"]))
    css = (CSS.replace("SG500", font("space-grotesk", 500)).replace("SG700", font("space-grotesk", 700))
           .replace("IN400", font("inter", 400)).replace("IN500", font("inter", 500)).replace("IN600", font("inter", 600))
           .replace("DM500", font("dm-mono", 500)).replace("GRAIN", grain_uri()))
    js = f"const TRANS={TRANS}, H={H}, TOTAL={total:.3f}, CAPS={json.dumps(captions(caps_in))};\n" + JS
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'{"".join(scenes)}<div id="wipe"><i></i><i></i></div><div id="cap"></div><div id="prog"></div>'
            f'<script>{js}</script></body></html>')
    return page, events


def mix_audio(total, events, rows, style, out):
    import sys
    sys.path.insert(0, str(HERE))
    from render_reel import soundtrack, tone, env, bandpass, lowpass  # noqa
    base = out.with_suffix(".music.wav")
    ev = []
    for k, at, kw in events:
        if k == "pop":
            ev.append(("pluck", at, {"note": kw.get("note", 3) + 2}))
        elif k == "click":
            ev.append(("tick", at, {})); ev.append(("tick", at + 0.03, {}))
        else:
            ev.append((k, at, kw))
    soundtrack(total, ev, style, base)
    sr, music = wavfile.read(str(base)); base.unlink()
    music = music[:, 0].astype(np.float64)
    vo = np.zeros_like(music)
    for r in rows:
        if not r["vo"]:
            continue
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", r["vo"], "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
        a = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
        i = int((r["st"] + r["lead"]) * SR); j = min(len(vo), i + len(a))
        vo[i:j] += a[:j - i]
    if np.abs(vo).max() > 0:
        act = np.convolve((np.abs(vo) > 0.02).astype(float), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
        duck = 1 - 0.72 * np.clip(act * 3, 0, 1)
        vo = vo / np.abs(vo).max() * 0.95
        mix = music * 0.55 * duck + vo
    else:
        mix = music
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.9
    wavfile.write(str(out), SR, np.stack([mix, mix], 1).astype(np.float32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("outdir")
    ap.add_argument("--fps", type=int, default=30); ap.add_argument("--stills", action="store_true")
    a = ap.parse_args()
    script = json.loads(Path(a.script).read_text())
    assert script.get("version") == 2, "render_v2 needs a version 2 script"
    assert script["scenes"][-1]["type"] == "end", "last scene must be type end"
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    rows, total = plan(script, out)
    page, events = build_page(script, rows, total)
    (out / "timing.json").write_text(json.dumps({"total": round(total, 3), "scenes": [round(r["dur"], 3) for r in rows],
                                                 "vo": [bool(r["vo"]) for r in rows]}))
    (out / "reel.html").write_text(page)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.set_content(page); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(300)
        for i, r in enumerate(rows):
            pg.evaluate(f"seek({r['st'] + max(r['dur'] - 0.5, 0):.3f})")
            pg.screenshot(path=str(out / f"still-{i + 1:02d}.png"))
        pg.evaluate(f"seek({max(rows[0]['dur'] - 0.15, 0):.3f})")
        pg.screenshot(path=str(out / "cover.jpg"), type="jpeg", quality=90)
        if a.stills:
            br.close(); print(f"stills only: {total:.1f}s planned"); return
        nfr = int(math.ceil(total * a.fps)); silent = out / "_video.mp4"
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(a.fps), str(silent)],
                              stdin=subprocess.PIPE)
        for f in range(nfr):
            pg.evaluate(f"seek({f / a.fps:.4f})"); ff.stdin.write(pg.screenshot(type="jpeg", quality=94))
        ff.stdin.close(); ff.wait(); br.close()
    wav = out / "_audio.wav"; mix_audio(total, events, rows, script.get("music", "pulse"), wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9",
                    "-c:a", "aac", "-ar", "48000", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
    silent.unlink(); wav.unlink()
    print(f"rendered {out / 'reel.mp4'} ({total:.1f}s, {nfr} frames, VO scenes: {sum(1 for r in rows if r['vo'])}/{len(rows)})")


if __name__ == "__main__":
    main()
