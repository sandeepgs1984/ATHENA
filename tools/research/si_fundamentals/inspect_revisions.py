"""Inspect revision indicators and corporate action cases."""

import json
from pathlib import Path

EVIDENCE_FILE = Path("tools/research/si_fundamentals/spike_evidence.json")


def inspect_revisions():
    # Load previously fetched data if available, or query
    from spike_runner import create_nse_session, fetch_nse_results

    opener = create_nse_session()
    rows = fetch_nse_results(opener)

    re_ind_values = {}
    revised_rows = []
    for r in rows:
        val = r.get("reInd")
        re_ind_values[val] = re_ind_values.get(val, 0) + 1
        if val not in ("N", None, ""):
            revised_rows.append(r)

    print("Distribution of reInd in NSE feed:", re_ind_values)
    print(f"Total non-N reInd rows: {len(revised_rows)}")
    for r in revised_rows[:5]:
        sym = r.get("symbol")
        reInd = r.get("reInd")
        toDate = r.get("toDate")
        exchtime = r.get("exchdisstime")
        scope = r.get("consolidated")
        print(f"Symbol: {sym} | reInd: {reInd} | PeriodEnd: {toDate} | Scope: {scope} | Dissem: {exchtime}")
        print(f"  XBRL: {r.get('xbrl')}")


if __name__ == "__main__":
    inspect_revisions()
