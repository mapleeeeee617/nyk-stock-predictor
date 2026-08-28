"""ニュース収集（公式プレスリリース + Google ニュース RSS）。"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, asdict

import feedparser
import requests
from bs4 import BeautifulSoup

from . import config


@dataclass
class NewsItem:
    date: str          # ISO 日付
    title: str
    url: str
    source: str        # "公式" / "Google News:媒体名"
    category: str       # "プレスリリース" / "お知らせ" / "報道" 等

    def as_dict(self):
        return asdict(self)


_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")


def _within_lookback(d: dt.date) -> bool:
    return (dt.date.today() - d).days <= config.NEWS_LOOKBACK_DAYS


def fetch_official_news() -> list[NewsItem]:
    """nyk.com の年別ニュース一覧をスクレイピングする。"""
    items: list[NewsItem] = []
    years = {dt.date.today().year, dt.date.today().year - 1}
    for year in sorted(years, reverse=True):
        url = config.NYK_NEWS_URL_TEMPLATE.format(year=year)
        try:
            r = requests.get(url, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
        except requests.RequestException:
            continue
        soup = BeautifulSoup(r.content, "lxml")
        for a in soup.select("a"):
            href = a.get("href", "")
            text = " ".join(a.get_text().split())
            if f"/news/{year}/" not in href or not text:
                continue
            m = _DATE_RE.search(text)
            if not m:
                continue
            d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if not _within_lookback(d):
                continue
            rest = _DATE_RE.sub("", text).strip()
            category = "プレスリリース"
            for tag in ("プレスリリース", "お知らせ", "IR", "採用"):
                if rest.startswith(tag):
                    category = tag
                    rest = rest[len(tag):].strip()
                    break
            full_url = href if href.startswith("http") else f"https://www.nyk.com{href}"
            items.append(NewsItem(d.isoformat(), rest, full_url, "公式", category))
    # 重複除去
    seen = set()
    uniq = []
    for it in items:
        if it.url in seen:
            continue
        seen.add(it.url)
        uniq.append(it)
    return uniq


def fetch_google_news() -> list[NewsItem]:
    """Google ニュース RSS から関連報道を取得する。"""
    feed = feedparser.parse(config.GOOGLE_NEWS_RSS)
    items: list[NewsItem] = []
    for e in feed.entries:
        try:
            pub = dt.datetime(*e.published_parsed[:6]).date()
        except Exception:
            pub = dt.date.today()
        if not _within_lookback(pub):
            continue
        title = e.title
        media = ""
        if " - " in title:
            title, media = title.rsplit(" - ", 1)
        items.append(
            NewsItem(pub.isoformat(), title.strip(), e.link,
                     f"Google News:{media}".rstrip(":"), "報道")
        )
    return items


def collect_news() -> list[NewsItem]:
    """全ソースを統合し、新しい順に返す。"""
    combined = fetch_official_news() + fetch_google_news()
    # タイトル正規化での重複除去
    seen: set[str] = set()
    uniq: list[NewsItem] = []
    for it in sorted(combined, key=lambda x: x.date, reverse=True):
        key = re.sub(r"\s+", "", it.title)[:40]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq
