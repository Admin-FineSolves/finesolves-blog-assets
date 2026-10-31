#!/usr/bin/env python3
"""Fine Solves pre-publish SEO + GEO + data audit.

Usage: python3 audit.py posts/DATE-SLOT [--prehost]   (reads post.html, meta.json, claims.json; writes audit.md)
Exit 0 = PASS (publish allowed). Exit 1 = FAIL (fix and re-run; never publish a failing post).

meta.json   = {"title": "...", "primary_keyword": "...", "secondary_keywords": ["...", "..."], "slot": "morning|evening"}
claims.json = [{"value": "27%", "claim": "share of Indian mid-market AI budget lost to complexity",
                "source": "Freshworks Global Cost of Complexity Report 2026", "url": "https://..."}]
Every percentage, ₹/$ amount, and crore/lakh/million/billion figure in the post must appear in claims.json
with a URL that is also listed in the post's Sources section.
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

BANNED = ["revolutionary", "seamless", "synergy", "game-changing", "game changer", "cutting-edge", "unlock",
          "transformative", "delve", "in today's fast-paced", "ever-evolving", "landscape", "leverage",
          "harness the power", "paradigm shift", "next-gen"]
QWORDS = ("what", "why", "how", "is", "are", "can", "should", "when", "which", "does", "do", "who", "where")

class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.stack = []; s.blocks = []; s.imgs = []; s.links = []; s.tables = []; s.cur = None
    def handle_starttag(s, t, a):
        a = dict(a)
        if t == "img": s.imgs.append(a)
        if t == "a": s.links.append(a.get("href", ""))
        if t == "table": s.tables.append({"rows": 0, "th": 0})
        if t == "tr" and s.tables: s.tables[-1]["rows"] += 1
        if t == "th" and s.tables: s.tables[-1]["th"] += 1
        if t in ("p", "h2", "h3", "li", "td", "th"):
            s.cur = {"tag": t, "text": "", "strong": False}; s.blocks.append(s.cur)
        if t == "strong" and s.cur and s.cur["tag"] == "p" and not s.cur["text"].strip(): s.cur["strong"] = True
        s.stack.append(t)
    def handle_endtag(s, t):
        if t in ("p", "h2", "h3", "li", "td", "th"): s.cur = None
    def handle_data(s, d):
        if s.cur is not None: s.cur["text"] += d

def words(t): return re.findall(r"[A-Za-z0-9₹$%][\w'’%.,₹$-]*", t)

def main():
    prehost = "--prehost" in sys.argv
    d = Path(sys.argv[1]); html = (d / "post.html").read_text()
    meta = json.loads((d / "meta.json").read_text())
    claims = json.loads((d / "claims.json").read_text()) if (d / "claims.json").exists() else []
    p = P(); p.feed(html)
    blocks = [b for b in p.blocks if b["text"].strip()]
    text = " ".join(b["text"] for b in blocks)
    low = text.lower()
    title, kw = meta["title"], meta["primary_keyword"].lower()
    res = []   # (category, check, ok, critical, detail)
    def ck(cat, name, ok, crit, detail=""): res.append((cat, name, bool(ok), crit, detail))

    # ---------- SEO ----------
    ck("SEO", "Title 30–60 characters", 30 <= len(title) <= 60, True, f"{len(title)} chars")
    kw_words = [w for w in re.findall(r"\w+", kw) if len(w) > 2]
    ck("SEO", "Primary keyword in title", all(w in title.lower() for w in kw_words), True, kw)
    first100 = " ".join(words(text)[:100]).lower()
    ck("SEO", "Primary keyword in first 100 words", all(w in first100 for w in kw_words), True)
    h2 = [b["text"].strip() for b in blocks if b["tag"] == "h2"]
    ck("SEO", "Primary keyword (or its words) in an H2", any(sum(w in h.lower() for w in kw_words) >= max(1, len(kw_words) - 1) for h in h2), False)
    wc = len(words(text))
    ck("SEO", "Word count 1,400–2,400", 1400 <= wc <= 2400, True, f"{wc} words")
    ck("SEO", "At least 6 H2 sections", len(h2) >= 6, True, f"{len(h2)} H2")
    ck("SEO", "Every image has descriptive alt (≥20 chars)", p.imgs and all(len(i.get("alt", "")) >= 20 for i in p.imgs), True, f"{len(p.imgs)} images")
    ck("SEO", "Internal link to finesolves.com", any("finesolves.com" in l for l in p.links), True)
    ext = {re.sub(r"^https?://(www\.)?", "", l).split("/")[0] for l in p.links if l.startswith("http") and "finesolves" not in l and "githubusercontent" not in l}
    ck("SEO", "≥5 outbound source links across ≥4 domains", len([l for l in p.links if l.startswith("http") and "finesolves" not in l]) >= 5 and len(ext) >= 4, True, f"{len(ext)} domains")
    long_p = [b for b in blocks if b["tag"] == "p" and len(words(b["text"])) > 110]
    ck("SEO", "No paragraph over 110 words", not long_p, False, f"{len(long_p)} long")
    sec = [k.lower() for k in meta.get("secondary_keywords", [])]
    ck("SEO", "≥2 secondary keywords used", sum(k in low for k in sec) >= min(2, len(sec)), False)
    ck("SEO", "No placeholders / script / style tags", not re.search(r"<script|<style|TODO|lorem" + ("" if prehost else r"|\{\{"), html, re.I), True)
    ck("SEO", "Ends with #end", html.strip().endswith("#end"), True)

    # ---------- GEO (AI-answer readiness) ----------
    first_p = next((b for b in blocks if b["tag"] == "p"), None)
    fw = len(words(first_p["text"])) if first_p else 0
    ck("GEO", "Answer-first bold paragraph, 40–75 words, with a number",
       first_p and first_p["strong"] and 40 <= fw <= 75 and re.search(r"\d", first_p["text"]), True, f"{fw} words")
    tldr_i = next((i for i, b in enumerate(blocks) if b["tag"] == "h2" and "tl;dr" in b["text"].lower()), None)
    tl = []
    if tldr_i is not None:
        for b in blocks[tldr_i + 1:]:
            if b["tag"] != "li": break
            tl.append(b)
    ck("GEO", "TL;DR with 4–6 bullets, each with a number", 4 <= len(tl) <= 6 and all(re.search(r"\d", b["text"]) for b in tl), True, f"{len(tl)} bullets")
    qh = [h for h in h2 if h.endswith("?") or h.lower().split(" ")[0] in QWORDS]
    ck("GEO", "≥4 H2s phrased as questions", len(qh) >= 4, True, f"{len(qh)}")
    # first sentence after each question H2 is short and extractable
    bad = []
    for i, b in enumerate(blocks):
        if b["tag"] == "h2" and b["text"].strip() in qh:
            nxt = next((x for x in blocks[i + 1:] if x["tag"] in ("p", "li")), None)
            if nxt:
                s1 = re.split(r"(?<=[.!?])\s", nxt["text"].strip())[0]
                if len(words(s1)) > 35: bad.append(b["text"][:40])
    ck("GEO", "Each question H2 answered in its first sentence (≤35 words)", not bad, True, "; ".join(bad))
    faq_i = next((i for i, b in enumerate(blocks) if b["tag"] == "h2" and "frequently asked" in b["text"].lower()), None)
    faq_q = []; faq_bad = 0
    if faq_i is not None:
        for j, b in enumerate(blocks[faq_i + 1:], faq_i + 1):
            if b["tag"] == "h2": break
            if b["tag"] == "h3":
                faq_q.append(b)
                ans = next((x for x in blocks[j + 1:] if x["tag"] == "p"), None)
                if not ans or not 30 <= len(words(ans["text"])) <= 90: faq_bad += 1
    ck("GEO", "FAQ: 4–6 questions, answers 30–90 words", 4 <= len(faq_q) <= 6 and faq_bad == 0, True, f"{len(faq_q)} Qs, {faq_bad} off-length")
    attrib = len(re.findall(r"\baccording to\b|\b(found|reports?|reported|estimates?|survey(ed)?|study|data from|shows?)\b", low))
    ck("GEO", "≥6 attribution phrases near facts", attrib >= 6, True, f"{attrib}")
    ck("GEO", "Entity definition: 'Fine Solves' named ≥2× and defined once", low.count("fine solves") >= 2 and re.search(r"fine solves[^.]{0,20}(is|—|-|,)\s+(an|a)\s", low), True)
    ck("GEO", "Freshness: 'Last updated' date line", re.search(r"last updated:?\s*\d{1,2}\s\w+\s20\d\d", low), True)
    ck("GEO", "Sources section present", any(h.lower().startswith("sources") for h in h2), True)
    ban = [w for w in BANNED if w in low]
    ck("GEO", "No banned filler words", not ban, True, ", ".join(ban))

    # ---------- DATA RICHNESS ----------
    good_tables = [t for t in p.tables if t["th"] >= 2 and t["rows"] >= 4]
    ck("DATA", "≥1 HTML table (header row + ≥3 data rows)", good_tables, True, f"{len(p.tables)} tables")
    charts = [i for i in p.imgs if re.search(r"chart-\d|CHART_\d", i.get("src", ""))]
    ck("DATA", "≥2 charts embedded", len(charts) >= 2, True, f"{len(charts)}")
    ck("DATA", "Infographic embedded", any(re.search("infographic|INFO_URL", i.get("src", "")) for i in p.imgs), True)
    stat_re = r"(?:₹|\$|US\$)\s?\d[\d,.]*\s?(?:lakh crore|crore|lakh|million|billion|trillion|bn|mn|k)?|\d[\d,.]*\s?%|\d[\d,.]*\s?(?:lakh crore|crore|lakh|million|billion|trillion)\b|\d+(?:\.\d+)?x\b"
    stats = re.findall(stat_re, text, re.I)
    ck("DATA", "≥15 quantified facts in text", len(stats) >= 15, True, f"{len(stats)}")
    # fact gate: every stat must be in claims.json with a URL present in the post
    norm = lambda s: re.sub(r"[\s,]", "", s.lower()).replace("us$", "$")
    claim_vals = {norm(c["value"]) for c in claims}
    claim_urls = {c.get("url", "") for c in claims}
    missing = sorted({s for s in stats if norm(s) not in claim_vals})
    ck("DATA", "Every statistic traced to claims.json", not missing, True, ", ".join(missing[:12]))
    unlinked = [u for u in claim_urls if u and u not in html]
    ck("DATA", "Every claim source is linked in the post", claims and not unlinked, True, ", ".join(unlinked[:5]))

    passed = sum(r[2] for r in res); crit_fail = [r for r in res if r[3] and not r[2]]
    score = round(100 * passed / len(res))
    ok = not crit_fail and score >= 90
    lines = [f"# Audit — {title}", "", f"**Result: {'PASS' if ok else 'FAIL'}** · score {score}/100 · {len(crit_fail)} critical failures", "",
             "| Area | Check | Result | Detail |", "| --- | --- | --- | --- |"]
    for cat, name, good, crit, det in res:
        lines.append(f"| {cat} | {name}{' *' if crit else ''} | {'✅' if good else ('❌' if crit else '⚠️')} | {det} |")
    lines += ["", "\\* critical — must pass. Publish only when Result is PASS."]
    (d / "audit.md").write_text("\n".join(lines))
    print("\n".join(lines))
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
