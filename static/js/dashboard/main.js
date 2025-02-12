// main.js
class Dashboard {
    constructor() {
        this.api = new DashboardApi();
        this.charts = {};
        this.initializationAttempts = 0;
        this.maxAttempts = 3;
    }

    async initialize() {
        try {
            await this.initializeCharts();
            await this.loadAllData();
            this.setupRefreshInterval();
        } catch (error) {
            console.error('Dashboard initialization error:', error);
            this.handleInitializationError(error);
        }
    }

    async initializeCharts() {
        // Initialize Business Status Chart
        const businessCtx = document.getElementById('businessStatusChart');
        if (!businessCtx) {
            throw new Error('Business status chart canvas not found');
        }

        this.charts.businessStatus = new Chart(businessCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Business Status',
                    data: [],
                    backgroundColor: [
                        '#4e73df', // primary
                        '#1cc88a', // success
                        '#36b9cc', // info
                        '#f6c23e'  // warning
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });

        // Initialize other charts as needed...
    }

    async loadAllData() {
        try {
            this.showLoading();
            const [businessStats, timelineData, recentTasks] = await Promise.all([
                this.api.getBusinessStats(),
                this.api.getTasksTimeline(),
                this.api.getRecentTasks()
            ]);

            this.updateBusinessStatusChart(businessStats);
            this.updateTimelineChart(timelineData);
            this.updateRecentTasks(recentTasks);
            this.hideLoading();
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    updateBusinessStatusChart(data) {
        if (!this.charts.businessStatus) return;

        const labels = Object.keys(data).map(key => 
            key.charAt(0).toUpperCase() + key.slice(1).toLowerCase()
        );
        const values = Object.values(data);

        this.charts.businessStatus.data.labels = labels;
        this.charts.businessStatus.data.datasets[0].data = values;
        this.charts.businessStatus.update();
    }

    showLoading() {
        const loadingDiv = document.getElementById('dashboardLoading');
        if (loadingDiv) {
            loadingDiv.classList.remove('d-none');
        }
    }

    hideLoading() {
        const loadingDiv = document.getElementById('dashboardLoading');
        if (loadingDiv) {
            loadingDiv.classList.add('d-none');
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('dashboardError');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.classList.remove('d-none');
        }
    }

    handleInitializationError(error) {
        this.initializationAttempts++;
        if (this.initializationAttempts < this.maxAttempts) {
            setTimeout(() => this.initialize(), 2000);
        } else {
            this.showError('Failed to initialize dashboard after multiple attempts');
        }
    }

    setupRefreshInterval() {
        setInterval(() => this.loadAllData(), 30000); // Refresh every 30 seconds
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new Dashboard();
    dashboard.initialize();
});
