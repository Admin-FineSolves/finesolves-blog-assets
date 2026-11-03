#!/usr/bin/env python3
"""Audit gate for a Fine Solves reel. Exit 0 = PASS. Writes REEL_DIR/audit.md.

Usage: python3 reels/audit_reel.py REEL_DIR [--prerender]
Needs REEL_DIR/script.json, meta.json, captions.json (and reel.mp4 unless --prerender).
meta.json     = {"brand":"finesolves|finehealth|finehr","topic":"...","primary_keyword":"...","angle":"..."}
captions.json = {"instagram":"...","linkedin":"...","youtube_title":"...","youtube_description":"...","alt":"..."}
claims.json   = optional [{"value":"27%","claim":"...","source":"...","url":"https://..."}]
"""
import json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANNED = ["revolutionary", "seamless", "synergy", "game-changing", "game changing", "cutting-edge", "cutting edge",
          "unlock", "transform", "delve", "landscape", "leverage", "harness the power", "paradigm shift", "next-gen",
          "fast-paced world", "empower"]
GENERIC_TAGS = {"#business", "#marketing", "#love", "#instagood", "#reels", "#viral", "#trending", "#explore",
                "#fyp", "#success", "#motivation", "#technology", "#tech", "#ai"}
BAD_NAMES = [r"\bFinesolves\b", r"\bFine solves\b", r"\bFINE SOLVES\b(?!\s*·)", r"\bFine Health\b", r"\bFinehealth\b",
             r"\bFine HR\b", r"\bFinehr\b", r"\bFineSolves\b"]
FINEHR_FEATURE = r"\bFineHR\b[^.?!\n]*\b(automat\w*|calculat\w*|track\w*|handl\w*|manag\w*|integrat\w*|send\w*|sync\w*|process\w*|generat\w*|run\w*|keeps?|covers?|includes?|supports?|payroll|attendance|leave|approv\w*|salar\w*|compliance|PF|ESI|TDS)\b"
MEDICAL = r"\b(diagnos\w*|cure\w*|clinical outcomes?|patient outcomes?|mortality|saves? lives|better care|treatment success)\b"
OK_NUMBER_CONTEXT = re.compile(r"^(0?\d|1\d|2[0-4]):\d\d|^(DAY|W|STEP)\s?\d|^\d{2}$")

fails, warns, passes = [], [], []


def check(ok, msg, critical=True):
    (passes if ok else (fails if critical else warns)).append(msg)


def onscreen_texts(script):
    out = []
    for s in script["scenes"]:
        for k in ("eyebrow", "text", "sub", "title", "result", "note", "line", "tag"):
            if s.get(k):
                out.append(s[k])
        for c in s.get("cards", []):
            out += [c["label"], c["text"]]
        out += s.get("items", []) + s.get("rows", [])
    return out


def main():
    d = Path(sys.argv[1]); pre = "--prerender" in sys.argv
    script = json.loads((d / "script.json").read_text())
    meta = json.loads((d / "meta.json").read_text())
    cap = json.loads((d / "captions.json").read_text())
    claims = json.loads((d / "claims.json").read_text()) if (d / "claims.json").exists() else []
    brand = meta.get("brand")
    check(brand in ("finesolves", "finehealth", "finehr"), f"brand is valid ({brand})")

    # ---- structure & timing
    sc = script["scenes"]
    total = sum(float(s["dur"]) for s in sc)
    check(sc[-1]["type"] == "end", "last scene is the end card")
    check(14 <= total <= 30, f"total length 14–30s ({total:.1f}s)")
    check(4 <= len(sc) <= 8, f"4–8 scenes ({len(sc)})")
    for i, s in enumerate(sc):
        n_items = len(s.get("cards", [])) + len(s.get("items", [])) + len(s.get("rows", []))
        need = 2.3 + 0.32 * max(n_items - 1, 0) + (0.8 if s["type"] == "counter" else 0)
        check(float(s["dur"]) >= need, f"scene {i+1} holds long enough to read ({s['dur']}s ≥ {need:.1f}s)")
        if s.get("text"):
            words = len(re.findall(r"\w[\w'’-]*", s["text"]))
            check(words <= 10, f"scene {i+1} headline ≤10 words ({words})")
            for ln in s["text"].split("\n"):
                check(len(ln) <= 26, f"scene {i+1} headline line ≤26 chars: “{ln}” ({len(ln)})")
        for c in s.get("cards", []):
            check(len(c["text"]) <= 40, f"scene {i+1} card text ≤40 chars: “{c['text']}”")
    end = sc[-1]
    if brand == "finehealth":
        check("FineHealth by Fine Solves" in end.get("line", ""), "FineHealth end card reads 'FineHealth by Fine Solves'")
    if brand == "finehr":
        check("FineHR by Fine Solves" in end.get("line", ""), "FineHR end card reads 'FineHR by Fine Solves'")

    # ---- copy rules (on-screen + captions)
    screen = "\n".join(onscreen_texts(script))
    captions_text = "\n".join(str(v) for v in cap.values())
    everything = screen + "\n" + captions_text
    low = everything.lower()
    hits = [w for w in BANNED if re.search(r"\b" + re.escape(w), low)]
    check(not hits, f"no banned words {hits or ''}")
    no_tags = re.sub(r"#\w+", "", everything)
    check(not re.search(r"\bsoftware\b", no_tags, re.I), "says 'products', not 'software' (hashtags excepted)")
    bad = [p for p in BAD_NAMES if re.search(p, everything)]
    check(not bad, f"brand names spelled Fine Solves / FineHealth / FineHR {bad or ''}")
    check("[CONFIRM]" not in everything and "CONFIRM" not in screen, "no [CONFIRM] items")
    check(not re.search(r"(₹|rs\.?\s?)\s?\d", low) and "pricing" not in low and "per month" not in low, "no pricing")
    check(not re.search(MEDICAL, everything, re.I), "no medical / patient-outcome claims")
    check(not re.search(r"testimonial|our client|clients like|trusted by|case study", low), "no invented clients or testimonials")
    if brand == "finehr" or "FineHR" in everything:
        m = re.search(FINEHR_FEATURE, everything)
        check(not m, f"FineHR makes no feature claims beyond 'one system' {('→ “'+m.group(0)+'”') if m else ''}")
    if "FineHealth" in everything:
        check(not re.search(r"FineHealth[^.\n]*WhatsApp|WhatsApp[^.\n]*FineHealth", everything),
              "no WhatsApp delivery claim for FineHealth (not shipped)")

    # ---- numbers must be illustrative-labelled or sourced
    claim_vals = {c["value"] for c in claims}
    for chunk in onscreen_texts(script) + re.split(r"(?<=[.!?\n])", captions_text):
        if OK_NUMBER_CONTEXT.match(chunk.strip()):
            continue
        nums = re.findall(r"\d[\d,]*(?:\.\d+)?\s?%?", re.sub(r"#\w+|finesolves\.com|\b(0?\d|1\d|2[0-4]):\d\d\b|\b0[1-9]\b", "", chunk))
        for n in nums:
            n = n.strip()
            if n in {"1", "2", "3", "4", "5", "6"} and "%" not in n:   # small counts ("three", "6 people") inside illustrative maths
                continue
            ok = n in claim_vals or any(n in v for v in claim_vals) or "illustrative" in everything.lower()
            check(ok, f"number “{n}” is sourced in claims.json or labelled illustrative")
    for c in claims:
        check(c.get("url", "").startswith("http"), f"claim {c.get('value')} has a source URL")
    if any(s["type"] == "counter" for s in sc) and not claims:
        check(any("ILLUSTRATIVE" in (s.get("note") or "") for s in sc if s["type"] == "counter"),
              "counter scene is labelled ILLUSTRATIVE")

    # ---- captions
    ig, li = cap.get("instagram", ""), cap.get("linkedin", "")
    kw = meta.get("primary_keyword", "").lower()
    for name, c in (("instagram", ig), ("linkedin", li)):
        first = c.strip().split("\n")[0].lower()
        check(bool(kw) and kw in first, f"{name}: first line contains the keyword “{kw}”")
        check("?" in c, f"{name}: asks the reader one question")
        check("finesolves.com" in c, f"{name}: has the finesolves.com CTA")
        tags = re.findall(r"#\w+", c)
        check(3 <= len(tags) <= 6, f"{name}: 3–6 hashtags ({len(tags)})")
        gen = [t for t in tags if t.lower() in GENERIC_TAGS]
        check(not gen, f"{name}: no generic hashtags {gen or ''}")
    check(len(ig) <= 2200, f"instagram ≤2,200 chars ({len(ig)})")
    check(len(li) <= 2800, f"linkedin ≤2,800 chars ({len(li)})")
    check(not re.search(r"[()\[\]{}]", li), "linkedin: no brackets or parentheses")
    want_cta = "Book a demo" if brand == "finehealth" else "Talk to us"
    check(want_cta in ig and want_cta in li, f"CTA is “{want_cta} → finesolves.com”")
    yt = cap.get("youtube_title", "")
    check(10 <= len(yt) <= 100 and "#Shorts" in yt, f"youtube title ≤100 chars with #Shorts ({len(yt)})")
    check(kw.split()[0] in yt.lower() if kw else False, "youtube title carries the keyword")
    check(0 < len(cap.get("youtube_description", "")) <= 4800 and "finesolves.com" in cap.get("youtube_description", ""),
          "youtube description present with finesolves.com")
    check(not re.search(r"[<>]", yt + cap.get("youtube_description", "")), "youtube text has no < or >")
    check(20 <= len(cap.get("alt", "")) <= 300, "alt text is one descriptive sentence")

    # ---- rotation & repetition (reels/log.md: | date | brand | topic | keyword | ... |)
    log = (HERE / "log.md").read_text() if (HERE / "log.md").exists() else ""
    rows = [r for r in log.splitlines() if r.startswith("| 20")]
    if rows:
        last_brand = rows[-1].split("|")[2].strip()
        check(last_brand != brand, f"brand differs from the previous reel ({last_brand})")
        recent_kw = [r.split("|")[4].strip().lower() for r in rows[-21:]]
        recent_topic = [r.split("|")[3].strip().lower() for r in rows]
        check(kw not in recent_kw, "primary keyword not used in the last 21 reels", critical=False)
        check(meta.get("topic", "").lower() not in recent_topic, "topic not used before")

    # ---- the video itself
    if not pre:
        mp4 = d / "reel.mp4"
        check(mp4.exists(), "reel.mp4 exists")
        if mp4.exists():
            pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                            str(mp4)], capture_output=True, text=True).stdout)
            v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
            check(v["width"] == 1080 and v["height"] == 1920, "video is 1080×1920")
            check(v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p", "video is H.264 yuv420p")
            check(v["r_frame_rate"] in ("30/1", "24/1"), f"frame rate 24/30 ({v['r_frame_rate']})")
            check(any(s["codec_type"] == "audio" for s in pr["streams"]), "has an audio track")
            dur = float(pr["format"]["duration"])
            check(abs(dur - total) < 0.5, f"duration matches script ({dur:.1f}s)")
            check(mp4.stat().st_size < 20 * 1024 * 1024, "file under 20 MB (CDN limit)")
        check((d / "cover.jpg").exists(), "cover.jpg exists")
        check(len(list(d.glob("still-*.png"))) == len(sc), "one review still per scene")

    score = round(100 * len(passes) / max(1, len(passes) + len(fails) + len(warns)))
    status = "PASS" if not fails else "FAIL"
    md = [f"# Reel audit: {status} ({score}/100)", ""]
    md += ["## Critical failures"] + [f"- ❌ {f}" for f in fails] if fails else []
    md += ["## Warnings"] + [f"- ⚠️ {w}" for w in warns] if warns else []
    md += ["## Passed"] + [f"- ✅ {p}" for p in passes]
    (d / "audit.md").write_text("\n".join(md) + "\n")
    print(f"{status} {score}/100 — {len(fails)} critical, {len(warns)} warnings")
    for f in fails:
        print("  ❌", f)
    for w in warns:
        print("  ⚠️", w)
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
