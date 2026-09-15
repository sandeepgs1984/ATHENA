import urllib.request
import urllib.parse
from http.cookiejar import CookieJar
import json
import ssl
import sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(CookieJar()),
    urllib.request.HTTPSHandler(context=ctx)
)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def test_nse():
    print("Testing NSE endpoints...")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    # Step 1: get cookies from home page
    try:
        req = urllib.request.Request("https://www.nseindia.com", headers=headers)
        with opener.open(req, timeout=15) as resp:
            print("NSE Home status:", resp.status)
    except Exception as e:
        print("NSE Home failed:", e)
        return

    # Step 2: query financial results or announcements
    api_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    endpoints = [
        ("Announcements", "https://www.nseindia.com/api/corporate-announcements?index=equities"),
        ("Financial Results", "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly"),
        ("Shareholding", "https://www.nseindia.com/api/corporates-share-holding-pattern?index=equities"),
        ("Quote INFY Results", "https://www.nseindia.com/api/results-comparision?symbol=INFY"),
    ]
    for name, url in endpoints:
        try:
            req = urllib.request.Request(url, headers=api_headers)
            with opener.open(req, timeout=15) as resp:
                data = resp.read()
                ct = resp.headers.get("Content-Type", "")
                print(f"NSE {name}: status={resp.status}, size={len(data)} bytes, ct={ct}")
                try:
                    js = json.loads(data.decode("utf-8-sig"))
                    if isinstance(js, list):
                        print(f"  -> JSON array with {len(js)} items. First item keys: {list(js[0].keys()) if js else 'empty'}")
                    elif isinstance(js, dict):
                        print(f"  -> JSON dict keys: {list(js.keys())}")
                except Exception as ex:
                    print(f"  -> Decode error: {ex}")
        except Exception as e:
            print(f"NSE {name} failed:", e)

def test_bse():
    print("\nTesting BSE endpoints...")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.bseindia.com/",
        "Origin": "https://www.bseindia.com",
    }
    endpoints = [
        ("BSE Announcements", "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate=20240910&strScrip=&strSearch=P&strToDate=20240915&strType=C"),
        ("BSE Financial Results INFY", "https://api.bseindia.com/BseIndiaAPI/api/FinancialResult/w?scripcode=500209"),
        ("BSE Shareholding INFY", "https://api.bseindia.com/BseIndiaAPI/api/ShareholdingPattern/w?scripcode=500209"),
    ]
    for name, url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                print(f"BSE {name}: status={resp.status}, size={len(data)} bytes")
                try:
                    js = json.loads(data.decode("utf-8"))
                    if isinstance(js, list):
                        print(f"  -> JSON array with {len(js)} items.")
                    elif isinstance(js, dict):
                        print(f"  -> JSON dict keys: {list(js.keys())}")
                except Exception as ex:
                    print(f"  -> Note: not plain JSON: {ex}")
        except Exception as e:
            print(f"BSE {name} failed:", e)

if __name__ == "__main__":
    test_nse()
    test_bse()
