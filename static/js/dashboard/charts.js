// static/js/dashboard/ 
class DashboardCharts {
    constructor() {
        console.log('Initializing DashboardCharts...');
        this.charts = {};
        this.config = DASHBOARD_CONFIG.charts;
        this.initializeChartDefaults();
    }

    initializeChartDefaults() {
        console.log('Setting Chart.js defaults...');
        if (typeof Chart === 'undefined') {
            console.error('Chart.js is not loaded!');
            return;
        }

        try {
            Chart.defaults.font.family = "'Nunito', 'Helvetica', 'Arial', sans-serif";
            Chart.defaults.responsive = true;
            Chart.defaults.maintainAspectRatio = false;
            Chart.defaults.color = this.config.colors.dark;
            console.log('Chart.js defaults set successfully');
        } catch (error) {
            console.error('Error setting Chart.js defaults:', error);
        }
    }

    createBusinessStatusChart(data) {
        console.log('Creating business status chart with data:', data);
        
        const ctx = document.getElementById('businessStatusChart');
        if (!ctx) {
            console.error('Business status chart canvas not found!');
            return null;
        }
    
        // Destroy existing chart if it exists
        if (this.charts.businessStatus) {
            this.charts.businessStatus.destroy();
        }
    
        try {
            // Format data correctly
            const chartData = {
                labels: data.labels,
                datasets: [{
                    data: data.datasets[0].data,
                    backgroundColor: [
                        'rgba(78, 115, 223, 0.8)',  // blue
                        'rgba(28, 200, 138, 0.8)',  // green
                        'rgba(54, 185, 204, 0.8)',  // cyan
                        'rgba(246, 194, 62, 0.8)'   // yellow
                    ],
                    borderColor: [
                        'rgb(78, 115, 223)',
                        'rgb(28, 200, 138)',
                        'rgb(54, 185, 204)',
                        'rgb(246, 194, 62)'
                    ],
                    borderWidth: 1
                }]
            };
    
            const config = {
                type: 'doughnut',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                padding: 20,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.raw || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${label}: ${value} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            };
    
            console.log('Creating chart with config:', config);
            this.charts.businessStatus = new Chart(ctx, config);
            return this.charts.businessStatus;
        } catch (error) {
            console.error('Error creating business status chart:', error);
            return null;
        }
    }
    
    createTasksTimelineChart(data) {
        console.log('Creating tasks timeline chart with data:', data);
        
        const ctx = document.getElementById('tasksTimelineChart');
        if (!ctx) {
            console.error('Tasks timeline chart canvas not found!');
            return null;
        }
    
        // Destroy existing chart if it exists
        if (this.charts.tasksTimeline) {
            this.charts.tasksTimeline.destroy();
        }
    
        try {
            const config = {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: 'Tasks',
                        data: data.tasks,
                        borderColor: 'rgb(78, 115, 223)',
                        backgroundColor: 'rgba(78, 115, 223, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointBackgroundColor: 'rgb(78, 115, 223)',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            ticks: {
                                stepSize: 1
                            }
                        }
                    }
                }
            };
    
            console.log('Creating chart with config:', config);
            this.charts.tasksTimeline = new Chart(ctx, config);
            return this.charts.tasksTimeline;
        } catch (error) {
            console.error('Error creating tasks timeline chart:', error);
            return null;
        }
    }
    
}
