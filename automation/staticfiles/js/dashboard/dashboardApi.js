class DashboardApi {
    constructor() {
        this.baseUrl = '/api/dashboard';
        this.headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken()
        };
    }

    getCsrfToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (!csrfToken) {
            console.warn('CSRF token not found');
        }
        return csrfToken;
    }

    async fetchData(endpoint) {
        try {
            const response = await fetch(`${this.baseUrl}/${endpoint}`, {
                method: 'GET',
                headers: this.headers,
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    getAdminStats = () => this.fetchData('admin-stats/');
    getRecentProjects = () => this.fetchData('recent-projects/');
    getRecentTasks = () => this.fetchData('recent-tasks/');
    getAmbassadorData = () => this.fetchData('ambassador-data/');
    getBusinessStatus = () => this.fetchData('business-status/');
}
