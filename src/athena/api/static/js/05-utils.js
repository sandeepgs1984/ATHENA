

    function extractScoreFromText(text) {
        const m = String(text || "").match(/score\s+(\d+(?:\.\d+)?)/i)
            || String(text || "").match(/composite\s+(\d+(?:\.\d+)?)/i);
        if (!m) return null;
        const n = Number(m[1]);
        return Number.isFinite(n) ? n.toFixed(n % 1 === 0 ? 0 : 1) : null;
    }

    /** Round long Decimal strings for display without inventing new values. */
    function sanitizeNumericText(text) {
        return String(text || "").replace(/\d+\.\d{3,}/g, match => {
            const number = Number(match);
            return Number.isFinite(number) ? number.toFixed(1) : match;
        });
    }

    function formatDecisionPrice(value) {
        const amount = Number(value);
        if (!Number.isFinite(amount)) return "—";
        return `₹${amount.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    function formatDecisionRatio(value) {
        const ratio = Number(value);
        if (!Number.isFinite(ratio)) return "—";
        return `${ratio.toFixed(2)} : 1`;
    }

    function formatDecisionTime(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "Unknown time";
        return date.toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        }) + " IST";
    }

    function friendlyAnalysisName(value) {
        return String(value || "unknown")
            .replace(/_/g, " ")
            .replace(/\b\w/g, char => char.toUpperCase());
    }

    // Meaning over decimals (UX-2/owner audit): a 0-100 value on its own
    // means nothing to a trader in under 5 seconds — band it into a word
    // first, keep the number as a secondary caption.
    function qualityBand(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return null;
        if (n >= 85) return "Excellent";
        if (n >= 70) return "Strong";
        if (n >= 55) return "Good";
        if (n >= 40) return "Fair";
        return "Weak";
    }

    // Risk reads as a hazard level (Low/Medium/High), not a quality score.
    // Keep these cutoffs aligned with config/risk_assessment.json:
    // levels.low_below = 40, levels.high_at_or_above = 70.
    function riskBand(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return null;
        if (n < 40) return "Low";
        if (n < 70) return "Medium";
        return "High";
    }

    function friendlyLabel(label) {
        return String(label || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }
