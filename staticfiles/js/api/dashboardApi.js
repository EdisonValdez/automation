class DashboardApi {
    constructor() {
        this.baseUrl = '/api/dashboard';
        this.headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken()
        };
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    async fetchWithError(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: this.headers
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    async getAdminStats() {
        return this.fetchWithError(`${this.baseUrl}/admin-stats/`);
    }

    async getRecentProjects(limit = 5) {
        return this.fetchWithError(`${this.baseUrl}/recent-projects/?limit=${limit}`);
    }

    async getRecentTasks(days = 7) {
        return this.fetchWithError(`${this.baseUrl}/recent-tasks/?days=${days}`);
    }

    async getTimelineData(startDate, endDate) {
        return this.fetchWithError(
            `${this.baseUrl}/timeline-data/?start_date=${startDate}&end_date=${endDate}`
        );
    }

    async getBusinessStatus() {
        return this.fetchWithError(`${this.baseUrl}/business-status/`);
    }

    async getCategoryStats() {
        return this.fetchWithError(`${this.baseUrl}/category-stats/`);
    }

    async getDashboardSummary(days = 30) {
        return this.fetchWithError(`${this.baseUrl}/summary/?days=${days}`);
    }
}
