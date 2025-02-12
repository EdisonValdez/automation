// static/js/dashboard/ 
 // dashboardApi.js
class DashboardApi {
    constructor() {
        this.baseUrl = '/api/dashboard';
        this.headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken()
        };
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    async handleResponse(response, endpoint) {
        if (!response.ok) {
            console.error(`Error response from ${endpoint}:`, response.status, response.statusText);
            const errorData = await response.text();
            console.error('Error details:', errorData);
            throw new Error(`Failed to fetch ${endpoint}: ${response.statusText}`);
        }
        return response.json();
    }

    async getBusinessStats() {
        try {
            console.log('Fetching business stats...');
            const response = await fetch(`${this.baseUrl}/business-stats/`, {
                method: 'GET',
                headers: this.headers,
                credentials: 'same-origin'
            });
            return this.handleResponse(response, 'business stats');
        } catch (error) {
            console.error('Business stats fetch error:', error);
            throw error;
        }
    }

    async getTasksTimeline() {
        try {
            console.log('Fetching tasks timeline...');
            const response = await fetch(`${this.baseUrl}/tasks-timeline/`, {
                method: 'GET',
                headers: this.headers,
                credentials: 'same-origin'
            });
            return this.handleResponse(response, 'tasks timeline');
        } catch (error) {
            console.error('Tasks timeline fetch error:', error);
            throw error;
        }
    }

    async getRecentTasks() {
        try {
            console.log('Fetching recent tasks...');
            const response = await fetch(`${this.baseUrl}/recent-tasks/`, {
                method: 'GET',
                headers: this.headers,
                credentials: 'same-origin'
            });
            return this.handleResponse(response, 'recent tasks');
        } catch (error) {
            console.error('Recent tasks fetch error:', error);
            throw error;
        }
    }
}
