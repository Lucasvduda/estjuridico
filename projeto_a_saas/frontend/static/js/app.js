/**
 * LegalShield AI — Main App (Router SPA)
 * Gerencia navegação hash, sidebar, inicialização.
 */

const App = {
    currentPage: null,

    // Definição de rotas
    routes: {
        // Advogado
        'dashboard':    { page: PageDashboard,    title: 'Dashboard',           icon: 'layout-dashboard', section: 'main' },
        'contracts':    { page: PageContracts,     title: 'Contratos',           icon: 'file-text',       section: 'main' },
        'analysis/new': { page: PageAnalysis,      title: 'Nova Análise',        icon: 'scan',            section: 'main' },
        'history':      { page: PageHistory,       title: 'Histórico',           icon: 'history',         section: 'main' },
        // Admin
        'admin/dashboard': { page: PageAdminDashboard, title: 'Analytics',       icon: 'bar-chart-3',    section: 'admin' },
        'admin/tenants':   { page: PageAdminTenants,   title: 'Empresas/Logins', icon: 'building-2',     section: 'admin' },
        'admin/models':    { page: PageAdminModels,    title: 'Modelos IA',      icon: 'cpu',            section: 'admin' },
        'admin/testing':   { page: PageAdminTesting,   title: 'Testar IA',       icon: 'flask-conical',  section: 'admin' },
        'admin/themes':    { page: PageAdminThemes,    title: 'Cores/Temas',     icon: 'palette',        section: 'admin', alt: true },
        'admin/audit':     { page: PageAdminAudit,     title: 'Auditoria',       icon: 'shield-alert',   section: 'admin' },
    },

    init() {
        // Listen for hash changes
        window.addEventListener('hashchange', () => this.navigate());

        // Sidebar toggle
        document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('collapsed');
        });

        // Mobile menu
        document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('mobile-open');
        });

        // Logout
        document.getElementById('btn-logout')?.addEventListener('click', async () => {
            try {
                await API.logout();  // Blacklist token no servidor
            } catch (e) {
                // Ignorar erros — limpar state local mesmo se API falhar
            }
            Store.clear();
            this.handleAuth();
        });

        // Start
        this.handleAuth();
    },

    handleAuth() {
        const loading = document.getElementById('loading-screen');
        const app = document.getElementById('app');
        const authScreen = document.getElementById('auth-screen');

        if (Store.isAuthenticated) {
            loading.style.display = 'none';
            authScreen.style.display = 'none';
            app.style.display = 'flex';
            this.buildSidebar();
            this.updateUserInfo();

            // Navigate to current hash or default
            if (!window.location.hash || window.location.hash === '#/login' || window.location.hash === '#/register') {
                window.location.hash = '#/dashboard';
            } else {
                this.navigate();
            }
        } else {
            loading.style.display = 'none';
            app.style.display = 'none';
            authScreen.style.display = 'flex';

            if (window.location.hash === '#/register') {
                Auth.renderRegister();
            } else {
                Auth.renderLogin();
            }
        }
        safeIcons();
    },

    buildSidebar() {
        const nav = document.getElementById('sidebar-nav');
        let html = '';

        // Main Section
        html += '<div class="nav-section-title">Principal</div>';
        Object.entries(this.routes).forEach(([path, route]) => {
            if (route.section === 'main') {
                html += `
                    <a class="nav-item" data-route="${path}" onclick="App.navigateTo('${path}')">
                        <i data-lucide="${route.icon}"></i>
                        <span class="nav-label">${route.title}</span>
                    </a>
                `;
            }
        });

        // Admin Section (only for superadmin)
        if (Store.isSuperAdmin) {
            html += '<div class="nav-section-title">Administração</div>';
            Object.entries(this.routes).forEach(([path, route]) => {
                if (route.section === 'admin') {
                    html += `
                        <a class="nav-item" data-route="${path}" onclick="App.navigateTo('${path}')">
                            <i data-lucide="${route.icon}"></i>
                            <span class="nav-label">${route.title}</span>
                        </a>
                    `;
                }
            });
        }

        nav.innerHTML = html;
        safeIcons();
    },

    updateUserInfo() {
        const user = Store.user;
        if (user) {
            document.getElementById('user-name').textContent = user.full_name || user.email || 'Usuário';
            const roleMap = { superadmin: 'Super Admin', admin: 'Administrador', user: 'Advogado', viewer: 'Visualizador' };
            document.getElementById('user-role').textContent = roleMap[user.role] || user.role;
        }
    },

    navigateTo(path) {
        window.location.hash = `#/${path}`;
        // Close mobile menu
        document.getElementById('sidebar').classList.remove('mobile-open');
    },

    navigate() {
        const hash = window.location.hash.replace('#/', '') || 'dashboard';

        // Find matching route
        let route = this.routes[hash];
        let routeParams = {};

        // Handle parametric routes like analysis/:id
        if (!route) {
            if (hash.startsWith('analysis/') && hash !== 'analysis/new') {
                route = { page: PageAnalysis, title: 'Resultado da Análise', icon: 'scan', section: 'main' };
                routeParams.id = hash.split('/')[1];
            }
        }

        if (!route) {
            window.location.hash = '#/dashboard';
            return;
        }

        // Check admin access
        if (route.section === 'admin' && !Store.isSuperAdmin) {
            window.location.hash = '#/dashboard';
            Components.toast('Acesso negado', 'error');
            return;
        }

        // Update UI
        document.getElementById('page-title').textContent = route.title;

        // Update active nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.route === hash);
        });

        // Render page
        const content = document.getElementById('page-content');
        content.innerHTML = '<div class="flex justify-center mt-8"><div class="skeleton skeleton-card" style="width:100%;max-width:600px;height:200px;"></div></div>';

        if (route.page && route.page.render) {
            route.page.render(content, routeParams);
        }
    },
};

// === Helpers ===

/** Chama lucide.createIcons() apenas se a lib estiver carregada. */
function safeIcons() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    }
}

// === Inicialização ===
// Os scripts estão no <body> sem defer, então quando app.js roda o DOM já
// tem todos os elementos (loading-screen, app, auth-screen, etc.).
// Não precisamos de DOMContentLoaded — chamamos App.init() diretamente.
(function initApp() {
    function fallback(err) {
        if (err) console.error('[LegalShield] Erro na inicialização:', err);
        var ls = document.getElementById('loading-screen');
        if (ls) ls.style.display = 'none';
        var auth = document.getElementById('auth-screen');
        if (auth) {
            auth.style.display = 'flex';
            try { Auth.renderLogin(); } catch(e2) {}
        }
    }

    try {
        App.init();
    } catch (e) {
        fallback(e);
    }
}());
