#!/usr/bin/env python3
"""
resolve_previews.py

Finds the best Apple Music recording for every piece in the Repertoire catalog,
then writes the choices (Apple track IDs only, no audio) into picks.js, which
index.html loads. Because the picks live in their own file, you can change the
design of index.html without redoing this.

Usage (needs Python 3 and an internet connection, nothing to install):
    python3 resolve_previews.py
    python3 resolve_previews.py --html index.html --delay 3.5 --min-score 7.5

Outputs:
    picks.js        the chosen recordings (keep it next to index.html)
    review.csv      every piece, its score, and the top candidates, so you can spot-check

Pieces scoring below --min-score get no pick. The app still finds a recording
for them live when someone presses play, and they are listed in review.csv.

Apple's Search API allows roughly 20 requests per minute, so the script waits
--delay seconds between requests. 92 pieces takes about 6 to 10 minutes.
Re-running is safe: it starts from scratch each time and only rewrites picks.js and review.csv.
"""
import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BAD_WORDS = [
    "arr.", "arranged", "arrangement", "transcri", "karaoke", "instrumental version",
    "cover", "guitar", "violin", "cello", "flute", "harp", "saxophone", "synth",
    "lofi", "lo-fi", "music box", "relax", "sleep", "meditat", "study", "tribute",
    "orchestral version", "for orchestra", "piano trio", "duo",
]
STOP = {"in", "the", "of", "for", "and", "no", "a", "de", "la", "du", "des", "from", "with", "op"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def parse_catalog(html):
    """Read the P = [...] catalog out of index.html."""
    a = html.index("var P = [")
    b = html.index("\n  ];", a)
    rows = re.findall(r'\["([a-z]+)","(.*?)","(.*?)","(.*?)",(\d+)\]', html[a:b])
    return [dict(genre=g, composer=c, title=t, detail=d, level=int(l)) for g, c, t, d, l in rows]


def search_title(t):
    """A title as a music search likes it: no notes like (Song-Book), no curly quotes or apostrophes."""
    t = re.sub(r"\s*\((?:Song-Book|piano solo|Blue Lullaby)\)", "", t, flags=re.I)
    return t.replace("(", "").replace(")", "").replace("\u2019", "'").replace("\u201c", "").replace("\u201d", "").replace('"', "")


def search_detail(d):
    return "" if re.match(r"(Song-Book|Solo version|Piano and orchestra)", d) else d


def load_alts(html):
    """Apple's own wording for pieces it names differently (see APPLE_ALT in index.html)."""
    m = re.search(r"  var APPLE_ALT = (\{.*\});", html)
    return json.loads(m.group(1)) if m else {}


def key_of(p):
    return f'{p["composer"]}|{p["title"]}|{p["detail"]}'


def api_get(base, path, params, retries=3):
    url = f"{base}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RepertoireResolver/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = 60 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5)
    return {"results": []}


def search(base, term, delay):
    data = api_get(base, "search", {"media": "music", "entity": "song", "limit": 25, "country": "us", "term": term})
    time.sleep(delay)
    return [r for r in data.get("results", []) if r.get("previewUrl")]


def score(piece, r):
    track, album, artist = norm(r.get("trackName")), norm(r.get("collectionName")), norm(r.get("artistName"))
    hay = f"{track} {album}"
    hay_tokens = set(hay.split())
    everything = f"{hay} {artist}"

    surname = norm(piece["composer"]).split()[-1]
    s = 3.0 if surname in everything.split() or surname in everything else 0.0

    if piece.get("alt"):
        # the track title must carry Apple's name for this movement (e.g. "Dream" for Op. 40 No. 2)
        if any(norm(a) in hay_tokens for a in piece["alt"]):
            s += 3.0
    else:
        title_tokens = [t for t in norm(search_title(piece["title"])).split() if t not in STOP]
        if title_tokens:
            s += 3.0 * sum(t in hay_tokens for t in title_tokens) / len(title_tokens)

    nums = re.findall(r"\d+", piece["detail"])
    if nums:
        s += 3.0 * sum(n in hay_tokens for n in nums) / len(nums)
    m = re.search(r"op\.?\s*(\d+)", piece["detail"], re.I)
    if m and re.search(rf"\bop {m.group(1)}\b", hay):
        s += 1.5

    if piece["genre"] in ("sonata", "concerto"):
        if re.search(r"\b(i|1st|first)\b", track) and not re.search(r"\b(ii|iii|iv|2nd|3rd)\b", track):
            s += 1.0

    raw = f'{r.get("trackName", "")} {r.get("collectionName", "")} {r.get("artistName", "")}'.lower()
    for w in BAD_WORDS:
        if w in raw and not (w == "orchestral version" and piece["genre"] == "concerto"):
            s -= 5.0
            break
    return round(s, 2)


def candidates(piece, base, delay):
    title, detail = search_title(piece["title"]), search_detail(piece["detail"])
    queries = []
    if piece.get("alt"):
        queries.append(f'{piece["composer"]} Concert Etudes {re.split(r" No[.]", piece["detail"])[0]} {piece["alt"][0]}')
    queries += [f'{piece["composer"]} {title} {detail}'.strip(), f'{piece["composer"]} {title}',
                f'{piece["composer"]} piano {re.sub(r"^piano ", "", title, flags=re.I)}']
    results, seen = [], set()
    for q in queries:
        for r in search(base, q, delay):
            if r["trackId"] not in seen:
                seen.add(r["trackId"]); results.append(r)
        if results and max(score(piece, r) for r in results) >= 6:
            break
    return sorted(((score(piece, r), r) for r in results), key=lambda x: -x[0])


def picks_js(picks):
    lines = ["/* Generated by resolve_previews.py. Delete this file and the app looks recordings up live. */", "window.PICKS = {"]
    items = list(picks.items())
    for n, (k, v) in enumerate(items):
        comma = "," if n < len(items) - 1 else ""
        lines.append(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}{comma}")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="index.html")
    ap.add_argument("--delay", type=float, default=3.5, help="seconds between requests")
    ap.add_argument("--min-score", type=float, default=7.5)
    ap.add_argument("--api", default="https://itunes.apple.com", help="API base URL (for testing)")
    ap.add_argument("--picks", default="picks.js")
    ap.add_argument("--review", default="review.csv")
    args = ap.parse_args()

    with open(args.html, encoding="utf-8") as f:
        html = f.read()
    catalog = parse_catalog(html)
    alts = load_alts(html)
    for pc in catalog:
        pc["alt"] = alts.get(key_of(pc))
    print(f"Found {len(catalog)} pieces in {args.html}")

    picks, rows = {}, []
    for n, p in enumerate(catalog, 1):
        ranked = candidates(p, args.api, args.delay)
        best_score, best = ranked[0] if ranked else (0, None)
        ok = best is not None and best_score >= args.min_score
        label = f'{p["composer"]}: {p["title"]} ({p["detail"]})'
        if ok:
            picks[key_of(p)] = {"id": best["trackId"], "name": best.get("trackName", ""), "artist": best.get("artistName", "")}
        print(f'[{n}/{len(catalog)}] {"OK    " if ok else "REVIEW"} {best_score:>5}  {label}')
        row = {"piece": label, "status": "picked" if ok else "no confident match", "score": best_score}
        for i in range(3):
            if i < len(ranked):
                sc, r = ranked[i]
                row[f"candidate{i + 1}"] = f'{sc} | {r.get("trackName", "")} | {r.get("artistName", "")} | {r.get("collectionName", "")}'
            else:
                row[f"candidate{i + 1}"] = ""
        rows.append(row)

    with open(args.picks, "w", encoding="utf-8") as f:
        f.write(picks_js(picks))
    with open(args.review, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["piece", "status", "score", "candidate1", "candidate2", "candidate3"])
        w.writeheader()
        w.writerows(rows)

    print(f"\nPicked a recording for {len(picks)} of {len(catalog)} pieces.")
    print(f"Wrote {args.picks} and {args.review}. Pieces without a pick still work: the app searches live.")


if __name__ == "__main__":
    main()
