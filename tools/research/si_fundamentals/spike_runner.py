"""SI-F0.1 Empirical Fundamentals Source Feasibility Spike Runner.

Isolated research tool for querying and verifying real Indian equity filings
across NSE and BSE APIs and official XBRL archives.
"""

from __future__ import annotations

import io
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

EVIDENCE_FILE = Path("tools/research/si_fundamentals/spike_evidence.json")


def create_nse_session() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    cj = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ctx),
    )

    page_url = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
    req = urllib.request.Request(
        page_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )
    with opener.open(req, timeout=20) as resp:
        _ = resp.read()
    return opener


def fetch_nse_results(opener: urllib.request.OpenerDirector) -> list[dict[str, Any]]:
    api_url = "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
        },
    )
    with opener.open(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def fetch_bse_announcements(scrip_code: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    url = (
        f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?"
        f"pageno=1&strCat=-1&strPrevDate={start_date}&strScrip={scrip_code}&strSearch=P&strToDate={end_date}&strType=C"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("Table", [])


def fetch_xbrl_elements(xbrl_url: str) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        xbrl_url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        content = resp.read()

    root = ET.fromstring(content)
    contexts: dict[str, str] = {}
    facts: list[dict[str, Any]] = []

    for child in root:
        tag = child.tag.split("}")[-1]
        if tag == "context":
            cid = child.attrib.get("id", "")
            period = child.find("{http://www.xbrl.org/2003/instance}period")
            p_str = ""
            if period is not None:
                for p_child in period:
                    p_tag = p_child.tag.split("}")[-1]
                    p_str += f"{p_tag}:{p_child.text} "
            contexts[cid] = p_str.strip()
        elif tag not in ("unit", "schemaRef"):
            val = (child.text or "").strip()
            if val:
                facts.append({
                    "tag": tag,
                    "context": child.attrib.get("contextRef"),
                    "unit": child.attrib.get("unitRef"),
                    "decimals": child.attrib.get("decimals"),
                    "value": val,
                })

    return {
        "url": xbrl_url,
        "byte_size": len(content),
        "root_tag": root.tag,
        "contexts": contexts,
        "facts_count": len(facts),
        "facts": facts,
    }


def main() -> None:
    print("=== STARTING SI-F0.1 EMPIRICAL SPIKE RUNNER ===")
    results_summary: dict[str, Any] = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "matrix_tests": {},
        "cross_exchange_comparison": {},
        "xbrl_inspections": {},
        "reconciliation_cases": {},
    }

    # Step 1: Query NSE Feed
    print("\n1. Querying Official NSE Financial Results Feed...")
    opener = create_nse_session()
    nse_rows = fetch_nse_results(opener)
    print(f"Total NSE financial results entries retrieved: {len(nse_rows)}")

    # Matrix symbols
    target_symbols = ["INFY", "TCS", "RELIANCE", "PAYTM", "IDEA", "VBL", "HDFCBANK"]
    indexed_nse: dict[str, list[dict[str, Any]]] = {s: [] for s in target_symbols}

    for row in nse_rows:
        sym = row.get("symbol")
        if sym in indexed_nse:
            indexed_nse[sym].append(row)

    # Log Matrix findings
    print("\n2. Company Validation Matrix Summary:")
    for sym, filings in indexed_nse.items():
        print(f"\n--- Symbol: {sym} (Filings count: {len(filings)}) ---")
        for f in filings:
            scope = f.get("consolidated")
            cumul = f.get("cumulative")
            audited = f.get("audited")
            to_date = f.get("toDate")
            dissem = f.get("exchdisstime")
            re_ind = f.get("reInd")
            xbrl = f.get("xbrl")
            bank = f.get("bank")
            print(f"  [{scope} | {cumul} | {audited}] End: {to_date} | Disseminated: {dissem} | Bank: {bank} | ReInd: {re_ind}")
            print(f"    XBRL: {xbrl}")

        results_summary["matrix_tests"][sym] = filings

    # Step 3: Inspect RAW XBRL for Selected Types
    print("\n3. Inspecting RAW XBRL Payloads...")
    inspections = [
        ("INFY_Consolidated", "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117292_1348213_16012025074012.xml"),
        ("PAYTM_LossMaker", "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117412_1353590_20012025063743.xml"),
        ("HDFCBANK_NegativeControl", "https://nsearchives.nseindia.com/corporate/xbrl/BANKING_117525_1359016_23012025122721.xml"),
    ]

    for label, url in inspections:
        print(f"\nFetching & parsing XBRL: {label}...")
        parsed = fetch_xbrl_elements(url)
        print(f"  Byte size: {parsed['byte_size']}, Contexts: {len(parsed['contexts'])}, Facts: {parsed['facts_count']}")

        # Filter key tags
        key_tags = [
            "RevenueFromOperations", "InterestEarned", "InterestExpended",
            "ProfitLossForPeriod", "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            "PaidUpValueOfEquityShareCapital", "FaceValueOfEquityShareCapital"
        ]
        sample_facts = [f for f in parsed["facts"] if f["tag"] in key_tags]
        for sf in sample_facts:
            print(f"    {sf['tag']} ({sf['context']}): {sf['value']} (unit={sf['unit']})")

        results_summary["xbrl_inspections"][label] = {
            "url": url,
            "byte_size": parsed["byte_size"],
            "contexts": parsed["contexts"],
            "sample_key_facts": sample_facts,
        }

    # Step 4: BSE Announcements & Reconciliation for INFY
    print("\n4. Querying BSE Corporate Announcements for INFY (500209)...")
    # Date when Q3 FY25 was announced: Jan 16, 2025
    bse_infy = fetch_bse_announcements("500209", "20250116", "20250116")
    print(f"BSE Announcements on Jan 16, 2025 for INFY: {len(bse_infy)}")
    for ann in bse_infy:
        print(f"  Headline: {ann.get('HEADLINE')}")
        print(f"  DissemDT: {ann.get('DissemDT')} | Category: {ann.get('CATEGORYNAME')} | Subcat: {ann.get('SUBCATNAME')}")
        print(f"  Attachment: {ann.get('ATTACHMENTNAME')}")

    results_summary["cross_exchange_comparison"]["INFY_20250116"] = {
        "bse_announcements": bse_infy,
        "nse_filings": indexed_nse.get("INFY", []),
    }

    # Step 5: Save JSON report
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_FILE, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
    print(f"\nSaved empirical evidence to {EVIDENCE_FILE} ({EVIDENCE_FILE.stat().st_size} bytes)")
    print("=== SPIKE RUN COMPLETE ===")


if __name__ == "__main__":
    main()
