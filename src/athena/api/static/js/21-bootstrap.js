

    // Escape closes any open modal
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeAllModals();
        }
    });

    // Initialize Startup Flows (auth gate first)
    bootstrapSession();
