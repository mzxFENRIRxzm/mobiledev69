"""Stage factual Honda BigWing catalog/spec data for human review before RAG ingest."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


ROOT = Path(__file__).resolve().parents[1]
CATALOG_URL = "https://www.thaihonda.co.th/hondabigbike/motorcycle"
HOST = "www.thaihonda.co.th"
USER_AGENT = "THE_X-MotorcycleCatalog/0.1"
MAX_HTML_BYTES = 1_000_000
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "param", "source", "track", "wbr"}


class Element:
    def __init__(self, tag="root", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def find_all(self, tag):
        for child in self.children:
            if isinstance(child, Element):
                if child.tag == tag:
                    yield child
                yield from child.find_all(tag)

    def direct_child(self, tag, class_name=None):
        return next((child for child in self.children if isinstance(child, Element)
                     and child.tag == tag and (class_name is None or child.has_class(class_name))), None)

    def text(self):
        return " ".join(" ".join(part.text().split()) if isinstance(part, Element)
                        else " ".join(part.split()) for part in self.children).strip()


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = Element(tag, attrs)
        self.stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(raw):
    parser = TreeParser()
    parser.feed(raw.decode("utf-8-sig", errors="replace"))
    return parser.root


def allowed_detail_url(url):
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    return (parsed.scheme == "https" and parsed.netloc == HOST and not parsed.query
            and not parsed.fragment and len(parts) == 4 and
            parts[:2] == ["hondabigbike", "motorcycle"] and
            all(re.fullmatch(r"[a-z0-9-]+", part) for part in parts[2:]))


def parse_catalog(raw):
    root = parse_html(raw)
    models = []
    seen = set()
    for anchor in root.find_all("a"):
        url = anchor.attrs.get("href", "")
        name_node = next((child for child in anchor.find_all("span") if child.has_class("product-name")), None)
        if not allowed_detail_url(url) or name_node is None or url in seen:
            continue
        seen.add(url)
        price_node = next((child for child in anchor.find_all("span") if child.has_class("price")), None)
        parts = urlparse(url).path.strip("/").split("/")
        year_match = re.search(r"-(20\d{2})$", parts[-1])
        models.append({"name": name_node.text(), "category": parts[-2],
                       "source_url": url, "url_year_hint": int(year_match.group(1)) if year_match else None,
                       "display_price_at_fetch": price_node.text() if price_node else None})
    return models


def parse_detail(raw):
    root = parse_html(raw)
    spec = next((node for node in root.find_all("div") if node.has_class("spec")), None)
    if spec is None:
        return []
    result = []
    for section in spec.find_all("li"):
        heading = section.direct_child("div", "accordion-title")
        if heading is None:
            continue
        group = heading.text()
        for row in section.find_all("tr"):
            cells = [cell.text() for cell in row.children if isinstance(cell, Element) and cell.tag == "td"]
            if len(cells) == 2 and cells[0] and cells[1] and cells[1] != "-":
                result.append({"group": group, "label": cells[0], "value": cells[1]})
    return result


def detail_name(raw):
    text = raw.decode("utf-8-sig", errors="replace")
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if title:
        return re.sub(r"^Honda\s*-\s*", "", unescape(title.group(1)).strip(), flags=re.I)
    match = re.search(r"_bikeModel\s*=\s*'((?:\\.|[^'])*)'", text)
    return match.group(1).replace("\\'", "'") if match else None


def normalized_model_name(value):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\bnew\b", "", value.lower()))


def fetch(url, robots):
    if not robots.can_fetch(USER_AGENT, url):
        raise ValueError(f"robots.txt disallows {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=20) as response:
        if response.geturl() != url or "text/html" not in response.headers.get("Content-Type", ""):
            raise ValueError(f"Unexpected redirect or content type for {url}")
        raw = response.read(MAX_HTML_BYTES + 1)
    if len(raw) > MAX_HTML_BYTES:
        raise ValueError(f"HTML exceeds {MAX_HTML_BYTES} bytes: {url}")
    return raw


def cache_path(directory, url):
    return directory / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:20] + ".html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local" / "honda-bigwing")
    parser.add_argument("--max-models", type=int, default=0, help="0 means every catalog entry")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests, at least 1")
    parser.add_argument("--offline", action="store_true", help="Parse cached HTML without network requests")
    args = parser.parse_args()
    if args.max_models < 0 or args.delay < 1:
        parser.error("--max-models must be >= 0 and --delay must be >= 1")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw"
    raw_dir.mkdir(exist_ok=True)
    target = output / "catalog.json"
    previous = json.loads(target.read_text(encoding="utf-8")) if args.offline and target.exists() else {}
    robots = RobotFileParser()
    robots_status = previous.get("robots_status", "offline")
    if not args.offline:
        robots_url = f"https://{HOST}/robots.txt"
        try:
            with urlopen(Request(robots_url, headers={"User-Agent": USER_AGENT}), timeout=20) as response:
                robots.parse(response.read(100_000).decode("utf-8", errors="replace").splitlines())
            robots_status = "read"
        except HTTPError as exc:
            if exc.code != 404:
                raise
            robots.parse([])
            robots_status = "404"
    def get(url):
        path = cache_path(raw_dir, url)
        if args.offline:
            return path.read_bytes()
        data = fetch(url, robots)
        path.write_bytes(data)
        return data

    catalog_raw = get(CATALOG_URL)
    models = parse_catalog(catalog_raw)
    if not models:
        raise SystemExit("No model links found; check the site layout before ingesting anything.")
    total = len(models)
    if args.max_models:
        models = models[:args.max_models]
    records = []
    for model in models:
        if not args.offline:
            time.sleep(args.delay)
        url = model["source_url"]
        try:
            raw = get(url)
            specifications = parse_detail(raw)
            page_name = detail_name(raw)
            flags = []
            if not specifications:
                flags.append("no_specifications_found")
            if model["url_year_hint"] is None:
                flags.append("year_not_in_url")
            if not page_name:
                flags.append("detail_name_missing")
            elif normalized_model_name(page_name) != normalized_model_name(model["name"]):
                flags.append("catalog_detail_name_mismatch")
            records.append({**model, "source_sha256": hashlib.sha256(raw).hexdigest(),
                            "detail_name": page_name, "specifications": specifications,
                            "review_status": "pending", "review_flags": flags})
        except (HTTPError, URLError, OSError, ValueError) as exc:
            records.append({**model, "specifications": [], "review_status": "pending",
                            "review_flags": [f"fetch_error:{type(exc).__name__}"]})
            if isinstance(exc, HTTPError) and exc.code in (429, 503):
                break
    now = datetime.now(timezone.utc).isoformat()
    manifest = {"source": CATALOG_URL, "fetched_at_utc": previous.get("fetched_at_utc", now) if args.offline else now,
                "processed_at_utc": now,
                "robots_status": robots_status, "catalog_sha256": hashlib.sha256(catalog_raw).hexdigest(),
                "catalog_count": total, "records": records}
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_path = output / "review.csv"
    previous_reviews = {}
    if review_path.exists():
        with review_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            previous_reviews = {(row.get("source_url"), row.get("source_sha256")): row
                                for row in csv.DictReader(csv_file)}
    with review_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["name", "detail_name", "category", "url_year_hint",
                                                      "display_price_at_fetch", "spec_count", "review_flags",
                                                      "source_url", "source_sha256", "approved", "review_notes"])
        writer.writeheader()
        for record in records:
            prior = previous_reviews.get((record["source_url"], record.get("source_sha256")), {})
            writer.writerow({key: record.get(key) for key in writer.fieldnames if key not in
                             {"spec_count", "review_flags", "approved", "review_notes"}} | {
                                 "spec_count": len(record["specifications"]),
                                 "review_flags": ",".join(record["review_flags"]),
                                 "approved": prior.get("approved", ""),
                                 "review_notes": prior.get("review_notes", "")})
    print(f"Discovered {total} models; staged {len(records)} in {target}.")
    print(f"Models with specs: {sum(bool(record['specifications']) for record in records)}; all pending review.")
    print(f"Manual review flags: {sum(bool(record['review_flags']) for record in records)}; see review.csv.")
    if len(records) != len(models) or any(not record["specifications"] for record in records):
        raise SystemExit("Some pages need inspection; see review_flags in catalog.json.")


if __name__ == "__main__":
    main()
