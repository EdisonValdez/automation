// static/js/dashboard/ 

class DashboardComponents {
    constructor() {
        this.config = DASHBOARD_CONFIG;
    }

    // Utility method to create loading spinner
    createLoadingSpinner() {
        return `
            <div class="text-center p-3">
                <div class="${this.config.loading.spinnerClass}" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    }

    // Create status badge
    createStatusBadge(status) {
        const statusColor = this.config.status.colors[status] || this.config.status.colors.DEFAULT;
        return `<span class="badge bg-${statusColor}">${status}</span>`;
    }

    // Create recent project item
    createProjectItem(project) {
        return `
            <div class="list-group-item list-group-item-action">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${this.escapeHtml(project.project_title)}</h6>
                    ${this.createStatusBadge(project.status)}
                </div>
                <p class="mb-1">
                    <small class="text-muted">
                        ${this.formatDate(project.created_at)} | 
                        Businesses: ${project.business_count || 0}
                    </small>
                </p>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                        ${this.escapeHtml(project.destination || 'No destination')}
                    </small>
                    <button class="btn btn-sm btn-outline-primary view-details" 
                            data-project-id="${project.id}">
                        View Details
                    </button>
                </div>
            </div>
        `;
    }

    // Create recent task item
    createTaskItem(task) {
        return `
            <div class="list-group-item list-group-item-action">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${this.escapeHtml(task.task_title)}</h6>
                    ${this.createStatusBadge(task.status)}
                </div>
                <p class="mb-1">
                    ${this.escapeHtml(task.description || 'No description')}
                </p>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                        ${this.formatDate(task.created_at)}
                    </small>
                    <div class="progress" style="width: 100px">
                        <div class="progress-bar" role="progressbar" 
                             style="width: ${task.progress || 0}%" 
                             aria-valuenow="${task.progress || 0}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            ${task.progress || 0}%
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // Create error message
    createErrorMessage(message) {
        return `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                ${this.escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    }

    // Create pagination controls
    createPagination(currentPage, totalPages, baseUrl) {
        if (totalPages <= 1) return '';

        let pages = [];
        const maxPages = this.config.pagination.maxPages;
        let startPage = Math.max(1, currentPage - Math.floor(maxPages / 2));
        let endPage = Math.min(totalPages, startPage + maxPages - 1);

        if (endPage - startPage + 1 < maxPages) {
            startPage = Math.max(1, endPage - maxPages + 1);
        }

        for (let i = startPage; i <= endPage; i++) {
            pages.push(`
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="${baseUrl}?page=${i}">${i}</a>
                </li>
            `);
        }

        return `
            <nav aria-label="Page navigation">
                <ul class="pagination justify-content-center">
                    <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                        <a class="page-link" href="${baseUrl}?page=1" aria-label="First">
                            <span aria-hidden="true">&laquo;</span>
                        </a>
                    </li>
                    ${pages.join('')}
                    <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                        <a class="page-link" href="${baseUrl}?page=${totalPages}" aria-label="Last">
                            <span aria-hidden="true">&raquo;</span>
                        </a>
                    </li>
                </ul>
            </nav>
        `;
    }

    // Utility methods
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    showLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = this.createLoadingSpinner();
        }
    }

    hideLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = '';
        }
    }
}
