"""Pull the current inventory off waltsautosales.net and write inventory.json.

Run hourly by .github/workflows/inventory.yml. Vehicle data only (stock, VIN,
year/make/model, miles, price) - the same things the public website shows.
"""
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

LIST_URL = "https://waltsautosales.net/newandusedcars?pagesize=500"
SITEMAP_URL = "https://waltsautosales.net/sitemap"
SITE = "https://waltsautosales.net"
OUT = sys.argv[1] if len(sys.argv) > 1 else "inventory.json"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (WaltsLotWalk)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def field(chunk, label):
    m = re.search(r"<label[^>]*>\s*" + label + r":\s*</label>\s*([^<]*)", chunk, re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def parse(page):
    cars = {}
    # Each listing card starts at its hidden compare link.
    for chunk in page.split('id="compareVdpLink_')[1:]:
        vin = field(chunk, "VIN").upper()
        if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin) or vin in cars:
            continue
        m_id = re.match(r"(\d+)", chunk)
        m_title = re.search(r'aria-label="([^"]+)"', chunk)
        m_href = re.search(r'href="(/vdp/[^"]+)"', chunk)
        m_price = re.search(r"compareChecked\(this, '\d+', '([^']*)'", chunk)
        # The card's photo sits before its compare link, so look it up by listing id.
        m_img = m_id and re.search(r'data-src="([^"]+/Media/\d+/' + m_id.group(1) + r'/[^"]+)"', page)
        title = html.unescape(m_title.group(1)).strip() if m_title else ""
        cars[vin] = {
            "vin": vin,
            "stock": field(chunk, "Stock #"),
            "title": title,
            "miles": field(chunk, "Mileage"),
            "price": m_price.group(1) if m_price else "",
            "url": SITE + m_href.group(1) if m_href else "",
            "img": m_img.group(1) if m_img else "",
            "id": m_id.group(1) if m_id else "",
        }
    return list(cars.values())


def main():
    cars = parse(get(LIST_URL))
    expected = len(set(re.findall(r"/vdp/(\d+)/", get(SITEMAP_URL))))
    print(f"parsed {len(cars)} cars, sitemap lists {expected}")
    # Never overwrite a good list with a broken scrape (site down, layout change).
    if len(cars) < 10 or (expected and len(cars) < expected * 0.9):
        sys.exit("scrape looks wrong - leaving inventory.json alone")
    cars.sort(key=lambda c: c["stock"])
    data = {
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(cars),
        "cars": cars,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


if __name__ == "__main__":
    main()
