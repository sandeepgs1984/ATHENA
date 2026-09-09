
    // ID-11: Owner-facing Intraday Plan — GET /decisions/{id}/intraday-intelligence,
    // fetched once when a Decision Brief opens (never attached to the
    // existing 10s live-price poll: the design contract explicitly forbids
    // wiring this into that loop, since it is a materially heavier local
    // recompute than a quote read). Renders qualification/actionability/
    // sizing/live-supervision as one coherent card, clearly separate from
    // the Structural Plan (legacy TradePlan) shown elsewhere on this brief.
    // Never dumps raw JSON/internal enums — every state maps through a
    // small deterministic label table below.

    const INTRADAY_PLAN_CARD = document.getElementById("intraday-plan-card");
    const INTRADAY_PLAN_ASOF = document.getElementById("intraday-plan-asof");
    const INTRADAY_PLAN_QUALIFICATION = document.getElementById("intraday-plan-qualification");
    const INTRADAY_PLAN_ACTIONABILITY = document.getElementById("intraday-plan-actionability");
    const INTRADAY_PLAN_ENTRY_DETAILS = document.getElementById("intraday-plan-entry-details");
    const INTRADAY_PLAN_ENTRY_PRICE = document.getElementById("intraday-plan-entry-price");
    const INTRADAY_PLAN_INVALIDATION = document.getElementById("intraday-plan-invalidation");
    const INTRADAY_PLAN_T1 = document.getElementById("intraday-plan-t1");
    const INTRADAY_PLAN_T2 = document.getElementById("intraday-plan-t2");
    const INTRADAY_PLAN_SIZING = document.getElementById("intraday-plan-sizing");
    const INTRADAY_PLAN_SUPERVISION = document.getElementById("intraday-plan-supervision");
    const INTRADAY_PLAN_FRESHNESS = document.getElementById("intraday-plan-freshness");

    const INTRADAY_QUALIFICATION_LABELS = {
        QUALIFIED: { label: "Qualified", tone: "good" },
        NOT_YET: { label: "Waiting", tone: "neutral" },
        UNKNOWN: { label: "Unknown", tone: "neutral" },
        DISQUALIFIED_FOR_SESSION: { label: "Disqualified", tone: "bad" },
        EXPIRED: { label: "Expired", tone: "bad" },
        OUT_OF_SCOPE: { label: "Not applicable", tone: "neutral" },
        UNAVAILABLE: { label: "Not available", tone: "neutral" },
    };

    const INTRADAY_ACTIONABILITY_LABELS = {
        ACTIONABLE: { label: "Actionable", tone: "good" },
        NOT_ACTIONABLE: { label: "Not actionable", tone: "neutral" },
        UNKNOWN: { label: "Unknown", tone: "neutral" },
        UNAVAILABLE: { label: "Not available", tone: "neutral" },
    };

    const INTRADAY_SIZING_LABELS = {
        SIZED: { label: "Suggested", tone: "good" },
        NOT_SIZED: { label: "Not sized", tone: "neutral" },
        ZERO_QUANTITY_UNDER_POLICY: { label: "Zero under policy", tone: "warn" },
        UNAVAILABLE: { label: "Not available", tone: "neutral" },
    };

    const INTRADAY_SUPERVISION_LABELS = {
        VALID: { label: "Plan valid", tone: "good" },
        INVALIDATED: { label: "Invalidated", tone: "bad" },
        NOT_APPLICABLE: { label: "Not applicable", tone: "neutral" },
        UNAVAILABLE: { label: "Not available", tone: "neutral" },
    };

    // A short, deterministic reason phrase for the reason codes this API
    // can actually produce (comma-joined engine reason-code values) — never
    // a generative/free-text explanation.
    const INTRADAY_REASON_PHRASES = {
        UPSTREAM_NOT_ACTIONABLE: "upstream not actionable",
        UPSTREAM_DECISION_NOT_TRADE: "Decision is not TRADE",
        UPSTREAM_EQ_NOT_QUALIFIED: "qualification not met",
        INSUFFICIENT_EVIDENCE: "insufficient evidence",
        INVALIDATION_UNAVAILABLE: "invalidation unavailable",
        UNVALIDATED_DIRECTION: "SHORT direction not yet validated",
        UPSTREAM_NOT_CURRENT: "evidence no longer current",
        CAPITAL_POLICY_UNAVAILABLE: "sizing policy not configured",
        INVALID_RISK_GEOMETRY: "risk geometry invalid",
        ZERO_QUANTITY_UNDER_POLICY: "every constraint floors to zero",
        VWAP_LOSS: "closed below session VWAP",
    };

    function intradayReasonPhrase(reasonCsv) {
        if (!reasonCsv) return "";
        const codes = String(reasonCsv).split(",").map(c => c.trim()).filter(Boolean);
        if (!codes.length) return "";
        return codes.map(c => INTRADAY_REASON_PHRASES[c] || c).join(" · ");
    }

    function intradayApplyTone(el, tone) {
        if (!el) return;
        el.className = `intraday-plan-value tone-${tone || "neutral"}`;
    }

    function intradayFormatMoney(value) {
        if (value === null || value === undefined) return "—";
        const num = Number(value);
        return Number.isFinite(num) ? `₹${num.toFixed(2)}` : "—";
    }

    function intradayFormatTime(iso) {
        if (!iso) return null;
        const d = new Date(iso);
        return Number.isNaN(d.getTime())
            ? null
            : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function resetIntradayPlanCard() {
        if (INTRADAY_PLAN_CARD) INTRADAY_PLAN_CARD.style.display = "none";
    }

    function renderIntradayPlan(data) {
        if (!INTRADAY_PLAN_CARD) return;
        if (!data) {
            resetIntradayPlanCard();
            return;
        }
        INTRADAY_PLAN_CARD.style.display = "";

        const qualification = data.qualification || {};
        const qView = INTRADAY_QUALIFICATION_LABELS[qualification.state] || INTRADAY_QUALIFICATION_LABELS.UNAVAILABLE;
        if (INTRADAY_PLAN_QUALIFICATION) {
            INTRADAY_PLAN_QUALIFICATION.textContent = qView.label;
            INTRADAY_PLAN_QUALIFICATION.title = qualification.evidence_summary || "";
            intradayApplyTone(INTRADAY_PLAN_QUALIFICATION, qView.tone);
        }

        const actionability = data.actionability || {};
        const aView = INTRADAY_ACTIONABILITY_LABELS[actionability.state] || INTRADAY_ACTIONABILITY_LABELS.UNAVAILABLE;
        if (INTRADAY_PLAN_ACTIONABILITY) {
            const reasonPhrase = intradayReasonPhrase(actionability.reason);
            INTRADAY_PLAN_ACTIONABILITY.textContent = aView.label;
            INTRADAY_PLAN_ACTIONABILITY.title = reasonPhrase
                ? `${aView.label} — ${reasonPhrase} (currentness: ${actionability.currentness || "UNAVAILABLE"})`
                : `currentness: ${actionability.currentness || "UNAVAILABLE"}`;
            intradayApplyTone(INTRADAY_PLAN_ACTIONABILITY, aView.tone);
        }

        const showEntryDetails = actionability.state === "ACTIONABLE" && actionability.entry_reference != null;
        if (INTRADAY_PLAN_ENTRY_DETAILS) INTRADAY_PLAN_ENTRY_DETAILS.hidden = !showEntryDetails;
        if (showEntryDetails) {
            if (INTRADAY_PLAN_ENTRY_PRICE) INTRADAY_PLAN_ENTRY_PRICE.textContent = intradayFormatMoney(actionability.entry_reference);
            if (INTRADAY_PLAN_INVALIDATION) {
                const inv = actionability.operative_invalidation;
                INTRADAY_PLAN_INVALIDATION.textContent = inv ? intradayFormatMoney(inv.level) : "—";
            }
            if (INTRADAY_PLAN_T1) INTRADAY_PLAN_T1.textContent = intradayFormatMoney(actionability.t1);
            if (INTRADAY_PLAN_T2) INTRADAY_PLAN_T2.textContent = intradayFormatMoney(actionability.t2);
        }

        const sizing = data.sizing || {};
        const sView = INTRADAY_SIZING_LABELS[sizing.state] || INTRADAY_SIZING_LABELS.UNAVAILABLE;
        if (INTRADAY_PLAN_SIZING) {
            const qty = sizing.suggested_quantity;
            const reasonPhrase = intradayReasonPhrase(sizing.reason);
            if (sizing.state === "SIZED" && qty != null) {
                INTRADAY_PLAN_SIZING.textContent = `Qty ${qty}${sizing.binding_constraint ? ` (${sizing.binding_constraint.replace(/_/g, " ").toLowerCase()})` : ""}`;
            } else {
                INTRADAY_PLAN_SIZING.textContent = sView.label;
            }
            INTRADAY_PLAN_SIZING.title = reasonPhrase || sView.label;
            intradayApplyTone(INTRADAY_PLAN_SIZING, sView.tone);
        }

        const supervision = data.supervision || {};
        const svView = INTRADAY_SUPERVISION_LABELS[supervision.state] || INTRADAY_SUPERVISION_LABELS.UNAVAILABLE;
        if (INTRADAY_PLAN_SUPERVISION) {
            const targetProgress = supervision.target_progress;
            const progressSuffix = targetProgress && targetProgress !== "UNAVAILABLE" && targetProgress !== "NONE_REACHED"
                ? ` · ${targetProgress.replace(/_/g, " ").toLowerCase()}`
                : "";
            INTRADAY_PLAN_SUPERVISION.textContent = `${svView.label}${progressSuffix}`;
            const reasonPhrase = intradayReasonPhrase(supervision.reason);
            INTRADAY_PLAN_SUPERVISION.title = reasonPhrase || svView.label;
            intradayApplyTone(INTRADAY_PLAN_SUPERVISION, svView.tone);
        }

        if (INTRADAY_PLAN_ASOF) {
            const asOfSummary = data.as_of_summary || {};
            const t = intradayFormatTime(asOfSummary.computed_at);
            INTRADAY_PLAN_ASOF.textContent = t ? `As of ${t}` : "";
        }
        if (INTRADAY_PLAN_FRESHNESS) {
            const currentness = actionability.currentness;
            INTRADAY_PLAN_FRESHNESS.textContent = currentness && currentness !== "UNAVAILABLE"
                ? `Intraday currentness: ${currentness.replace(/_/g, " ").toLowerCase()}`
                : "";
        }
    }

    async function loadIntradayPlan(decisionId) {
        if (!INTRADAY_PLAN_CARD) return;
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/intraday-intelligence`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            renderIntradayPlan(response && response.data);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load intraday plan for ${decisionId}`, err);
            resetIntradayPlanCard();
        }
    }
