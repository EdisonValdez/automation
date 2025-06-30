// static/js/dashboard/config.js

const DASHBOARD_CONFIG = {
    // API endpoint configurations
    api: {
        baseUrl: '/api/dashboard',
        endpoints: {
            adminStats: 'admin-stats/',
            recentProjects: 'recent-projects/',
            recentTasks: 'recent-tasks/',
            businessStatus: 'business-status/',
            tasksTimeline: 'tasks-timeline/',
            ambassadorData: 'ambassador-data/'
        },
        refreshInterval: 300000, // 5 minutes in milliseconds
    },

    // Chart configurations
    charts: {
        colors: {
            primary: '#4e73df',
            success: '#1cc88a',
            info: '#36b9cc',
            warning: '#f6c23e',
            danger: '#e74a3b',
            secondary: '#858796',
            light: '#f8f9fc',
            dark: '#5a5c69'
        },
        businessStatus: {
            type: 'doughnut',
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: {
                            size: 14
                        },
                        bodyFont: {
                            size: 13
                        }
                    }
                }
            }
        },
        tasksTimeline: {
            type: 'line',
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 20,
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: {
                            size: 14
                        },
                        bodyFont: {
                            size: 13
                        }
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
                        }
                    }
                }
            }
        }
    },

    // Status configurations
    status: {
        colors: {
            PENDING: 'warning',
            IN_PROGRESS: 'info',
            COMPLETED: 'success',
            FAILED: 'danger',
            CANCELLED: 'secondary',
            DEFAULT: 'secondary'
        }
    },

    // Pagination configurations
    pagination: {
        itemsPerPage: 5,
        maxPages: 5
    },

    // Animation configurations
    animations: {
        duration: 400,
        easing: 'ease-in-out'
    },

    // Loading state configurations
    loading: {
        spinnerClass: 'spinner-border text-primary',
        spinnerSize: 'sm',
        timeout: 30000 // 30 seconds timeout for loading states
    },

    // Error message configurations
    errors: {
        messages: {
            default: 'An error occurred. Please try again.',
            network: 'Network error. Please check your connection.',
            timeout: 'Request timed out. Please try again.',
            unauthorized: 'You are not authorized to view this data.',
            notFound: 'The requested resource was not found.'
        },
        displayDuration: 5000 // How long error messages are displayed
    },

    // Date format configurations
    dateFormat: {
        display: {
            date: 'MMM DD, YYYY',
            datetime: 'MMM DD, YYYY HH:mm',
            time: 'HH:mm'
        },
        api: {
            date: 'YYYY-MM-DD',
            datetime: 'YYYY-MM-DD HH:mm:ss'
        }
    }
};

// Prevent modifications to the configuration object
Object.freeze(DASHBOARD_CONFIG);
