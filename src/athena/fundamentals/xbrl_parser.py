"""Production XBRL/XML parser for official exchange filings (SI-F2B).

Follows ATHENA frozen decisions:
- D1: Layer 1 raw fact extraction.
- D2: Raw occurrence identity (document_id, source_occurrence_ordinal).
- D4: Period-safe duration coordinates (period_start, period_end).
- D5: Full raw dimension preservation.
- D11: Secure XML parsing using defusedxml.ElementTree.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    import defusedxml.ElementTree as ET

    _HAS_DEFUSEDXML = True
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore[no-redef]

    _HAS_DEFUSEDXML = False

from athena.domain.enums import FinancialUnitClass, RawPeriodType
from athena.domain.fundamentals import MAX_RAW_DOCUMENT_SIZE_BYTES, RawFinancialFact

XBRL_INSTANCE_NS = "http://www.xbrl.org/2003/instance"
XBRL_DIM_NS = "http://xbrl.org/2006/xbrldi"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def parse_xbrl_document(
    *,
    document_id: str,
    filing_id: str,
    raw_bytes: bytes,
) -> list[RawFinancialFact]:
    """Parse raw uncompressed XBRL document bytes into Layer 1 RawFinancialFact observations.

    Enforces:
    - Strict 20 MB bounded size check.
    - Secure XML parsing against entity expansion and DTDs via defusedxml.
    - Sequential 1-based source_occurrence_ordinal in physical XML document order.
    - Exact signed Decimals without binary float rounding.
    - Lossless context, period, unit, nil, and dimension extraction.
    """
    if len(raw_bytes) > MAX_RAW_DOCUMENT_SIZE_BYTES:
        raise ValueError(
            f"Raw document size ({len(raw_bytes)} bytes) exceeds MAX_RAW_DOCUMENT_SIZE_BYTES "
            f"({MAX_RAW_DOCUMENT_SIZE_BYTES} bytes)"
        )

    if not _HAS_DEFUSEDXML and (b"<!DOCTYPE" in raw_bytes or b"<!ENTITY" in raw_bytes):
        raise ValueError(
            f"Secure XML parsing failed for document {document_id!r}: "
            "DTD and entity declarations are prohibited"
        )

    try:
        root = ET.fromstring(raw_bytes)
    except Exception as exc:
        raise ValueError(f"Secure XML parsing failed for document {document_id!r}: {exc}") from exc

    # 1. Extract and semantically classify contexts (Context IDs are opaque tokens)
    contexts: dict[str, dict[str, Any]] = {}
    for elem in root.findall(f"{{{XBRL_INSTANCE_NS}}}context"):
        cid = elem.attrib.get("id", "")
        if not cid:
            continue

        period_elem = elem.find(f"{{{XBRL_INSTANCE_NS}}}period")
        cdata: dict[str, Any] = {
            "period_type": RawPeriodType.UNKNOWN,
            "period_start": None,
            "period_end": None,
            "duration_days": None,
        }

        if period_elem is not None:
            instant = period_elem.find(f"{{{XBRL_INSTANCE_NS}}}instant")
            if instant is not None and instant.text and instant.text.strip():
                cdata["period_type"] = RawPeriodType.INSTANT
                cdata["period_end"] = date.fromisoformat(instant.text.strip())
                cdata["period_start"] = None
                cdata["duration_days"] = None
            else:
                start_elem = period_elem.find(f"{{{XBRL_INSTANCE_NS}}}startDate")
                end_elem = period_elem.find(f"{{{XBRL_INSTANCE_NS}}}endDate")
                if (
                    start_elem is not None
                    and end_elem is not None
                    and start_elem.text
                    and end_elem.text
                    and start_elem.text.strip()
                    and end_elem.text.strip()
                ):
                    s_date = date.fromisoformat(start_elem.text.strip())
                    e_date = date.fromisoformat(end_elem.text.strip())
                    if s_date > e_date:
                        raise ValueError(
                            f"Context {cid!r} has period startDate ({s_date}) after endDate ({e_date})"
                        )
                    cdata["period_type"] = RawPeriodType.DURATION
                    cdata["period_start"] = s_date
                    cdata["period_end"] = e_date
                    cdata["duration_days"] = (e_date - s_date).days + 1

        # Extract dimensions from scenario or segment (explicit and typed)
        dimensions: list[dict[str, str]] = []
        for container_name in ("scenario", "segment"):
            container = elem.find(f"{{{XBRL_INSTANCE_NS}}}{container_name}")
            if container is not None:
                for member in container.findall(f"{{{XBRL_DIM_NS}}}explicitMember"):
                    dim = member.attrib.get("dimension", "").strip()
                    val = (member.text or "").strip()
                    if dim:
                        dimensions.append({
                            "kind": "explicit",
                            "dimension": dim,
                            "member": val,
                        })
                for member in container.findall(f"{{{XBRL_DIM_NS}}}typedMember"):
                    dim = member.attrib.get("dimension", "").strip()
                    child_chunks = [ET.tostring(c, encoding="unicode").strip() for c in member]
                    raw_content = "".join(child_chunks) if child_chunks else (member.text or "").strip()
                    if dim:
                        dimensions.append({
                            "kind": "typed",
                            "dimension": dim,
                            "raw_content": raw_content,
                        })

        sorted_dims = sorted(
            dimensions,
            key=lambda d: (
                d.get("kind", ""),
                d.get("dimension", ""),
                d.get("member", ""),
                d.get("raw_content", ""),
            ),
        )
        cdata["is_dimensioned"] = len(sorted_dims) > 0
        cdata["dimensions"] = tuple(sorted_dims)
        cdata["dimension_signature"] = json.dumps(sorted_dims, sort_keys=True) if sorted_dims else ""
        contexts[cid] = cdata

    # 2. Extract unit definitions
    units: dict[str, dict[str, Any]] = {}
    for elem in root.findall(f"{{{XBRL_INSTANCE_NS}}}unit"):
        uid = elem.attrib.get("id", "")
        if not uid:
            continue

        measure = elem.find(f"{{{XBRL_INSTANCE_NS}}}measure")
        divide = elem.find(f"{{{XBRL_INSTANCE_NS}}}divide")
        if measure is not None and measure.text and measure.text.strip():
            m_text = measure.text.strip()
            u_class = FinancialUnitClass.UNKNOWN
            m_upper = m_text.upper()
            if "INR" in m_upper or "ISO4217:INR" in m_upper:
                u_class = FinancialUnitClass.CURRENCY
            elif "SHARES" in m_upper:
                u_class = FinancialUnitClass.SHARES
            elif "PURE" in m_upper:
                u_class = FinancialUnitClass.PURE

            units[uid] = {
                "unit_id": uid,
                "raw_unit_identity": m_text,
                "unit_class": u_class,
            }
        elif divide is not None:
            num = divide.find(f"{{{XBRL_INSTANCE_NS}}}unitNumerator/{{{XBRL_INSTANCE_NS}}}measure")
            den = divide.find(f"{{{XBRL_INSTANCE_NS}}}unitDenominator/{{{XBRL_INSTANCE_NS}}}measure")
            num_text = (num.text or "").strip() if num is not None else ""
            den_text = (den.text or "").strip() if den is not None else ""
            raw_ident = f"{num_text}/{den_text}"

            u_class = FinancialUnitClass.UNKNOWN
            if "INR" in num_text.upper() and "SHARES" in den_text.upper():
                u_class = FinancialUnitClass.CURRENCY_PER_SHARE

            units[uid] = {
                "unit_id": uid,
                "raw_unit_identity": raw_ident,
                "unit_class": u_class,
            }

    # 3. Extract Fact elements in physical XML document order
    raw_facts: list[RawFinancialFact] = []
    occurrence_ordinal = 0

    for elem in root:
        tag = elem.tag
        # Skip top-level XBRL infrastructure elements
        if tag.startswith(f"{{{XBRL_INSTANCE_NS}}}"):
            continue

        occurrence_ordinal += 1

        if tag.startswith("{"):
            ns_uri, local_name = tag[1:].split("}", 1)
        else:
            ns_uri, local_name = "", tag

        cref = elem.attrib.get("contextRef", "").strip()
        if not cref:
            raise ValueError(
                f"Document {document_id!r} occurrence {occurrence_ordinal} ({local_name}) "
                f"missing mandatory contextRef"
            )

        c_info = contexts.get(cref)
        if c_info is None:
            raise ValueError(
                f"Document {document_id!r} occurrence {occurrence_ordinal} ({local_name}) "
                f"references non-existent contextRef {cref!r}"
            )

        uref = elem.attrib.get("unitRef")
        u_info = units.get(uref) if uref else None

        decimals = elem.attrib.get("decimals")
        precision = elem.attrib.get("precision")
        is_nil = elem.attrib.get(f"{{{XSI_NS}}}nil") == "true"
        raw_val = (elem.text or "").strip()

        numeric_val: Decimal | None = None
        if not is_nil and raw_val:
            try:
                numeric_val = Decimal(raw_val)
            except InvalidOperation:
                numeric_val = None

        if c_info["period_end"] is None:
            raise ValueError(
                f"Document {document_id!r} contextRef {cref!r} has no valid period_end date"
            )

        fact = RawFinancialFact(
            raw_fact_id=f"{document_id}:{occurrence_ordinal}",
            filing_id=filing_id,
            document_id=document_id,
            source_occurrence_ordinal=occurrence_ordinal,
            namespace_uri=ns_uri,
            local_name=local_name,
            raw_qname=f"{{{ns_uri}}}{local_name}",
            context_ref=cref,
            period_type=c_info["period_type"],
            period_start=c_info["period_start"],
            period_end=c_info["period_end"],
            duration_days=c_info["duration_days"],
            unit_ref=uref,
            raw_unit_identity=u_info["raw_unit_identity"] if u_info else None,
            unit_class=u_info["unit_class"] if u_info else FinancialUnitClass.UNKNOWN,
            decimals=decimals,
            precision=precision,
            is_nil=is_nil,
            raw_value=raw_val,
            numeric_value=numeric_val,
            is_dimensioned=c_info["is_dimensioned"],
            dimension_signature=c_info["dimension_signature"],
            dimensions=c_info["dimensions"],
        )
        raw_facts.append(fact)

    return raw_facts
