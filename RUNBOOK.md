# Fine Solves blog — runbook (2 posts a day)

Two scheduled runs publish to the Fine Solves blog (https://finesolves.com/blog — posts stored in Sanity) every day:
- **Morning slot (05:39 IST)** — news-led: something that happened in the last 7 days, with data.
- **Evening slot (18:47 IST)** — deep-dive / evergreen: a data-heavy explainer, benchmark, or playbook.

Each run: research → write a data-rich post → charts, table, hero, infographic → **SEO + GEO + data audit (must PASS)** → host images on GitHub → publish to Sanity (`publish_sanity.py`) → verify live.

The task prompt supplies `SLOT` (morning | evening) and `SANITY_WRITE_TOKEN` (secret — never write it into any file, commit, post or reply). Posts live in Sanity project `hf7ugumv`, dataset `production`; humans edit them at https://finesolves.sanity.studio. (Blogger / finesolves.blogspot.com is retired — don't publish there.)

## 0. Setup (fresh container every run)
```bash
# attach the repo first: add_repo(owner="Admin-FineSolves", repo="finesolves-blog-assets", access="push")
git clone --depth 1 https://github.com/Admin-FineSolves/finesolves-blog-assets ~/finesolves-blog-assets
cd ~/finesolves-blog-assets
npm i --silent @fontsource/space-grotesk @fontsource/inter @fontsource/dm-mono
DATE=$(TZ=Asia/Kolkata date +%F); POST=posts/$DATE-$SLOT; mkdir -p $POST
```
Topic history (last 25 posts — titles, dates, keywords):
```bash
curl -s --get "https://hf7ugumv.api.sanity.io/v2025-02-19/data/query/production" \
  --data-urlencode 'query=*[_type=="post"]|order(publishedAt desc)[0...25]{title,publishedAt,tags}'
```
Also `ls posts/` in the repo.

## 1. Pick the topic
Audience: founders, CXOs, ops and IT heads at Indian SMB / mid-market and enterprise firms (manufacturing, logistics, supply chain, healthcare, retail, BFSI).

Pillars:
1. **AI news & current affairs by industry** — what happened this week and what it means for operators. *(morning)*
2. **AI in supply chain, manufacturing & logistics** — forecasting, inventory, procurement, maintenance, scheduling. *(either)*
3. **Custom software & build-vs-buy** — scoping, costing, integration, tool sprawl, MVP-in-weeks. *(evening)*
4. **AI in healthcare operations / FineHealth** — HMS, hospital billing, clinic ops, ABDM, WhatsApp reports; mention FineHealth by Fine Solves naturally, no pricing. *(either)*
5. **Practical AI playbooks & benchmarks** — agents, LLM integration, data readiness, governance, ROI, cost benchmarks. *(evening)*

Rules: the two posts of a day must be different pillars; don't repeat the pillar of the previous post; no primary keyword reused within 60 days. Pick a topic where you can find **at least 15 hard numbers from at least 4 independent, credible sources** — if you can't, pick another topic.

## 2. Research (data first)
- 8–15 WebSearch queries (several per turn; "standard" first, "extended" for niche or very recent data), then WebFetch the 4–8 best pages to read the actual figures. Prefer primary sources: Gartner, McKinsey, Deloitte, BCG, EY, PwC, NASSCOM, IBEF, MeitY, RBI, NITI Aayog, government data, company filings, peer-reviewed research, reputable Indian business press (ET, Mint, Business Standard, Moneycontrol).
- Record every number you will use in `$POST/claims.json`:
  `[{"value":"27%","claim":"...","source":"Freshworks Global Cost of Complexity Report 2026","url":"https://..."}]`
  `value` must be written exactly as it will appear in the text (e.g. `27%`, `₹33,000 crore`, `$4.2 billion`, `3.5x`). Only numbers you saw on a fetched page. Never estimate, round up, or carry numbers from memory.
- Pick a primary keyword (what a buyer would type into Google or ask ChatGPT) and 2–3 secondary keywords. Write `$POST/meta.json`:
  `{"title":"…","primary_keyword":"…","secondary_keywords":["…","…"],"slot":"morning|evening"}`

## 3. Write `$POST/post.html` (data-rich, AEO/GEO + SEO)
1,400–2,400 words. HTML body only. Allowed tags: p, h2, h3, ul, ol, li, strong, em, a, img, table, thead, tbody, tr, th, td, blockquote.

Structure:
1. Hero: `<p><img src="{{HERO_URL}}" alt="<keyword-rich description> – Fine Solves" width="1200" height="630" style="width:100%;height:auto" /></p>`
2. **Answer-first paragraph** wrapped in `<p><strong>…</strong></p>`: 40–75 words, contains the primary keyword and one cited number. This is the passage AI engines quote.
3. One context paragraph: why this matters now.
4. `<h2>TL;DR</h2>` + 4–6 `<li>` bullets — **every bullet contains a number**.
5. 6–9 `<h2>` sections; at least 4 phrased as questions people ask (What / Why / How / Is / Should…?). The **first sentence under each question H2 answers it in ≤35 words**, then expand with data.
6. **At least 2 charts** (`{{CHART_1_URL}}`, `{{CHART_2_URL}}`…) placed next to the paragraph they support:
   `<p><img src="{{CHART_1_URL}}" alt="Chart: <what it shows, with the key number>" width="1200" height="750" style="width:100%;height:auto" /></p>`
7. **At least 1 data table** with a header row and ≥3 data rows (comparison, benchmark, cost breakdown, India vs global, before/after). Use:
   `<table style="width:100%;border-collapse:collapse"><thead><tr><th style="text-align:left;border-bottom:2px solid #092040;padding:8px">…</th>…</tr></thead><tbody><tr><td style="border-bottom:1px solid #E1E4E8;padding:8px">…</td>…</tr></tbody></table>` and add a one-line source caption under it: `<p><em>Source: …</em></p>`. Every chart's numbers must also appear in a table or in the text (accessibility).
8. Infographic `{{INFO_URL}}` (720px wide display) after the 2nd or 3rd section.
9. A practical section: numbered steps, checklist, or decision framework.
10. "What this means for Indian businesses" + one soft CTA: `<a href="https://finesolves.com">Talk to Fine Solves</a>`.
11. `<h2>Frequently asked questions</h2>` — 4–6 `<h3>` questions with 30–90-word self-contained answers.
12. `<h2>Sources</h2>` — `<ul>` of every source in claims.json (linked, title — publisher, year).
13. Footer: `<p><em>Last updated: DD Month YYYY. Published by Fine Solves — an AI software development company in Ahmedabad building custom software and AI systems for Indian businesses. <a href="https://finesolves.com">finesolves.com</a></em></p>`
14. Last line exactly `#end`.

Title: 30–60 characters, primary keyword near the front, a number or year where natural. Primary keyword also in the first 100 words and in at least one H2.

Writing rules:
- ≥15 quantified facts, each attributed in-line ("according to NASSCOM's 2026 report…", "Deloitte found…"). Use ≥6 attribution phrases.
- Paraphrase; any quote under 15 words, max one per source.
- Brand voice: direct, practical, a little dry; short declaratives; numbers over adjectives. Banned: revolutionary, seamless, synergy, game-changing, cutting-edge, unlock, transformative, delve, landscape, leverage, harness the power, paradigm shift, next-gen, in today's fast-paced world.
- Never invent clients, case studies, results or quotes. Fine Solves' own claims stay qualitative ("from the way we build…").
- Indian context: ₹ with Indian grouping (₹33,000 crore), Indian examples first.
- Paragraphs ≤110 words.

## 4. Visuals
**Charts** — write `$POST/charts.json` (2–4 charts; types `bar` (rankings/shares), `column` (comparisons, max 2 series), `line` (change over time); see header of charts.py). Titles state the finding in ≤8 words; subtitle = what/who/when; source line on every chart. Max 2 series (navy + teal), one axis. Run `python3 charts.py $POST/charts.json $POST`.
**Hero + infographic** — write `$POST/spec.json` (see creatives.py) and run `python3 creatives.py $POST/spec.json $POST`.
Convert all PNGs to JPEG:
```bash
python3 -c "import sys,glob;from PIL import Image
[Image.open(f).convert('RGB').save(f[:-4]+'.jpg',quality=82,optimize=True,progressive=True) for f in glob.glob(sys.argv[1]+'/*.png')]" $POST && rm $POST/*.png
```
Open **every** JPEG with Read and check: no overlapping or clipped text, labels readable, numbers match claims.json. Fix and re-render if not.

## 5. Audit gate (must PASS before publishing)
```bash
python3 audit.py $POST      # writes $POST/audit.md; exit 0 = PASS
```
The audit checks SEO (title, keyword placement, length, headings, alt text, links), GEO (answer-first block, TL;DR with numbers, question H2s answered in the first sentence, FAQ shape, attribution density, entity definition, freshness date, sources, banned words) and DATA (table, ≥2 charts, infographic, ≥15 stats, every stat traced to claims.json, every claim source linked).
Run `python3 audit.py $POST --prehost` before hosting (image placeholders allowed) and fix until it PASSES; after the URLs are filled in step 6 run `python3 audit.py $POST` — the **final** run must PASS with zero critical failures.
Then do a manual GEO/SEO read-through and fix anything found:
- Could an AI answer engine lift the answer-first paragraph and each FAQ answer verbatim and be correct?
- Does every number in the text match claims.json exactly, and does each claim say what the source says (re-open the source if unsure)?
- Is the post genuinely useful to an Indian ops/IT leader, not generic?
Up to 3 fix-and-re-audit rounds. If it still fails, **do not publish** — report the failing checks.

## 6. Host images (GitHub)
```bash
git add $POST && git -c user.name="Fine Solves Blog Bot" -c user.email="admin@finesolves.com" commit -qm "Post $DATE $SLOT: <title>" && git push origin main
SHA=$(git rev-parse HEAD); BASE=https://raw.githubusercontent.com/Admin-FineSolves/finesolves-blog-assets/$SHA/$POST
```
Replace every `{{HERO_URL}}`, `{{INFO_URL}}`, `{{CHART_n_URL}}` with `$BASE/<file>.jpg`. Check each URL: `curl -s -o /dev/null -w "%{http_code} %{content_type}" URL` → `200 image/jpeg`. Re-run `python3 audit.py $POST` (must PASS), commit and push.

## 7. Publish
```bash
SANITY_WRITE_TOKEN='<token from the task prompt>' python3 publish_sanity.py $POST
```
It strips the `#end` marker, builds the slug from the title (unique — it adds `-2` if another post has it), writes the post as document `post-$DATE-$SLOT` with `createOrReplace` (re-running updates the same post, never duplicates), reads it back and prints the live URL. Exit 0 = published. Then commit and push `$POST/sanity-mutation.json` (no secrets in it).
Within a few minutes, WebFetch `https://finesolves.com/blog` and confirm the new title is listed (the page reads Sanity live). The post's prerendered page and the sitemap are rebuilt automatically within ~30 minutes (Railway cron) — don't wait for that.

## 8. Report
One line: slot, title, live URL, pillar, audit score.

## Failure handling
- Not enough hard data for a topic → change topic (never pad with unsourced numbers).
- Audit still failing after 3 rounds → don't publish; report the failing checks.
- `publish_sanity.py` fails with HTTP 401/403 or "SANITY_WRITE_TOKEN is not set" → report "Sanity write token missing or expired — create an Editor token at sanity.io/manage/project/hf7ugumv/api and update SANITY_WRITE_TOKEN in the task prompt". Any other failure → report its output.
- Git push fails or any image URL isn't 200 image/jpeg → don't publish; report.
