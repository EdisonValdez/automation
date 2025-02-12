class DashboardComponents {
    static createLoadingSpinner() {
        return `
            <div class="d-flex justify-content-center align-items-center h-100">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    }

    static createErrorAlert(message) {
        return `
            <div class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
            </div>
        `;
    }

    static createTaskCard(task) {
        return `
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">${task.project_title}</h5>
                    <p class="card-text">
                        <span class="badge bg-${this.getStatusColor(task.status)}">${task.status}</span>
                        <small class="text-muted ms-2">${task.created_at}</small>
                    </p>
                </div>
            </div>
        `;
    }

    static getStatusColor(status) {
        const colors = {
            'PENDING': 'warning',
            'IN_PROGRESS': 'info',
            'COMPLETED': 'success',
            'FAILED': 'danger'
        };
        return colors[status] || 'secondary';
    }
}
