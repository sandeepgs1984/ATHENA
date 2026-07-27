

    function decisionScoreValue(d) {
        const fromText = extractScoreFromText(d.explanation || "");
        if (fromText != null) return Number(fromText);
        return -1;
    }

    const DECISION_TYPE_PRIORITY = { TRADE: 0, WATCH: 1, NO_TRADE: 2, INSUFFICIENT_DATA: 3 };
    function decisionTypePriority(d) {
        const t = String((d.metadata && d.metadata.decision_type) || "").toUpperCase();
        return DECISION_TYPE_PRIORITY[t] ?? 9;
    }

    function formatVolatilityLabel(volStr) {
        const key = String(volStr || "").toUpperCase();
        const map = {
            HIGH_VOLATILITY: { label: "High", cls: "bear", hint: "India VIX above high band" },
            LOW_VOLATILITY: { label: "Low", cls: "bull", hint: "India VIX below low band" },
            NORMAL_VOLATILITY: { label: "Normal", cls: "neutral", hint: "India VIX in normal band" },
            VOLATILITY_UNKNOWN: {
                label: "Unknown",
                cls: "neutral",
                hint: "India VIX was not in the market snapshot — re-run validate/smoke after this update",
            },
            UNKNOWN: {
                label: "Unknown",
                cls: "neutral",
                hint: "Volatility not assessed yet",
            },
        };
        if (map[key]) return map[key];
        const cleaned = key.replace(/_VOLATILITY$/, "").replace(/_/g, " ");
        return { label: cleaned || "Unknown", cls: "neutral", hint: "" };
    }

    function decisionStance(type, direction) {
        const t = String(type || "").toUpperCase();
        const dir = String(direction || "NONE").toUpperCase();
        if (t === "TRADE" && dir === "LONG") return { label: "BUY", cls: "stance-buy" };
        if (t === "TRADE" && dir === "SHORT") return { label: "SELL", cls: "stance-sell" };
        if (t === "TRADE") return { label: "TRADE", cls: "stance-buy" };
        if (t === "WATCH") return { label: "HOLD", cls: "stance-hold" };
        if (t === "NO_TRADE") return { label: "PASS", cls: "stance-pass" };
        if (t === "INSUFFICIENT_DATA") return { label: "WAIT", cls: "stance-wait" };
        return { label: t || "—", cls: "stance-pass" };
    }

    function friendlyGateName(gate) {
        const map = {
            DATA: "Data",
            EVIDENCE: "Evidence",
            RISK: "Risk",
            EXPLAINABILITY: "Explain",
            CONFIDENCE: "Confidence",
            MARKET: "Market",
        };
        return map[String(gate || "").toUpperCase()] || String(gate || "");
    }

    function formatDecisionSummary(explanation, type, gateResults) {
        let headline = sanitizeNumericText(String(explanation || "").trim());
        // Soften any leftover machine phrasing from older runs
        headline = headline
            .replace(/gates failed:\s*\[([^\]]*)\]/gi, (_, inner) => {
                const parts = inner.split(",").map(s => s.replace(/['"]/g, "").trim()).filter(Boolean);
                return parts.length ? `still blocked on ${parts.map(friendlyGateName).join(", ")}` : "safety checks pending";
            })
            .replace(/\bcomposite\s+(\d+(?:\.\d+)?)/gi, "score $1")
            .replace(/\bcomposite\b/gi, "score");

        if (!headline) {
            const t = String(type || "").toUpperCase();
            if (t === "WATCH") headline = "Hold / watch — interesting score, not ready to trade yet.";
            else if (t === "TRADE") headline = "Trade setup — score and safety checks cleared.";
            else if (t === "NO_TRADE") headline = "Pass — score below watch level.";
            else headline = "No explanation recorded.";
        }

        const score = extractScoreFromText(headline);
        const scoreChip = score
            ? `<span class="meta-chip score-chip">Score ${score}</span>`
            : "";

        const gates = Array.isArray(gateResults) ? gateResults : [];
        const failed = gates.filter(g => g && g.passed === false);
        let gateChips = "";
        if (failed.length) {
            gateChips = `<div class="gate-chip-row">${failed.map(g =>
                `<span class="gate-chip fail" title="${sanitizeNumericText(g.detail || "").replace(/"/g, "&quot;")}">Needs ${friendlyGateName(g.gate)}</span>`
            ).join("")}</div>`;
        } else if (gates.length && gates.every(g => g.passed)) {
            gateChips = `<div class="gate-chip-row"><span class="gate-chip pass">All checks passed</span></div>`;
        }

        return { headline, scoreChip, gateChips };
    }

    function humanizeDecisionText(text) {
        if (!text) return "No explanation recorded";
        return formatDecisionSummary(text, "", []).headline;
    }

    // Friendly label (UX-8 copy pass) — the raw enum (TRADE/WATCH/NO_TRADE/
    // INSUFFICIENT_DATA) was leaking straight into a chip sitting right next
    // to the already-friendly stance chip (BUY/HOLD/PASS/WAIT), reading as
    // two badges for one idea, one polished and one raw.
    function decisionTypeBadge(type) {
        const t = (type || "").toUpperCase();
        return `<span class="type-chip type-${t.toLowerCase()}">${t ? escapeDecisionHtml(friendlyAnalysisName(t)) : "—"}</span>`;
    }

    function contextChipTone(label) {
        const s = String(label || "").toUpperCase();
        if (s.includes("UNKNOWN")) return "unknown";
        if (/(BULL|STRONG|HEALTHY|CALM)$|GAP_UP/.test(s)) return "good";
        if (/(BEAR|WEAK|ELEVATED)$|HIGH_VOLATILITY|GAP_DOWN/.test(s)) return "bad";
        if (/(MIXED|FLAT|SIDEWAYS)/.test(s)) return "warn";
        return "neutral";
    }

    function contextChip(label, tone) {
        return `<span class="context-chip tone-${tone}">${escapeDecisionHtml(friendlyLabel(label))}</span>`;
    }