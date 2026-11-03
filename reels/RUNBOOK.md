# Fine Solves reels: runbook (1 reel a day, posted to Instagram, YouTube Shorts and LinkedIn)

One scheduled run a day does the whole thing with no human in the loop:
pick the brand and topic → write the script and captions → **pre-render audit** → render the MP4 → check the stills → **final audit (must PASS)** → host the files on GitHub → post to YouTube, then Instagram, then LinkedIn → log it.

Never post a reel that fails the audit. Never post to any platform twice for the same day: `posted.json` is the record.

## 0. Setup (fresh container every run)
```bash
# attach first: add_repo(owner="Admin-FineSolves", repo="finesolves-blog-assets", access="push")
git clone --depth 1 https://github.com/Admin-FineSolves/finesolves-blog-assets ~/finesolves-blog-assets
cd ~/finesolves-blog-assets
npm i --silent @fontsource/space-grotesk @fontsource/inter @fontsource/dm-mono
DATE=$(TZ=Asia/Kolkata date +%F); R=reels/out/$DATE; mkdir -p $R
```
If `$R/posted.json` already exists, read it, skip the platforms already marked done, and post only the missing ones (re-use the existing script, captions and video). Don't re-render.

## 1. Pick the brand
Read `reels/log.md`. Rotate in this order and take the next one after the last logged row: **finesolves → finehealth → finesolves → finehr → finehealth →** (repeat). Fine Solves and FineHealth get two slots in five, FineHR gets one.

## 2. Pick the topic
One pain point a buyer recognises in two seconds. Not the technology. Check `log.md` and the "Already used" list below, and never repeat a topic.

| Brand | Audience | Topic pool (examples, invent more in the same spirit) |
|---|---|---|
| **finesolves** (custom products and AI) | founders, ops and IT heads at Indian SMB / mid-market firms | data retyped across WhatsApp/Excel/Tally; "ask the one person who knows"; month-end reconciliation by hand; approvals stuck in email; reports built by copy-paste every Monday; buying a big ERP for one small gap; AI pilots that never reach production; vendor follow-ups in spreadsheets; the cost of a requirements doc nobody reads; build vs buy for one workflow; dispatch planning on a whiteboard; stock counts that never match |
| **finehealth** (hospital management system) | hospital owners, administrators, doctors running clinics | OPD queue at registration; GST billing by hand; IPD charges added at discharge; lost or duplicate patient files; prescriptions doctors can't read back; reports printed and physically handed over; day-end cash reconciliation at the counter; one patient registered twice under two spellings; deposits and advances tracked in a register; multi-doctor clinic scheduling on paper |
| **finehr** (HR) | HR managers and owners at SMBs | attendance registers turned into salaries by hand; leave requests lost in email/WhatsApp; month-end payroll crunch; "how many leaves do I have left?" questions; new-joiner paperwork chasing; employee data in five spreadsheets |

**Claim limits (hard rules, the audit enforces most of them):**
- FineHealth may say: registration, OPD, IPD, GST-ready billing, one patient record, prescriptions, reports, cloud-hosted. **Not** WhatsApp delivery (planned, not shipped). No medical or patient-outcome claims. It improves operations.
- **FineHR: no feature claims at all beyond "one system" / "one place".** Describe the HR pain in detail; the product line is only e.g. "FineHR by Fine Solves. One system for your HR team." Never write "FineHR + a verb" (automates, tracks, handles, calculates, manages…).
- Never invent statistics, clients, hospitals, testimonials, results or prices. Any estimate is marked **ILLUSTRATIVE** on screen and "illustrative" in the captions. Prefer reels with no numbers. If you use a real statistic, it must come from a page you fetched this run, go in `$R/claims.json` with its URL, and be named in the caption ("according to …").
- Say **"products", never "software"**, on screen, in captions and alt text ("custom products", "a hospital billing product"). Hashtags keep their searchable form (#HospitalBillingSoftware).
- Names: "Fine Solves" (two words), "FineHealth", "FineHR". First mention "FineHealth by Fine Solves".
- Banned words: revolutionary, seamless, synergy, game-changing, cutting-edge, unlock, transform, delve, landscape, leverage, empower.

Write `$R/meta.json`:
`{"brand":"finehealth","topic":"<one line, unique>","primary_keyword":"hospital billing software","angle":"<the hook>"}`
`primary_keyword` is what a buyer would type into Google, and it must open the first caption line. Caption prose can't say "software", so pick keywords without that word: hospital management system, hospital billing, clinic management, HMS India, HR and payroll, leave management, attendance management, custom product development, AI product development, business process automation, Tally integration. The searchable "…Software" forms go in the hashtags.

## 3. Write `$R/script.json`
**Queue first:** if `reels/queue/` has a folder whose `meta.json` brand matches today's brand, use it. Copy its script.json, meta.json and captions.json into `$R`, then `git rm -r` that queue folder in the same commit as the reel. Skip to step 5.

Otherwise write a new one. Format: see the header of `reels/render_reel.py`. The aim is a reel that feels good to watch: constant gentle motion, one satisfying "click into place" moment, and a rhythm of short beats.

**Scene vocabulary**
- `kinetic`: big words revealed word by word through a mask. Use for the hook, twists and punchlines. `highlight` + `hl_style` "bar" (underline) or "block" (teal fill) on the one phrase that matters. Optional mono `eyebrow` (typed on) for place/time.
- `chaos`: 3–6 mono chips drift around, then snap into one tidy card with ticks. The signature "mess → order" moment: scattered tools, files or steps becoming one system.
- `ui`: a product window builds itself: rows rise in, values type on, a teal progress line runs, and the status chip flips to teal at the end. Use for FineHealth / Fine Solves "how it works". Show only allowed claims. For FineHR use `chaos` or `kinetic` instead, since a UI implies features.
- `compare`: today's steps appear and get struck through one by one, then a navy card rises with the new way.
- `bignum`: one giant number ticks up, with a mono unit on a teal block. Only ILLUSTRATIVE maths or a sourced stat.
- `steps`: three short lines with dots lighting up along a line ("Register. Treat. Bill.").
- `end`: logo, end line, tag, finesolves.com, brand bands sliding into the corner.
- `"transition": "bands"` on a scene = a navy/teal diagonal slab wipes across the cut into it. Use once per reel, before the resolution.

**Shape** (16–24 s, 5–6 scenes): hook `kinetic` (2.6–3 s) → twist `kinetic` (2.5–2.8 s) → one set-piece: `chaos` / `ui` / `compare` / `bignum` (4.2–5.8 s) → optional second set-piece or punchline → resolution `steps` or `kinetic` with `"transition":"bands"` (2.8–3.4 s) → `end` (3.2 s). Every reel needs at least one set-piece. Don't use the same set-piece two reels in a row (check the previous script in `reels/out/`).

**Copy rules:** headline ≤10 words, every authored line ≤26 characters (break with `\n`), chips ≤18 characters, card and row text ≤40, sentence case, short declaratives, dry and specific. Hooks work best as something the viewer has said or heard ("How many leaves do I have left?") or a time and place ("OPD · 10:42 AM"). End lines: "FineHealth by Fine Solves" (tag HOSPITAL MANAGEMENT SYSTEM or GST-READY HOSPITAL BILLING), "FineHR by Fine Solves" (tag ONE SYSTEM FOR HR), or a short Fine Solves promise like "Custom products,\nlive in weeks." (tag CUSTOM PRODUCTS · AI).

## 4. Write `$R/captions.json`
```json
{"instagram": "...", "linkedin": "...", "youtube_title": "...", "youtube_description": "...", "alt": "..."}
```
- **instagram** (≤2,200 chars): line 1 opens with the primary keyword. Two short paragraphs: the problem, then what Fine Solves / FineHealth / FineHR does about it (within the claim limits). One question to the reader. CTA line: "Book a demo → finesolves.com" (FineHealth) or "Talk to us → finesolves.com" (Fine Solves, FineHR). 5 specific hashtags, nothing generic (#business, #reels, #viral…).
- **linkedin**: the same caption, rewritten for LinkedIn if it helps. **No ( ) [ ] { } characters anywhere.** Keep the same CTA and hashtags. The run adds "Watch the reel: <YouTube URL>" before the CTA at posting time. Don't put it in the file.
- **youtube_title** (≤100 chars): keyword-led, ends with " #Shorts".
- **youtube_description**: 2–3 sentences + "https://finesolves.com" + the 5 hashtags. No < or >.
- **alt**: one sentence naming what the reel shows.

## 5. Pre-render audit, render, look
```bash
python3 reels/audit_reel.py $R --prerender        # fix until PASS
python3 reels/render_reel.py $R/script.json $R    # ~40 s; writes reel.mp4 (sound designed, loudness-normalised), cover.jpg, still-NN.png
```
Open **every** `still-NN.png` with Read (and `cover.jpg`). Check: nothing clipped or overlapping, nothing below y≈1460 except the small wordmark and end-card bands, every word spelled right, and the cover works as a thumbnail (it's the settled first scene). Then pull 4–5 mid-motion frames from reel.mp4 (`ffmpeg -ss <t> -i $R/reel.mp4 -frames:v 1 f.png`), especially inside chaos, compare and ui scenes, and check that moving elements never cover the headline. Fix the script and re-render if not.

## 6. Final audit (must PASS)
```bash
python3 reels/audit_reel.py $R
```
Then a manual read-through: would an Indian hospital administrator / ops head / HR manager stop scrolling for the hook? Is every claim within the limits? Is the copy free of filler? Up to 3 fix-and-re-audit rounds. If it still fails, **don't post**. Report the failing checks.

## 7. Host on GitHub
```bash
rm -f $R/reel.html
git add $R && git -c user.name="Fine Solves Reels Bot" -c user.email="admin@finesolves.com" commit -qm "Reel $DATE: <topic>"
git pull -q --rebase origin main && git push -q origin main
SHA=$(git rev-parse HEAD)
VIDEO_URL=https://cdn.jsdelivr.net/gh/Admin-FineSolves/finesolves-blog-assets@$SHA/$R/reel.mp4
COVER_URL=https://raw.githubusercontent.com/Admin-FineSolves/finesolves-blog-assets/$SHA/$R/cover.jpg
RAW_VIDEO=https://raw.githubusercontent.com/Admin-FineSolves/finesolves-blog-assets/$SHA/$R/reel.mp4
curl -s -o /dev/null -w "%{http_code}\n" $RAW_VIDEO    # must be 200
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" $COVER_URL   # must be 200 image/jpeg
```
(The container can't reach jsDelivr; Zapier can. jsDelivr serves `video/mp4`, which Instagram needs. If it hasn't cached the file yet, Instagram may take a minute.)

## 8. Post (Zapier), in this order, each exactly once
After **each** successful post, write the result into `$R/posted.json` (`{"youtube":{"id":"…","url":"…"},"instagram":{"id":"…"},"linkedin":{"id":"…"}}`), commit and push straight away, so a re-run never posts twice.

Always `inspect_zapier_actions` first to get exact params and dynamic values.

1. **YouTube**: selected_api `YouTubeV4CLIAPI`, action `upload_video`: `title` = youtube_title, `description` = youtube_description, `video` = VIDEO_URL (fall back to RAW_VIDEO once if the file can't be fetched), `privacy_status` = public, `made_for_kids` = false, `category_id` = Science & Technology (resolve the dynamic enum), `tags` = the 5 hashtags without "#", `default_language` = en. Short URL = `https://youtube.com/shorts/<id>`.
2. **Instagram**: selected_api `InstagramBusinessCLIAPI`, action `publish_video`: `instagramPageId` = the Fine Solves business account (resolve the dynamic enum; if there's more than one candidate, stop and report), `video` = VIDEO_URL, `caption` = instagram. If the action errors because the media isn't ready or can't be fetched, wait 60 s and try once more with RAW_VIDEO. A failed attempt isn't a post.
3. **LinkedIn company page**: selected_api `LinkedInCLIAPI`, action `create_company_update`: `company_id` = the Fine Solves page (resolve the dynamic enum; stop if ambiguous), `comment` = linkedin caption with "Watch the reel: <Short URL>" inserted on its own line before the CTA, `image` = COVER_URL, `image_type` = post_media. (Zapier can't upload video to a LinkedIn page, so LinkedIn gets the cover frame + link. If YouTube failed, post with the cover and finesolves.com only.)

If one platform fails, still post to the others, then report which one failed and why.

## 9. Log and report
Append a row to `reels/log.md`:
`| DATE | brand | topic | primary_keyword | YouTube URL | IG ✓/✗ | LI ✓/✗ | audit score |`
Commit and push. Finish with one line: date, brand, topic, YouTube URL, Instagram ✓/✗, LinkedIn ✓/✗, audit score.

## Failure handling
- Audit fails after 3 rounds → don't post; report the failing checks.
- Zapier says an app isn't connected or auth expired → skip that platform; report "Reconnect <app> in Zapier".
- Git push fails → don't post (no public URL); report.
- Render error → fix the script (usually a too-long line or a missing field) and retry; never post a partial video.

## Already used (don't repeat these topics)
Batch 1 (01–05): team as the integration (WhatsApp/Excel/Tally retyping); weeks not quarters; off-the-shelf fits most; AI won't fix a messy process; no black box / pay per milestone.
Batch 2 (06–10): queue at the billing counter; where's the file?; discharge bill built at the end; the cost of "we'll manage in Excel"; three questions before you buy AI.
Batch 3: paper relay; paper machine; pop-up hospital; discharge hourglass; punch-card mountain; leave-letter maze.
