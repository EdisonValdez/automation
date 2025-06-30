class DashboardCharts {
    constructor() {
        this.charts = {};
    }

    initializeBusinessStatusChart(data, elementId) {
        const ctx = document.getElementById(elementId)?.getContext('2d');
        if (!ctx) return;

        this.charts.businessStatus = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(data),
                datasets: [{
                    data: Object.values(data),
                    backgroundColor: Object.values(DASHBOARD_CONFIG.chartColors)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }

    initializeTasksChart(data, elementId) {
        const ctx = document.getElementById(elementId)?.getContext('2d');
        if (!ctx) return;

        this.charts.tasks = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Tasks',
                    data: data.values,
                    borderColor: DASHBOARD_CONFIG.chartColors.primary,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    updateChart(chartName, newData) {
        if (this.charts[chartName]) {
            this.charts[chartName].data = newData;
            this.charts[chartName].update();
        }
    }
}
