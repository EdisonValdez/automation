class DashboardUI {
    constructor() {
        this.api = new DashboardApi();
        this.charts = {};
        this.loadingStates = {};
    }

    showLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            this.loadingStates[elementId] = true;
            element.innerHTML = `
                <div class="loading-spinner">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;
        }
    }

    hideLoading(elementId) {
        this.loadingStates[elementId] = false;
    }

    showError(elementId, error) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    ${error.message || 'An error occurred'}
                </div>
            `;
        }
    }

    async initializeDashboard() {
        await Promise.all([
            this.initializeTimelineChart(),
            this.initializeBusinessStatusChart(),
            this.initializeCategoryChart(),
            this.loadRecentProjects(),
            this.loadRecentTasks()
        ]);
    }

    async initializeTimelineChart() {
        try {
            this.showLoading('timelineChart');
            const data = await this.api.getTimelineData();
            
            this.charts.timeline = new Chart(
                document.getElementById('timelineChart'),
                {
                    type: 'line',
                    data: {
                        labels: data.dates,
                        datasets: [
                            {
                                label: 'Tasks',
                                data: data.tasks,
                                borderColor: 'rgb(75, 192, 192)',
                                tension: 0.1
                            },
                            {
                                label: 'Businesses',
                                data: data.businesses,
                                borderColor: 'rgb(255, 99, 132)',
                                tension: 0.1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'top',
                            },
                            title: {
                                display: true,
                                text: 'Timeline Activity'
                            }
                        }
                    }
                }
            );
        } catch (error) {
            this.showError('timelineChart', error);
        } finally {
            this.hideLoading('timelineChart');
        }
    }

    async initializeBusinessStatusChart() {
        try {
            this.showLoading('businessStatusChart');
            const data = await this.api.getBusinessStatus();
            
            this.charts.businessStatus = new Chart(
                document.getElementById('businessStatusChart'),
                {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(data.data),
                        datasets: [{
                            data: Object.values(data.data),
                            backgroundColor: [
                                '#FF6384',
                                '#36A2EB',
                                '#FFCE56',
                                '#4BC0C0'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'right',
                            },
                            title: {
                                display: true,
                                text: 'Business Status Distribution'
                            }
                        }
                    }
                }
            );
        } catch (error) {
            this.showError('businessStatusChart', error);
        } finally {
            this.hideLoading('businessStatusChart');
        }
    }

    async loadRecentProjects() {
        try {
            this.showLoading('recentProjects');
            const data = await this.api.getRecentProjects();
            
            const projectsList = document.getElementById('recentProjectsList');
            projectsList.innerHTML = data.data.map(project => `
                <div class="project-item">
                    <h5>${project.project_title}</h5>
                    <div class="project-details">
                        <span class="badge bg-${this.getStatusColor(project.status)}">
                            ${project.status}
                        </span>
                        <small>${project.created_at}</small>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            this.showError('recentProjects', error);
        } finally {
            this.hideLoading('recentProjects');
        }
    }

    getStatusColor(status) {
        const colors = {
            'PENDING': 'warning',
            'IN_PROGRESS': 'info',
            'COMPLETED': 'success',
            'FAILED': 'danger'
        };
        return colors[status] || 'secondary';
    }
}
