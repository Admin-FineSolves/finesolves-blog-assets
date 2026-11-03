# finesolves-blog-assets

Images and source files for the Fine Solves blog, produced by a daily automated pipeline.

- `RUNBOOK.md` — the daily process (research → write → creatives → publish).
- `creatives.py` — renders the branded hero (1200×630) and infographic (1080×1350).
- `posts/YYYY-MM-DD/` — each day's post HTML, creative spec and images.
- `topics-log.md` — every published post, used to avoid repeat topics.

Website: https://finesolves.com

## Reels
- `reels/RUNBOOK.md`: the daily reel process (script → render → audit → post to YouTube, Instagram, LinkedIn).
- `reels/render_reel.py`: renders a branded 1080×1920 motion-graphics reel from `script.json`.
- `reels/audit_reel.py`: the brand, claim and spec gate. Must PASS before posting.
- `reels/out/YYYY-MM-DD/`: each day's script, captions, video, cover and `posted.json`.
- `reels/log.md`: every posted reel, used for brand rotation and to avoid repeat topics.
