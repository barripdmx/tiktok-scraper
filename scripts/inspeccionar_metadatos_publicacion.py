"""Inspecciona los campos de una publicación pública y una imagen servida por TikTok."""

from __future__ import annotations

import csv
import json
import urllib.request
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "outputs" / "comentarios_blocus_20261026" / "publicaciones.csv"


class Hydration(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__UNIVERSAL_DATA_FOR_REHYDRATION__":
            self.capture = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(), response.headers.get_content_type()


def main():
    with POSTS.open(encoding="utf-8-sig", newline="") as stream:
        posts = list(csv.DictReader(stream))
    for kind in ("photo", "video"):
        post = None
        item = {}
        checked = 0
        candidates = [row for row in posts if row["tipo"] == kind]
        if kind == "photo":
            candidates = candidates[::max(1, len(candidates) // 20)][:20]
        else:
            candidates = candidates[:20]
        for candidate in candidates:
            checked += 1
            try:
                html, _ = fetch(candidate["url"])
                parser = Hydration()
                parser.feed(html.decode("utf-8", errors="replace"))
                scope = json.loads("".join(parser.parts)).get("__DEFAULT_SCOPE__", {})
                detail = scope.get("webapp.video-detail", {})
                item = detail.get("itemInfo", {}).get("itemStruct", {})
            except Exception:
                item = {}
            if item:
                post = candidate
                break
        if post is None:
            print(kind, "no public item found among", checked, "URLs")
            continue
        print(kind, post["id"], "item_found", bool(item))
        print("  item keys", sorted(item.keys()))
        for key in ("createTime", "desc", "locationCreated", "poi", "music", "stats", "statsV2"):
            value = item.get(key)
            if key in ("music", "stats", "statsV2"):
                value = sorted(value.keys()) if isinstance(value, dict) else None
            print(" ", key, str(value)[:180])
        if kind == "photo":
            image_post = item.get("imagePost", {})
            images = image_post.get("images", [])
            print("  imagePost keys", sorted(image_post.keys()), "images", len(images))
            if images:
                first = images[0]
                print("  first image keys", sorted(first.keys()))
                urls = first.get("imageURL", {}).get("urlList", [])
                if urls:
                    try:
                        payload, mime = fetch(urls[0])
                        picture = Image.open(BytesIO(payload))
                        exif = picture.getexif()
                        print("  CDN image", urlparse(urls[0]).hostname, mime, len(payload),
                              picture.format, picture.size, "EXIF tags", len(exif),
                              "info keys", sorted(picture.info.keys()))
                    except Exception as exc:
                        print("  CDN image unavailable", type(exc).__name__, str(exc)[:120])
        else:
            video = item.get("video", {})
            print("  video keys", sorted(video.keys()))
            for key in ("duration", "width", "height", "ratio", "format", "codecType", "bitrate"):
                print(" ", key, video.get(key))


if __name__ == "__main__":
    main()
