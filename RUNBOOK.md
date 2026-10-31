# Fine Solves daily blog — runbook

Each daily run researches one topic, writes one AEO/SEO-optimised post, renders two branded creatives, hosts the creatives in the public GitHub repo Admin-FineSolves/finesolves-blog-assets, and publishes the post to the Fine Solves Blogger blog by email (Blogger "Posting using email", sent through Zapier Gmail).

The scheduled task prompt supplies `BLOGGER_POST_EMAIL` (secret — never write it into any file, commit or post) and `BLOG_URL`.
creatives.py, this runbook and every past post live in the repo.

## 0. Setup (every run — fresh container)
```bash
# attach the repo first: add_repo(owner="Admin-FineSolves", repo="finesolves-blog-assets", access="push")
git clone --depth 1 https://github.com/Admin-FineSolves/finesolves-blog-assets ~/finesolves-blog-assets
cd ~/finesolves-blog-assets
npm i --silent @fontsource/space-grotesk @fontsource/inter @fontsource/dm-mono
DATE=$(TZ=Asia/Kolkata date +%F); mkdir -p posts/$DATE
```
Topic history: WebFetch `BLOG_URL/feeds/posts/summary?alt=rss` for live titles.

## 1. Pick today's topic
Audience: founders, CXOs, ops and IT heads at Indian SMB / mid-market and enterprise firms (manufacturing, logistics, supply chain, healthcare, retail, BFSI).

Rotate pillars so no pillar repeats on consecutive days (check the feed):
1. **AI news & current affairs by industry** — a development from the last 7 days and what it means for operators.
2. **AI in supply chain, manufacturing & logistics** — forecasting, inventory, procurement, maintenance, scheduling.
3. **Custom software & build-vs-buy** — how to scope, cost, integrate, avoid tool sprawl, MVP-in-weeks.
4. **AI in healthcare operations / FineHealth** — HMS, hospital billing, clinic ops, ABDM, WhatsApp reports. Mention FineHealth by Fine Solves naturally, no pricing.
5. **Practical AI playbooks** — agents, LLM integration, data readiness, governance, ROI measurement.

Research: run 4–8 WebSearch queries (send several in one turn; "standard" mode first). Prefer last-30-day news and primary sources (Gartner, McKinsey, Deloitte, NASSCOM, EY, MeitY, company announcements, Indian business press). Pick a topic that (a) has a fresh, citable hook, (b) is not already on the blog (no same primary keyword in the feed's last 60 days), (c) answers a question a buyer would actually type into Google or ask ChatGPT.

## 2. Write the post (`posts/$DATE/post.html`)
Length 1,200–1,700 words. HTML body only (no `<html>`, `<head>`, `<style>`, `<script>`). Allowed tags: p, h2, h3, ul, ol, li, strong, em, a, img, table/tr/th/td, blockquote.

Structure (AEO + SEO):
1. `<p><img src="{{HERO_URL}}" alt="<keyword-rich alt> – Fine Solves" width="1200" height="630" style="width:100%;height:auto" /></p>`
2. **Answer-first paragraph** in `<strong>`: 40–60 words that directly answer the title's question, with the primary keyword and one cited number. This is the snippet AI engines quote.
3. One context paragraph (why now, the hook).
4. `<h2>TL;DR</h2>` — 4–5 bullets, each a standalone fact with a number.
5. 4–6 `<h2>` sections phrased as the questions people ask ("What is…", "Why…", "How do you…", "Is X worth it…"). First sentence of each section answers the question in one line, then expands.
6. Insert `<p><img src="{{INFO_URL}}" alt="Infographic: …" width="1080" height="1350" style="width:100%;max-width:640px;height:auto;display:block;margin:0 auto" /></p>` after the 2nd or 3rd section.
7. A practical section (numbered steps / checklist / comparison table).
8. "What this means for Indian businesses" + soft CTA: link `https://finesolves.com` with anchor like "Talk to Fine Solves". One CTA only.
9. `<h2>Frequently asked questions</h2>` — 4–5 `<h3>` questions, 40–70-word answers, self-contained.
10. `<h2>Sources</h2>` — linked list of every source used (title — publisher).
11. Footer: `<p><em>Published by Fine Solves — an AI software development company in Ahmedabad building custom software and AI systems for Indian businesses. <a href="https://finesolves.com">finesolves.com</a></em></p>`
12. Last line exactly `#end` (stops Blogger posting anything after it).

Title (email subject): ≤ 60 characters, primary keyword near the front, specific number or year where natural. No clickbait.

Rules:
- Every statistic must come from a page you actually retrieved today; cite it in-line ("according to Deloitte's 2026…") and in Sources. If unsure, drop it. Never invent clients, case studies, results or quotes.
- Paraphrase; quotes under 15 words and at most one per source.
- Voice (Fine Solves brand): direct, practical, a little dry; short declaratives; numbers over adjectives. Avoid: revolutionary, seamless, synergy, game-changing, cutting-edge, unlock, transform, delve, landscape, in today's fast-paced world.
- Use SEO vocabulary where it fits naturally: AI software development company India, custom software development company Ahmedabad, hospital management system India, AI in supply chain India, etc.
- Indian context: ₹ with Indian grouping (₹33,000 crore), Indian examples where possible.

## 3. Creatives (`posts/$DATE/spec.json` → images)
Write spec.json:
```json
{"eyebrow":"<pillar label, ≤4 words>","title":"<hero headline ≤10 words>","highlight":"<one number or phrase from title>",
 "takeaways_title":"<≤6 words>","takeaways":["<3–5 items, each ≤14 words, each a fact from the post>"],
 "source_note":"Source: <main source, year>"}
```
Run `python3 creatives.py posts/$DATE/spec.json posts/$DATE`, then convert to JPEG:
```bash
python3 -c "from PIL import Image;import sys;d=sys.argv[1]
[Image.open(f'{d}/{n}.png').convert('RGB').save(f'{d}/{n}.jpg',quality=82,optimize=True,progressive=True) for n in ('hero','infographic')]" posts/$DATE
rm posts/$DATE/*.png
```
Open both JPEGs with Read and check: no text overflow or overlap, headline fits, numbers match the post. Fix spec and re-render if not.

## 4. Host images (GitHub: Admin-FineSolves/finesolves-blog-assets, public)
```bash
cd ~/finesolves-blog-assets
git add posts/$DATE && git -c user.name="Fine Solves Blog Bot" -c user.email="admin@finesolves.com" commit -qm "Post $DATE: <title>" && git push origin main
SHA=$(git rev-parse HEAD)
```
Image URLs (pinned to the commit so they never change):
`https://raw.githubusercontent.com/Admin-FineSolves/finesolves-blog-assets/$SHA/posts/$DATE/hero.jpg` (same for infographic.jpg).
Check with `curl -s -o /dev/null -w "%{http_code} %{content_type}" <url>` → must be `200 image/jpeg`. Replace `{{HERO_URL}}` / `{{INFO_URL}}` in post.html, commit and push again.

## 5. Publish
Zapier Gmail action `message` (selected_api `GoogleMailV2CLIAPI`): `to` = BLOGGER_POST_EMAIL, `subject` = title, `body_type` = html, `body` = full post.html contents. No signature, no attachments.
Wait ~2 minutes, then WebFetch `BLOG_URL/feeds/posts/summary?alt=rss` and confirm the title appears. If it does not after 10 minutes, report it — do NOT resend (avoids duplicate posts).

## 6. Report
Final reply: one line — title, live URL, pillar.

## Failure handling
- Research thin or no fresh hook → use an evergreen pillar 3 or 5 topic instead; never publish unsourced numbers.
- Zapier/Gmail auth error → stop, don't publish, report "Reconnect Gmail in Zapier".
- Git push fails or image URL doesn't return 200 image/jpeg → stop before publishing (post would have broken images) and report.
