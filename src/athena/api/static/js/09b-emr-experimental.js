

    // ---------------------------------------------------------------------------
    // EM-6B: Explosive Move Radar (Experimental) — read-only presentation
    // panel. Fetches GET /api/v1/emr/experimental/touch-10-radar and
    // renders it. Never triggers a scan; never polls faster than a normal
    // page/tab reload; no "Run Radar"/"Refresh Scanner" control exists
    // anywhere in this file — only a plain re-fetch of persisted data.
    // ---------------------------------------------------------------------------

    const emrRadarBody = document.getElementById("emr-radar-body");
    const emrRadarRefreshBtn = document.getElementById("emr-radar-refresh-btn");
    let emrRadarLoaded = false;

    function emrEscapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    function emrFormatProbability(value, language) {
        if (value == null) return "—";
        const pct = (Number(value) * 100).toFixed(1) + "%";
        // probability_language is the frozen EM-5 explanatory field --
        // rendered verbatim, never silently upgraded to "calibrated" if
        // the persisted value says otherwise.
        return language === "calibrated_probability"
            ? `${pct} <span class="emr-cell-muted">(model probability)</span>`
            : `${pct} <span class="emr-cell-muted">(raw estimate)</span>`;
    }

    function emrFormatScore(value) {
        if (value == null) return "—";
        return Number(value).toFixed(3);
    }

    function emrFormatEvidence(known, total) {
        if (known == null || total == null) return "—";
        return `${known} / ${total}`;
    }

    function emrFormatCheckpointPrice(price, semantic) {
        if (price == null) return "—";
        const formatted = typeof formatDecisionPrice === "function"
            ? formatDecisionPrice(price)
            : `₹${price}`;
        return semantic ? `${formatted} <span class="emr-cell-muted">(${emrEscapeHtml(semantic)})</span>` : formatted;
    }

    function emrFormatAge(scanAge) {
        if (!scanAge) return "—";
        const minutes = scanAge.age_minutes;
        if (minutes == null || !Number.isFinite(minutes)) return "—";
        if (minutes < 0) return "in the future (clock skew)";
        if (minutes < 1) return "less than a minute ago";
        if (minutes < 60) return `${Math.round(minutes)} min ago`;
        const hours = minutes / 60;
        return `${hours.toFixed(1)} hr ago`;
    }

    function emrFormatTimestamp(value) {
        if (!value) return "—";
        return typeof formatDecisionTime === "function" ? formatDecisionTime(value) : value;
    }

    function emrRenderLoading() {
        if (!emrRadarBody) return;
        emrRadarBody.innerHTML = `<div class="emr-loading-state">Loading Experimental radar…</div>`;
    }

    function emrRenderError() {
        if (!emrRadarBody) return;
        emrRadarBody.innerHTML = `<div class="emr-error-state">
            <i class="fas fa-triangle-exclamation"></i>
            Could not load the Experimental radar. Try refreshing.
        </div>`;
    }

    function emrRenderNoScan() {
        if (!emrRadarBody) return;
        emrRadarBody.innerHTML = `<div class="emr-empty-state">
            No completed EMR scan is available.<br>
            <span class="text-muted">The Experimental radar displays persisted scanner output only.</span>
        </div>`;
    }

    function emrRenderScanMeta(scan, scanAge) {
        return `<div class="emr-scan-meta">
            <div class="emr-scan-meta-item">
                <span class="emr-scan-meta-label">Session</span>
                <span class="emr-scan-meta-value">${emrEscapeHtml(scan.session_date)}</span>
            </div>
            <div class="emr-scan-meta-item">
                <span class="emr-scan-meta-label">Checkpoint</span>
                <span class="emr-scan-meta-value">${emrEscapeHtml(scan.checkpoint)}</span>
            </div>
            <div class="emr-scan-meta-item">
                <span class="emr-scan-meta-label">Last scan time</span>
                <span class="emr-scan-meta-value">${emrFormatTimestamp(scan.finished_ts || scan.started_ts)}</span>
            </div>
            <div class="emr-scan-meta-item">
                <span class="emr-scan-meta-label">Scan age</span>
                <span class="emr-scan-meta-value">${emrEscapeHtml(emrFormatAge(scanAge))}</span>
            </div>
        </div>`;
    }

    function emrRenderCoverage(coverage) {
        if (!coverage) return "";
        const reasons = (coverage.unranked_reason_counts || [])
            .map(([reason, count]) => `${emrEscapeHtml(reason)}: ${count}`)
            .join(", ");
        return `<div class="emr-coverage-strip">
            <span>Evaluated: <strong>${coverage.evaluated_count}</strong></span>
            <span>Ranked: <strong>${coverage.ranked_count}</strong></span>
            <span>Not ranked: <strong>${coverage.unranked_count}</strong></span>
        </div>
        ${reasons ? `<div class="emr-coverage-reasons">Not-ranked reasons — ${reasons}</div>` : ""}`;
    }

    function emrRenderCandidateRow(candidate, index) {
        return `<tr>
            <td>${index + 1}</td>
            <td>${emrEscapeHtml(candidate.instrument_id)}</td>
            <td>${emrFormatProbability(candidate.calibrated_probability, candidate.probability_language)}</td>
            <td>${emrFormatScore(candidate.deterministic_score)}</td>
            <td>${emrEscapeHtml(candidate.state)}</td>
            <td class="emr-cell-muted">${emrEscapeHtml(candidate.data_freshness)}</td>
            <td>${emrFormatCheckpointPrice(candidate.checkpoint_price, candidate.checkpoint_price_semantic)}</td>
            <td class="emr-cell-muted">${emrFormatEvidence(candidate.evidence_completeness_known, candidate.evidence_completeness_total)}</td>
        </tr>`;
    }

    function emrRenderCandidateTable(candidates) {
        if (!candidates || candidates.length === 0) {
            return `<div class="emr-empty-state">No ranked TOUCH-10 candidates in this scan.</div>`;
        }
        const rows = candidates.map((c, i) => emrRenderCandidateRow(c, i)).join("");
        return `<div class="emr-candidate-table-wrap">
            <table class="emr-candidate-table">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Symbol</th>
                        <th>Model Probability</th>
                        <th>Evidence Score</th>
                        <th>State</th>
                        <th>Data Freshness</th>
                        <th>Checkpoint Price</th>
                        <th>Evidence Coverage</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
    }

    function emrRenderMetadata(scan) {
        return `<details class="emr-metadata-details">
            <summary>Model &amp; scan metadata</summary>
            <div class="emr-metadata-list">
                <span>Run ID: ${emrEscapeHtml(scan.run_id)}</span>
                <span>Model version: ${emrEscapeHtml(scan.frozen_model_version)}</span>
                <span>Eligible: ${scan.eligible_count ?? "—"}</span>
                <span>Ineligible: ${scan.ineligible_count ?? "—"}</span>
            </div>
        </details>`;
    }

    function emrRenderPopulated(data) {
        const parts = [];
        parts.push(`<div class="emr-disclaimer">
            <span class="emr-experimental-badge"><i class="fas fa-flask"></i> Experimental</span>
            ${emrEscapeHtml(data.disclaimer)}
        </div>`);
        parts.push(emrRenderScanMeta(data.scan, data.scan_age));
        parts.push(`<h4>TOUCH 10% Research Candidates</h4>`);
        parts.push(emrRenderCoverage(data.coverage));
        parts.push(emrRenderCandidateTable(data.touch_10));
        parts.push(emrRenderMetadata(data.scan));
        emrRadarBody.innerHTML = parts.join("");
    }

    async function loadEmrExperimentalRadar() {
        if (!emrRadarBody) return;
        emrRenderLoading();
        try {
            const res = await apiRequest("/api/v1/emr/experimental/touch-10-radar", { skipToast: true });
            const data = res && res.data ? res.data : null;
            if (!data) {
                emrRenderError();
                return;
            }
            if (!data.scan) {
                // Distinct from "0 ranked candidates in a real scan" —
                // this is "no completed scan exists at all".
                emrRadarBody.innerHTML = `<div class="emr-disclaimer">
                    <span class="emr-experimental-badge"><i class="fas fa-flask"></i> Experimental</span>
                    ${emrEscapeHtml(data.disclaimer)}
                </div>`;
                emrRadarBody.innerHTML += `<div class="emr-empty-state">
                    No completed EMR scan is available.<br>
                    <span class="text-muted">The Experimental radar displays persisted scanner output only.</span>
                </div>`;
                return;
            }
            emrRenderPopulated(data);
        } catch (error) {
            console.error("Failed to load EMR experimental radar", error);
            emrRenderError();
        } finally {
            emrRadarLoaded = true;
        }
    }

    emrRadarRefreshBtn?.addEventListener("click", async (event) => {
        // The button lives inside a <summary> (for layout); stop it from
        // also toggling the <details> open/closed on click.
        event.preventDefault();
        event.stopPropagation();
        const icon = emrRadarRefreshBtn.querySelector("i");
        emrRadarRefreshBtn.disabled = true;
        icon?.classList.add("fa-spin");
        try {
            await loadEmrExperimentalRadar();
        } finally {
            emrRadarRefreshBtn.disabled = false;
            icon?.classList.remove("fa-spin");
        }
    });
