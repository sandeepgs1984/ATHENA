

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

    // Presentation-only mirror of config/decision.json plan freshness bands.
    // The selected brief still uses the authoritative /plan-freshness DTO;
    // this lets list rows show a deterministic pre-open hint from the
    // persisted TradePlan validity window without making extra API calls.
    const TRADE_PLAN_FRESHNESS_WARN_FRACTION = 0.5;
    const TRADE_PLAN_FRESHNESS_STALE_FRACTION = 0.8;

    function formatTradePlanRelativeDuration(seconds) {
        const totalSeconds = Math.max(0, Math.round(Number(seconds)));
        if (!Number.isFinite(totalSeconds)) return "";
        if (totalSeconds < 60) return "under 1m";
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const parts = [];
        if (days) parts.push(`${days}d`);
        if (hours) parts.push(`${hours}h`);
        if (minutes && parts.length < 2) parts.push(`${minutes}m`);
        return parts.slice(0, 2).join(" ");
    }

    function inferTradePlanFreshness(plan, now = new Date()) {
        if (!plan) {
            return {
                has_trade_plan: false,
                status: "NO_PLAN",
                summary: "No trade plan was generated for this decision.",
            };
        }
        const validFrom = new Date(plan.valid_from);
        const validUntil = new Date(plan.valid_until);
        const asOf = new Date(now);
        if (
            Number.isNaN(validFrom.getTime())
            || Number.isNaN(validUntil.getTime())
            || Number.isNaN(asOf.getTime())
        ) {
            return {
                has_trade_plan: true,
                status: "UNKNOWN",
                summary: "TradePlan validity window is unavailable.",
            };
        }
        const total = Math.max(0, (validUntil.getTime() - validFrom.getTime()) / 1000);
        const elapsed = total > 0
            ? Math.max(0, Math.min(total, (asOf.getTime() - validFrom.getTime()) / 1000))
            : total;
        const remaining = Math.max(0, (validUntil.getTime() - asOf.getTime()) / 1000);
        const decay = total > 0 ? elapsed / total : 1;
        const status = asOf >= validUntil
            ? "EXPIRED"
            : decay >= TRADE_PLAN_FRESHNESS_STALE_FRACTION
                ? "STALE"
                : decay >= TRADE_PLAN_FRESHNESS_WARN_FRACTION
                    ? "AGING"
                    : "FRESH";
        return {
            has_trade_plan: true,
            as_of: asOf.toISOString(),
            valid_from: validFrom.toISOString(),
            valid_until: validUntil.toISOString(),
            elapsed_seconds: Math.round(elapsed),
            remaining_seconds: Math.round(remaining),
            total_seconds: Math.round(total),
            decay_fraction: decay,
            status,
            summary: "",
        };
    }

    function formatTradePlanFreshnessBadge(data) {
        const status = String(data && data.status || "").toUpperCase();
        const label = friendlyLabel(status);
        if (status === "EXPIRED") {
            const asOf = new Date(data.as_of);
            const validUntil = new Date(data.valid_until);
            const expiredSeconds = (asOf.getTime() - validUntil.getTime()) / 1000;
            const ago = formatTradePlanRelativeDuration(expiredSeconds);
            return ago ? `${label} · expired ${ago} ago` : label;
        }
        const remaining = Number(data && data.remaining_seconds);
        const expiresIn = formatTradePlanRelativeDuration(remaining);
        return expiresIn ? `${label} · expires in ${expiresIn}` : label;
    }

    function formatTradePlanFreshnessTitle(data) {
        const pct = data && data.decay_fraction !== null && data.decay_fraction !== undefined
            ? Math.round(Number(data.decay_fraction) * 100)
            : null;
        const parts = [];
        if (Number.isFinite(pct)) parts.push(`${pct}% of the validity window elapsed`);
        if (data && data.valid_until) parts.push(`Valid until ${formatDecisionTime(data.valid_until)}`);
        return parts.join(" · ");
    }

    function formatTradePlanFreshnessShort(data) {
        const status = String(data && data.status || "").toUpperCase();
        if (!data || !data.has_trade_plan) return "No plan";
        if (status === "EXPIRED") return "Expired";
        if (status === "STALE") return "Stale";
        if (status === "AGING") return "Aging";
        if (status === "FRESH") return "Valid";
        return "Plan";
    }
