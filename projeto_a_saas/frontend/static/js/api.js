/**
 * LegalShield AI — API Client
 * Wrapper fetch() com JWT auto-refresh e error handling.
 */

const API = {
    baseUrl: '/api',

    async request(method, path, { body, params, isForm } = {}) {
        let url = `${this.baseUrl}${path}`;
        if (params) {
            const qs = new URLSearchParams(params).toString();
            if (qs) url += `?${qs}`;
        }

        const headers = {};
        if (Store.accessToken) {
            headers['Authorization'] = `Bearer ${Store.accessToken}`;
        }

        const opts = { method, headers };

        if (body && !isForm) {
            headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        } else if (isForm && body) {
            opts.body = body; // FormData
        }

        let response = await fetch(url, opts);

        // Auto-refresh on 401
        if (response.status === 401 && Store.refreshToken) {
            const refreshed = await this._refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${Store.accessToken}`;
                opts.headers = headers;
                response = await fetch(url, opts);
            }
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            let msg = `Erro ${response.status}`;
            if (typeof errorData.detail === 'string') {
                msg = errorData.detail;
            } else if (Array.isArray(errorData.detail)) {
                msg = errorData.detail.map(e => e.msg || e.message || JSON.stringify(e)).join('; ');
            }
            throw new Error(msg);
        }

        // Handle non-JSON responses (PDF download etc)
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return response.json();
        }
        if (contentType.includes('application/pdf')) {
            return response.blob();
        }
        return response.text();
    },

    async _refreshToken() {
        try {
            const resp = await fetch(`${this.baseUrl}/v1/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: Store.refreshToken }),
            });
            if (!resp.ok) {
                Store.clear();
                window.location.hash = '#/login';
                return false;
            }
            const data = await resp.json();
            Store.setAuth(data);
            return true;
        } catch (e) {
            Store.clear();
            window.location.hash = '#/login';
            return false;
        }
    },

    // === Auth ===
    login(email, password, mfa_code) {
        return this.request('POST', '/v1/auth/login', { body: { email, password, mfa_code } });
    },
    register(data) {
        return this.request('POST', '/v1/auth/register', { body: data });
    },
    logout() {
        return this.request('POST', '/v1/auth/logout');
    },

    // === Contracts ===
    listContracts(page = 1, perPage = 20) {
        return this.request('GET', '/v1/contracts/', { params: { page, per_page: perPage } });
    },
    uploadContract(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('POST', '/v1/contracts/upload', { body: formData, isForm: true });
    },
    deleteContract(id) {
        return this.request('DELETE', `/v1/contracts/${id}`);
    },

    // === Analysis ===
    createAnalysis(contractId, mode) {
        return this.request('POST', '/v1/analysis/', { body: { contract_id: contractId, mode } });
    },
    listAnalyses(contractId, page = 1) {
        const params = { page };
        if (contractId) params.contract_id = contractId;
        return this.request('GET', '/v1/analysis/', { params });
    },
    getAnalysis(id) {
        return this.request('GET', `/v1/analysis/${id}`);
    },

    // === Reports ===
    exportPDF(analysisId) {
        return this.request('POST', `/v1/reports/export/${analysisId}`);
    },

    // === Admin: Tenants ===
    listTenants() {
        return this.request('GET', '/admin/tenants/');
    },
    blockTenant(id, reason) {
        return this.request('POST', `/admin/tenants/${id}/block`, { body: { reason } });
    },
    unblockTenant(id) {
        return this.request('POST', `/admin/tenants/${id}/unblock`);
    },
    updateTenant(id, data) {
        return this.request('PATCH', `/admin/tenants/${id}`, { body: data });
    },

    // === Admin: Usage ===
    getUsage(period = 'month') {
        return this.request('GET', '/admin/usage', { params: { period } });
    },
    getAuditLogs(filters = {}) {
        return this.request('GET', '/admin/audit', { params: filters });
    },

    // === Admin: LLM Settings ===
    getLLMSettings() {
        return this.request('GET', '/admin/settings/llm/');
    },
    updateLLMSettings(data) {
        return this.request('PUT', '/admin/settings/llm/', { body: data });
    },
    testLLM(model, prompt) {
        return this.request('POST', '/admin/settings/llm/test', { body: { model, prompt } });
    },

    // === Admin: Theme ===
    getThemePresets() {
        return this.request('GET', '/admin/theme/presets');
    },
    getTenantTheme(tenantId) {
        return this.request('GET', `/admin/theme/${tenantId}`);
    },
    updateTenantTheme(tenantId, data) {
        return this.request('PUT', `/admin/theme/${tenantId}`, { body: data });
    },
    applyThemePreset(tenantId, presetName) {
        return this.request('PUT', `/admin/theme/${tenantId}/preset/${presetName}`);
    },
};
