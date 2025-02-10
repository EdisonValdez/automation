 
document.addEventListener('DOMContentLoaded', function() {
    const dashboard = new DashboardUI();
    dashboard.initializeDashboard();

    // Add refresh functionality
    const refreshButton = document.getElementById('refreshDashboard');
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            dashboard.initializeDashboard();
        });
    }

    // Add date range selector functionality
    const dateRangeSelector = document.getElementById('dateRangeSelector');
    if (dateRangeSelector) {
        dateRangeSelector.addEventListener('change', (e) => {
            const days = e.target.value;
            dashboard.updateTimelineChart(days);
        });
    }

    // Add error handling for failed API calls
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
        // Show a generic error message to the user
        const errorContainer = document.getElementById('dashboardErrors');
        if (errorContainer) {
            errorContainer.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    An error occurred while loading the dashboard. Please try refreshing the page.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        }
    });
});
