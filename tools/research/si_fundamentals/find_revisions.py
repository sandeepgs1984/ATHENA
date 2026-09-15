"""Find duplicate/revised filings for the same symbol and period_end."""

from spike_runner import create_nse_session, fetch_nse_results

opener = create_nse_session()
rows = fetch_nse_results(opener)

by_key = {}
for r in rows:
    key = (r.get("symbol"), r.get("toDate"), r.get("consolidated"))
    by_key.setdefault(key, []).append(r)

multi = {k: v for k, v in by_key.items() if len(v) > 1}
print(f"Total symbol-period-scope groups with multiple filings: {len(multi)}")
for (sym, toDate, scope), items in list(multi.items())[:5]:
    print(f"\nSymbol: {sym} | Period: {toDate} | Scope: {scope} (Count: {len(items)})")
    for it in items:
        reInd = it.get("reInd")
        dissem = it.get("exchdisstime")
        seq = it.get("seqNumber")
        xb = it.get("xbrl")
        print(f"  seq={seq} | reInd={reInd} | dissem={dissem} | xbrl={xb}")
