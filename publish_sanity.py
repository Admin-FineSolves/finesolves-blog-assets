"""Publish a finished post to the Fine Solves blog (Sanity project hf7ugumv, dataset production).

Usage: SANITY_WRITE_TOKEN=... python3 publish_sanity.py posts/<DATE>-<SLOT>

Reads <post>/meta.json and <post>/post.html. The document id is fixed per slot (post-<DATE>-<SLOT>) and the
mutation is createOrReplace, so re-running updates the same post instead of creating a duplicate.
Writes <post>/sanity-mutation.json (no secrets) and prints the live URL. Exit 0 = published and verified.
"""
import datetime
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API = "https://hf7ugumv.api.sanity.io/v2025-02-19/data"


def query(groq):
    url = f"{API}/query/production?" + urllib.parse.urlencode({"query": groq})
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)["result"]


def slugify(title):
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    return slug[:60].rsplit("-", 1)[0] if len(slug) > 60 else slug


def main(post):
    token = os.environ.get("SANITY_WRITE_TOKEN")
    if not token:
        sys.exit("SANITY_WRITE_TOKEN is not set")
    doc_id = "post-" + os.path.basename(post.rstrip("/"))  # post-2026-11-11-morning
    meta = json.load(open(f"{post}/meta.json", encoding="utf-8"))
    html = open(f"{post}/post.html", encoding="utf-8").read().strip()
    html = re.sub(r"\s*#end\s*$", "", html)  # the audit's end marker is not part of the article

    slug = slugify(meta["title"])
    base, n = slug, 2
    while query(f'count(*[_type=="post" && slug.current=={json.dumps(slug)} && _id!={json.dumps(doc_id)}])'):
        slug, n = f"{base}-{n}", n + 1

    doc = {
        "_id": doc_id,
        "_type": "post",
        "title": meta["title"],
        "slug": {"_type": "slug", "current": slug},
        "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tags": [k for k in [meta.get("primary_keyword")] if k],
        "html": html,
    }
    body = json.dumps({"mutations": [{"createOrReplace": doc}]})
    open(f"{post}/sanity-mutation.json", "w", encoding="utf-8").write(body)

    request = urllib.request.Request(
        f"{API}/mutate/production?returnIds=true",
        data=body.encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            result = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Sanity rejected the post: HTTP {e.code} {e.read().decode()[:300]}")
    if doc_id not in [x.get("id") for x in result.get("results", [])]:
        sys.exit(f"Unexpected Sanity response: {json.dumps(result)[:300]}")

    check = query(f'*[_id=={json.dumps(doc_id)}][0]{{title, "slug": slug.current, "chars": length(html)}}')
    if not check or not check.get("chars"):
        sys.exit(f"Post not readable after publishing: {check}")
    print(f"Published {doc_id}: https://finesolves.com/blog/{check['slug']} ({check['chars']} chars)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
