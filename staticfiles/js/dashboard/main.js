class Dashboard {
    constructor() {
        this.api = new DashboardApi();
        this.charts = new DashboardCharts();
        this.isAdmin = document.body.dataset.userRole === 'admin';
        this.initialize();
    }

    async initialize() {
        this.setupEventListeners();
        await this.loadAllData();
        this.setupAutoRefresh();
    }

    setupEventListeners() {
        document.getElementById('refreshDashboard')?.addEventListener('click', () => {
            this.loadAllData();
        });

        document.getElementById('dateRange')?.addEventListener('change', (e) => {
            this.loadAllData(e.target.value);
        });
    }

    setupAutoRefresh() {
        setInterval(() => {
            this.loadAllData();
        }, DASHBOARD_CONFIG.refreshInterval);
    }

    async loadAllData() {
        try {
            this.showAllLoading();

            const [adminStats, recentProjects, recentTasks, businessStatus] = await Promise.all([
                this.isAdmin ? this.api.getAdminStats() : null,
                this.api.getRecentProjects(),
                this.api.getRecentTasks(),
                this.api.getBusinessStatus()
            ]);

            this.updateDashboard({
                adminStats,
                recentProjects,
                recentTasks,
                businessStatus
            });

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data');
        } finally {
            this.hideAllLoading();
        }
    }

    updateDashboard(data) {
        if (this.isAdmin && data.adminStats) {
            this.updateAdminStats(data.adminStats);
        }

        if (data.recentProjects) {
            this.updateRecentProjects(data.recentProjects);
        }

        if (data.recentTasks) {
            this.updateRecentTasks(data.recentTasks);
        }

        if (data.businessStatus) {
            this.charts.initializeBusinessStatusChart(
                data.businessStatus,
                'businessStatusChart'
            );
        }
    }

    updateAdminStats(stats) {
        const elements = {
            totalProjects: document.getElementById('totalProjects'),
            totalBusinesses: document.getElementById('totalBusinesses'),
            completionRate: document.getElementById('completionRate'),
            activeUsers: document.getElementById('activeUsers')
        };

        Object.entries(elements).forEach(([key, element]) => {
            if (element && stats[key] !== undefined) {
                element.textContent = stats[key];
            }
        });
    }

    updateRecentProjects(projects) {
        const container = document.getElementById('recentProjectsList');
        if (!container) return;

        container.innerHTML = projects.data
            .map(project => DashboardComponents.createTaskCard(project))
            .join('');
    }

    updateRecentTasks(tasks) {
        const container = document.getElementById('recentTasksList');
        if (!container) return;

        container.innerHTML = tasks.data
            .map(task => DashboardComponents.createTaskCard(task))
            .join('');
    }

    showAllLoading() {
        const containers = ['adminStats', 'recentProjects', 'recentTasks', 'businessStatus'];
        containers.forEach(id => {
            const container = document.getElementById(id);
            if (container) {
                container.innerHTML = DashboardComponents.createLoadingSpinner();
            }
        });
    }

    hideAllLoading() {
        const loadingSpinners = document.querySelectorAll('.spinner-border');
        loadingSpinners.forEach(spinner => {
            spinner.remove();
        });
    }

    showError(message) {
        const errorContainer = document.getElementById('dashboardErrors');
        if (errorContainer) {
            errorContainer.innerHTML = DashboardComponents.createErrorAlert(message);
        }
    }
}
