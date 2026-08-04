

    // ---------------------------------------------------------------------------
    // Alert / Toast notification panel
    // ---------------------------------------------------------------------------
    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        let icon = "fa-info-circle";
        if (type === "success") icon = "fa-check-circle";
        if (type === "warning") icon = "fa-triangle-exclamation";
        if (type === "danger") icon = "fa-circle-xmark";

        toast.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        // Remove toast automatically after 4 seconds
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function openModal(modalEl) {
        if (!modalEl) return;
        modalEl.hidden = false;
        modalEl.setAttribute("aria-hidden", "false");
        modalEl.classList.add("active");
    }

    function closeModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.remove("active");
        modalEl.hidden = true;
        modalEl.setAttribute("aria-hidden", "true");
    }

    function closeAllModals() {
        closeModal(traceModal);
        closeModal(document.getElementById("backtest-modal"));
        closeModal(document.getElementById("chart-modal"));
        closeModal(document.getElementById("compare-modal"));
        closeModal(document.getElementById("executive-summary-modal"));
        closeModal(document.getElementById("intraday-sop-modal"));
        closeModal(document.getElementById("index-leadership-modal"));
        closeModal(document.getElementById("validation-funnel-modal"));
        closeModal(document.getElementById("validation-report-modal"));
        closeModal(document.getElementById("top-opportunities-modal"));
        if (!state.kiteBlocking) hideKiteGate();
    }
