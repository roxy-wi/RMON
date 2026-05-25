import asyncio
from playwright.async_api import async_playwright
from collections import defaultdict


async def audit_page_precise(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        resource_stats = defaultdict(lambda: {"count": 0, "bytes": 0})
        total_bytes = 0

        timings = {}

        async def handle_response(response):
            try:
                rtype = response.request.resource_type
                body = await response.body()
                size = len(body)
                resource_stats[rtype]["count"] += 1
                resource_stats[rtype]["bytes"] += size
                nonlocal total_bytes
                total_bytes += size
            except Exception:
                pass

        page.on("response", handle_response)

        # ⏱️ Start timing
        t0 = asyncio.get_event_loop().time()
        await page.goto(url, wait_until="networkidle")
        t1 = asyncio.get_event_loop().time()

        # ⏱️ Evaluate in page context
        timing = await page.evaluate(
            """() => {
                const t = performance.timing;
                return {
                    navigationStart: t.navigationStart,
                    domContentLoaded: t.domContentLoadedEventEnd,
                    load: t.loadEventEnd
                };
            }"""
        )

        base = timing["navigationStart"]
        timings["domcontentloaded"] = round((timing["domContentLoaded"] - base) / 1000, 3)
        timings["load"] = round((timing["load"] - base) / 1000, 3)
        timings["networkidle"] = round(t1 - t0, 3)

        dom_count = await page.evaluate("document.getElementsByTagName('*').length")

        await browser.close()

        return {
            "url": url,
            "timings": timings,
            "dom_elements": dom_count,
            "resource_stats": dict(resource_stats),
            "total_bytes": total_bytes
        }


def format_audit_result(result: dict):
    print("\n📄 Page Audit Report")
    print(f"🌐 URL: {result['url']}")
    print(f"🧱 DOM elements: {result['dom_elements']}")
    print(f"📦 Total loaded: {result['total_bytes'] / 1024:.2f} KB\n")

    print("⏱️ Timings:")
    for key, val in result["timings"].items():
        print(f"  - {key:<15}: {val:>5.3f} sec")

    print("\n📊 Resource Types:")
    print(f"{'Type':<12} | {'Count':>5} | {'Size (KB)':>10}")
    print("-" * 32)
    for rtype, stats in result["resource_stats"].items():
        print(f"{rtype:<12} | {stats['count']:>5} | {stats['bytes'] / 1024:>10.2f}")
    print("-" * 32)


from lighthouse import launch_lighthouse

report = launch_lighthouse(
    url="https://example.com",
    output="json",
    chrome_flags="--headless",
)

print(report)

# 🔍 Пример запуска
if __name__ == "__main__":
    url = "https://edgecenter.ru"
    result = asyncio.run(audit_page_precise(url))
    format_audit_result(result)


import requests
from datetime import datetime, timedelta
import pytz
from statistics import median


start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S%z")
end = (datetime.now() - timedelta(minutes=0)).strftime("%Y-%m-%dT%H:%M:%S%z")
vm = 'https://vmselect-infra.p.ecnl.ru/select/0/prometheus/api/v1'
req = f'{vm}/query_range?query=avg_over_time(EdgeMon_metrics{{check_id="16465"}}[1d])&start={start}&end={end}&step=1h'

resp = requests.get(req, verify=False)

# print(resp.json())
values = {}
for metric in resp.json()['data']['result']:
    values[metric['metric']['metric']] = []

    print(metric['metric'])
    for value in metric['values']:
        # date_time = datetime.fromtimestamp(value[0], tz=pytz.UTC).strftime('%Y-%m-%d %H:%M:%S%z')
        # print(f'{date_time} - {value[1]}')
        values[metric['metric']['metric']].append(value[1])

    print(values[metric['metric']['metric']])
    print(median(values[metric['metric']['metric']]))