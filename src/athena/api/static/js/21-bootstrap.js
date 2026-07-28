

    // Escape closes any open modal. A drill-down modal (.modal-stacked, e.g.
    // Inspect Trace opened from inside the Validation Pipeline details modal)
    // closes on its own first, so one Escape doesn't dismiss the parent too.
    window.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        const stackedTop = document.querySelector(".modal-overlay.modal-stacked.active");
        if (stackedTop) {
            closeModal(stackedTop);
            return;
        }
        closeAllModals();
    });

    // Initialize Startup Flows (auth gate first)
    bootstrapSession();
