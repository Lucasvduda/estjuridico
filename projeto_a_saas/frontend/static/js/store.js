/**
 * LegalShield AI — Store (Estado Global)
 * Gerencia autenticação, user, tenant, tokens e temas.
 */

const Store = {
    _state: {
        accessToken: null,
        refreshToken: null,
        user: null,
        tenant: null,
        theme: null,
    },

    init() {
        const saved = localStorage.getItem('ls_auth');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                this._state.accessToken = parsed.accessToken;
                this._state.refreshToken = parsed.refreshToken;
                this._state.user = parsed.user;
                this._state.tenant = parsed.tenant;
            } catch (e) {
                this.clear();
            }
        }
        // Carregar tema
        const savedTheme = localStorage.getItem('ls_theme');
        if (savedTheme) {
            try {
                this._state.theme = JSON.parse(savedTheme);
                this.applyTheme(this._state.theme);
            } catch (e) {}
        }
    },

    get accessToken() { return this._state.accessToken; },
    get refreshToken() { return this._state.refreshToken; },
    get user() { return this._state.user; },
    get tenant() { return this._state.tenant; },
    get theme() { return this._state.theme; },
    get isAuthenticated() { return !!this._state.accessToken; },
    get isAdmin() { return this._state.user?.role === 'admin' || this._state.user?.role === 'superadmin'; },
    get isSuperAdmin() { return this._state.user?.role === 'superadmin'; },

    setAuth(data) {
        this._state.accessToken = data.access_token;
        this._state.refreshToken = data.refresh_token;
        this._save();
    },

    setUser(user) {
        this._state.user = user;
        this._save();
    },

    setTenant(tenant) {
        this._state.tenant = tenant;
        this._save();
    },

    setTheme(theme) {
        this._state.theme = theme;
        localStorage.setItem('ls_theme', JSON.stringify(theme));
        this.applyTheme(theme);
    },

    applyTheme(theme) {
        if (!theme) return;
        const root = document.documentElement;
        if (theme.primary_color) {
            root.style.setProperty('--color-primary', theme.primary_color);
            root.style.setProperty('--color-primary-hover', this._adjustBrightness(theme.primary_color, -15));
            root.style.setProperty('--color-primary-light', theme.primary_color + '26');
            root.style.setProperty('--color-primary-glow', theme.primary_color + '66');
        }
        if (theme.accent_color) {
            root.style.setProperty('--color-accent', theme.accent_color);
            root.style.setProperty('--color-accent-light', theme.accent_color + '26');
        }
        if (theme.sidebar_color) {
            root.style.setProperty('--bg-sidebar', theme.sidebar_color);
        }
        if (theme.bg_color) {
            root.style.setProperty('--bg-primary', theme.bg_color);
        }
    },

    _adjustBrightness(hex, percent) {
        const num = parseInt(hex.replace('#', ''), 16);
        const r = Math.min(255, Math.max(0, (num >> 16) + percent));
        const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + percent));
        const b = Math.min(255, Math.max(0, (num & 0x0000FF) + percent));
        return `#${(r << 16 | g << 8 | b).toString(16).padStart(6, '0')}`;
    },

    clear() {
        this._state = { accessToken: null, refreshToken: null, user: null, tenant: null, theme: null };
        localStorage.removeItem('ls_auth');
        localStorage.removeItem('ls_theme');
        document.documentElement.removeAttribute('style');
    },

    _save() {
        localStorage.setItem('ls_auth', JSON.stringify({
            accessToken: this._state.accessToken,
            refreshToken: this._state.refreshToken,
            user: this._state.user,
            tenant: this._state.tenant,
        }));
    },
};

Store.init();
