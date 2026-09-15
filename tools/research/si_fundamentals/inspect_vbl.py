"""Inspect VBL corporate action / share count in XBRL."""

import ssl
import urllib.request
import xml.etree.ElementTree as ET

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# VBL XBRL URL from our previous scan:
url = "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_119394_1376694_10022025052608.xml"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
    content = resp.read()

root = ET.fromstring(content)
for child in root:
    tag = child.tag.split("}")[-1]
    if tag in (
        "PaidUpValueOfEquityShareCapital",
        "FaceValueOfEquityShareCapital",
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
    ):
        c_ref = child.attrib.get("contextRef")
        print(f"VBL {tag} [{c_ref}]: {child.text}")
