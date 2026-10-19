"""Rebuild the Writing section of the profile README from clarafold.com.

Reads the sitemap, fetches every /insights/ page and takes the title, publish date
and topic from the page's JSON-LD. Everything between the WRITING markers in
README.md is regenerated; the rest of the file is left alone.

Standard library only, so the GitHub Action needs no install step.
    python3 scripts/update_writing.py
"""
import html
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SITE = "https://clarafold.com"
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- WRITING:START -->", "<!-- WRITING:END -->"
TOPICS = ["GTM", "ABM", "Outbound", "RevOps", "Content", "AI"]  # display order; unknown topics go last
LATEST = 5


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cyberanon1111-profile-bot"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def article(url: str) -> dict:
    page = fetch(url)
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
    title = re.sub(r"\s*[|—–-]\s*Clarafold\s*$", "", html.unescape(title).strip())
    date = re.search(r'"datePublished":\s*"([\d-]{10})', page)
    topic = re.search(r'"articleSection":\s*"([^"]+)"', page)
    return {"url": url, "title": title,
            "date": date.group(1) if date else "",
            "topic": topic.group(1) if topic else "Other"}


def render(posts: list) -> str:
    posts = sorted(posts, key=lambda p: (p["date"], p["title"]), reverse=True)
    out = [START, "",
           f"{len(posts)} articles on [clarafold.com/insights]({SITE}/insights). "
           "Practical, sourced and written for teams selling into hard B2B markets.", "",
           "**Latest**", ""]
    out += [f"- [{p['title']}]({p['url']}) · `{p['topic']}`" for p in posts[:LATEST]]
    out += ["", "**All articles by topic**", ""]
    topics = sorted({p["topic"] for p in posts},
                    key=lambda t: (TOPICS.index(t) if t in TOPICS else len(TOPICS), t))
    for t in topics:
        group = [p for p in posts if p["topic"] == t]
        out += [f"<details><summary><b>{t}</b> · {len(group)}</summary>", ""]
        out += [f"- [{p['title']}]({p['url']})" for p in group]
        out += ["", "</details>"]
    out += ["", END]
    return "\n".join(out)


def main() -> int:
    urls = re.findall(r"<loc>([^<]*/insights/[^<]+)</loc>", fetch(f"{SITE}/sitemap.xml"))
    if not urls:
        print("No insight URLs in sitemap; leaving README unchanged.")
        return 1
    with ThreadPoolExecutor(8) as pool:
        posts = list(pool.map(article, urls))

    text = README.read_text()
    if START not in text or END not in text:
        print("WRITING markers not found in README.md")
        return 1
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: render(posts), text, flags=re.S)
    if new != text:
        README.write_text(new)
        print(f"README updated: {len(posts)} articles.")
    else:
        print("No change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
