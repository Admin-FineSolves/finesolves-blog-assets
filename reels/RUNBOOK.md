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
Read `reels/log.md`. Alternate **finesolves → finehr → finesolves → finehr …**: take the other one from the last logged row (if the last row is finehealth, take finesolves). **FineHealth is paused** (from 2026-11-17): no new FineHealth reels.

## 2. Pick the topic
The reels are for sales and marketing: every topic is aimed at one ICP (buyer) and is a pain that buyer recognises in two seconds. Not the technology. Name the ICP in `meta.json` (`"icp"`), write the hook in their words, and rotate ICPs so the same one doesn't run twice in a row for a brand. Check `log.md` and the "Already used" list below, and never repeat a topic.

**ICPs**
- **Fine Solves (custom-built products and AI):** startup founders · operations teams / ops heads · owners of manufacturing companies (plant, godown, dispatch, vendors, job work) · other SMB / mid-market founders and business heads.
- **FineHR (HRMS):** HR teams and HR managers · startup founders who still do HR themselves · owners of manufacturing companies with shift and contract workforces.

| Brand | Audience | Topic pool (examples, invent more in the same spirit) |
|---|---|---|
| **finesolves** (custom products and AI) | startup founders, operations teams, manufacturing company owners at Indian SMB / mid-market firms | founder still running ops from WhatsApp groups; MVP stuck with an agency for months; production plan on a whiteboard; job-work challans tracked on paper; machine downtime noted in a register; | data retyped across WhatsApp/Excel/Tally; "ask the one person who knows"; month-end reconciliation by hand; approvals stuck in email; reports built by copy-paste every Monday; buying a big ERP for one small gap; AI pilots that never reach production; vendor follow-ups in spreadsheets; the cost of a requirements doc nobody reads; build vs buy for one workflow; dispatch planning on a whiteboard; stock counts that never match |
| ~~finehealth~~ (paused) | hospital owners, administrators, doctors running clinics | OPD queue at registration; GST billing by hand; IPD charges added at discharge; lost or duplicate patient files; prescriptions doctors can't read back; reports printed and physically handed over; day-end cash reconciliation at the counter; one patient registered twice under two spellings; deposits and advances tracked in a register; multi-doctor clinic scheduling on paper |
| **finehr** (HRMS) | HR teams, startup founders doing HR, manufacturing owners with shift workers | attendance registers turned into salaries by hand; shift attendance at the factory gate; leave requests lost in email/WhatsApp; month-end payroll crunch; "how many leaves do I have left?"; founder screening 60 candidates alone; first-round interviews eating the HR team's week; candidates who no-show after three calls |

**Claim limits (hard rules, the audit enforces most of them):**
- FineHealth may say: registration, OPD, IPD, GST-ready billing, one patient record, prescriptions, reports, cloud-hosted. **Not** WhatsApp delivery (planned, not shipped). No medical or patient-outcome claims. It improves operations.
- **FineHR may name only these features: attendance, leave, payroll, and the AI interviewer** (first-round interviews), plus "one system" / "one place" for HR. Nothing else: no statutory compliance (PF/ESI/TDS), integrations, biometric devices, WhatsApp, onboarding, appraisals, expenses or mobile-app claims. No numbers about the AI interviewer (accuracy, hires, time saved) unless sourced.
- Never invent statistics, clients, hospitals, testimonials, results or prices. Any estimate is marked **ILLUSTRATIVE** on screen and "illustrative" in the captions. Prefer reels with no numbers. If you use a real statistic, it must come from a page you fetched this run, go in `$R/claims.json` with its URL, and be named in the caption ("according to …").
- Say **"products", never "software"**, on screen, in captions and alt text ("custom products", "a hospital billing product"). Hashtags keep their searchable form (#HospitalBillingSoftware).
- Names: "Fine Solves" (two words), "FineHealth", "FineHR". First mention "FineHealth by Fine Solves".
- Banned words: revolutionary, seamless, synergy, game-changing, cutting-edge, unlock, transform, delve, landscape, leverage, empower.

Write `$R/meta.json`:
`{"brand":"finehr","icp":"HR team","topic":"<one line, unique>","primary_keyword":"payroll management","angle":"<the hook>"}`
`primary_keyword` is what a buyer would type into Google, and it must open the first caption line. Caption prose can't say "software", so pick keywords without that word: HRMS India, HR and payroll, payroll management, AI interviewer, AI recruitment, MVP development, product development for startups, manufacturing ERP, leave management, attendance management, custom product development, AI product development, business process automation, Tally integration. The searchable "…Software" forms go in the hashtags.

## 3. Write `$R/script.json` (v2 story format, rendered by `reels/render_v2.py`)
**Queue first:** if `reels/queue/` has a folder whose `meta.json` brand matches today's brand, use it. Copy its script.json, meta.json, captions.json and `vo/` (if present) into `$R`, then `git rm -r` that queue folder in the same commit as the reel. If it has `vo/`, skip to step 5; otherwise skip to step 4b (voiceover).

Otherwise write a new one. **All new reels use v2** (`"version": 2`; full format in the header of `reels/render_v2.py`). The old `render_reel.py` text-on-white look is retired: it read as low effort. The bar: every frame is full of something worth looking at, the story is shown with props rather than told in words, and it sounds produced (voiceover + music).

**Scene types (props):** `phone` (lock-screen notifications flooding in, or a chat thread with typing dots) · `calendar` (`fill`: a week fills with blocks and gets stamped; `clear`: blocks vanish, a few flip teal) · `calls` (stacked video-call cards asking the same question) · `sheet` (spreadsheet typing in, a cell flagged, sticky note) · `statement` (big line on teal, the turn) · `app` (product window: nav, rows with progress bars, status chips flipping, a cursor clicking a button, a toast) · `modules` (module tiles fly in and lock into one system) · `end` (product name, tag, CTA button the cursor clicks, finesolves.com).
**Backgrounds:** `navy` = the problem, `teal` = the turn, `cream` = the product and the payoff. Use all three.
**Transitions:** default `push`; `"trans":"wipe"` into the teal turn (once); `"trans":"zoom"` into the product and the end card.

**Story shape** (7–9 scenes, 24–34 s with VO):
1. **Hook** (navy, `phone`): name the ICP and the moment in the eyebrow and headline ("FOUNDERS · HIRING" / "Hiring this month?").
2. **The mess, shown** (`calendar` fill / `sheet` / `calls` / chat): the pain as the ICP sees it on their own screen.
3. **The cost** (navy prop or second mess beat): what it costs them (the product isn't getting built; salaries go out late; the truck leaves without the invoice). No invented numbers.
4. **The turn** (teal `statement`, `"trans":"wipe"`): one line, "Let the AI interviewer go first."
5. **The product doing it** (`app`, `"trans":"zoom"`): only allowed claims.
6. **The payoff** (`calendar` clear / a clean sheet / `modules`).
7. **Optional "one system"** (`modules`).
8. **End** (`end`, `"trans":"zoom"`, `cta`: "Book a demo" for FineHR, "Talk to us" for Fine Solves).
Rotate the mess prop: don't open two reels in a row with the same prop sequence (check the previous script in `reels/out/`).

**Copy rules:** headline ≤3 lines of ≤18 characters (break with `\n`), every prop string ≤32 characters, sentence case, dry and specific. Each scene's `vo` is one or two spoken sentences (≤22 words), conversational, written for the ear. The VO carries the story; the headline is the 3-word version of it. Mock UI content (names, times, file names) must look real but generic: no real companies, people or brands. End lines: "FineHR by Fine Solves" (tag HRMS · ATTENDANCE · PAYROLL, HRMS · AI INTERVIEWER or ONE SYSTEM FOR HR), or a short Fine Solves promise like "Custom products,\nlive in weeks." (tag CUSTOM PRODUCTS · AI).

## 4. Write `$R/captions.json`
```json
{"instagram": "...", "linkedin": "...", "youtube_title": "...", "youtube_description": "...", "alt": "..."}
```
- **instagram** (≤2,200 chars): line 1 opens with the primary keyword. Two short paragraphs: the problem, then what Fine Solves / FineHR does about it for that ICP (within the claim limits). One question to the reader. CTA line: "Book a demo → finesolves.com" (FineHR) or "Talk to us → finesolves.com" (Fine Solves). 5 specific hashtags, nothing generic (#business, #reels, #viral…).
- **linkedin**: the same caption, rewritten for LinkedIn if it helps. **No ( ) [ ] { } characters anywhere.** Keep the same CTA and hashtags. The run adds "Watch the reel: <YouTube URL>" before the CTA at posting time. Don't put it in the file.
- **youtube_title** (≤100 chars): keyword-led, ends with " #Shorts".
- **youtube_description**: 2–3 sentences + "https://finesolves.com" + the 5 hashtags. No < or >.
- **alt**: one sentence naming what the reel shows.

## 4b. Voiceover (ElevenLabs via Zapier)
For each scene with a `vo` line, in order: `execute_zapier_write_action` on ElevenLabs (`App226160CLIAPI`, action `text_to_speech`): `text` = the vo line, `voice_id` = `cjVigY5qzO86Huf0OWal` (Eric, smooth and trustworthy; the owner prefers Jessa `yj30vwTGJxSHezdAGsv9`, which needs a paid ElevenLabs plan: try Jessa first, and if ElevenLabs answers "paid_plan_required" or the action returns None, use Eric for every scene; never mix voices in one reel), `model_id` = `eleven_multilingual_v2`, `output_format` = `mp3_44100_128`. Download each result's `audio_url` to `$R/vo/NN.mp3` (NN = scene number, 01…): `curl -sSf -o $R/vo/NN.mp3 "<audio_url>"`. Write "finesolves dot com" for the site in VO text.
If ElevenLabs isn't connected, a call fails, or a download is refused, delete `$R/vo/` and render without voiceover (the renderer then uses each scene's `dur`, with no captions). Report "VO skipped: <reason>". Never ship a reel with VO on some scenes and not others.

## 5. Pre-render audit, render, look
```bash
python3 reels/audit_reel.py $R --prerender        # fix until PASS
python3 reels/render_v2.py $R/script.json $R      # ~2 min; writes reel.mp4 (VO + ducked music + burned-in captions), cover.jpg, still-NN.png, timing.json
```
Open **every** `still-NN.png` with Read (and `cover.jpg`). Check: nothing clipped or overlapping, captions (y≈1430–1510) don't cover the key part of a prop, every word spelled right, and the cover works as a thumbnail. Then pull 6–8 mid-motion frames from reel.mp4 (`ffmpeg -ss <t> -i $R/reel.mp4 -frames:v 1 f.png`), especially during transitions and inside calendar, calls and app scenes. Fix the script and re-render if not.

## 6. Final audit (must PASS)
```bash
python3 reels/audit_reel.py $R
```
Then a manual read-through: would an Indian hospital administrator / ops head / HR manager stop scrolling for the hook? Is every claim within the limits? Is the copy free of filler? Up to 3 fix-and-re-audit rounds. If it still fails, **don't post**. Report the failing checks.

## 7. Host on GitHub
```bash
rm -f $R/reel.html
# keep vo/ in the commit so a re-run can reuse it
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
