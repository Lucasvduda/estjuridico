/**
 * LegalShield AI — Auth Module
 * Login, Registro e MFA.
 */

const Auth = {
    renderLogin() {
        const container = document.getElementById('auth-form-container');
        container.innerHTML = `
            <h2>Entrar</h2>
            <form id="login-form">
                <div class="form-group">
                    <label class="form-label" for="login-email">E-mail</label>
                    <input class="form-input" type="email" id="login-email" placeholder="seu@email.com" required autocomplete="email">
                </div>
                <div class="form-group">
                    <label class="form-label" for="login-password">Senha</label>
                    <input class="form-input" type="password" id="login-password" placeholder="••••••••" required minlength="8" autocomplete="current-password">
                </div>
                <div class="form-group hidden" id="mfa-group">
                    <label class="form-label" for="login-mfa">Código MFA</label>
                    <input class="form-input" type="text" id="login-mfa" placeholder="000000" maxlength="6">
                </div>
                <button type="submit" class="btn btn-primary btn-block btn-lg" id="btn-login">
                    <span class="btn-text">Entrar</span>
                </button>
            </form>
            <div class="auth-switch">
                Não tem conta? <a onclick="Auth.renderRegister()">Criar conta</a>
            </div>
        `;
        safeIcons();

        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-login');
            btn.classList.add('btn-loading');
            btn.disabled = true;

            try {
                const email = document.getElementById('login-email').value;
                const password = document.getElementById('login-password').value;
                const mfa = document.getElementById('login-mfa').value || undefined;

                const data = await API.login(email, password, mfa);
                Store.setAuth(data);

                // Decode JWT to get user info
                const payload = JSON.parse(atob(data.access_token.split('.')[1]));
                Store.setUser({
                    id: payload.sub,
                    role: payload.role || 'user',
                    tenant_id: payload.tenant_id,
                });

                Components.toast('Login realizado com sucesso!', 'success');
                App.handleAuth();
            } catch (err) {
                if (err.message.includes('MFA')) {
                    document.getElementById('mfa-group').classList.remove('hidden');
                    Components.toast('Insira o código MFA', 'warning');
                } else {
                    Components.toast(err.message, 'error');
                }
            } finally {
                btn.classList.remove('btn-loading');
                btn.disabled = false;
            }
        });
    },

    renderRegister() {
        const container = document.getElementById('auth-form-container');
        container.innerHTML = `
            <h2>Criar Conta</h2>
            <form id="register-form">
                <div class="form-group">
                    <label class="form-label" for="reg-name">Nome Completo</label>
                    <input class="form-input" type="text" id="reg-name" placeholder="João Silva" required minlength="2">
                </div>
                <div class="form-group">
                    <label class="form-label" for="reg-email">E-mail</label>
                    <input class="form-input" type="email" id="reg-email" placeholder="joao@escritorio.com.br" required>
                </div>
                <div class="form-group">
                    <label class="form-label" for="reg-password">Senha</label>
                    <input class="form-input" type="password" id="reg-password" placeholder="Mínimo 8 caracteres, 1 maiúscula, 1 número" required minlength="8">
                </div>
                <div class="form-group">
                    <label class="form-label" for="reg-tenant-name">Nome da Empresa</label>
                    <input class="form-input" type="text" id="reg-tenant-name" placeholder="Escritório Silva Advogados" required>
                </div>
                <div class="form-group">
                    <label class="form-label" for="reg-tenant-slug">Slug (identificador único)</label>
                    <input class="form-input" type="text" id="reg-tenant-slug" placeholder="silva-advogados" required minlength="3" pattern="[a-z0-9-]+">
                    <span class="form-error" style="color:var(--text-tertiary);font-size:11px;">Apenas letras minúsculas, números e hífens</span>
                </div>
                <button type="submit" class="btn btn-primary btn-block btn-lg" id="btn-register">
                    <span class="btn-text">Criar Conta</span>
                </button>
            </form>
            <div class="auth-switch">
                Já tem conta? <a onclick="Auth.renderLogin()">Entrar</a>
            </div>
        `;

        // Auto-generate slug from company name
        const nameInput = document.getElementById('reg-tenant-name');
        const slugInput = document.getElementById('reg-tenant-slug');
        nameInput.addEventListener('input', () => {
            slugInput.value = nameInput.value
                .toLowerCase()
                .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/^-|-$/g, '');
        });

        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-register');
            btn.classList.add('btn-loading');
            btn.disabled = true;

            try {
                const data = await API.register({
                    full_name: document.getElementById('reg-name').value,
                    email: document.getElementById('reg-email').value,
                    password: document.getElementById('reg-password').value,
                    tenant_name: document.getElementById('reg-tenant-name').value,
                    tenant_slug: document.getElementById('reg-tenant-slug').value,
                });
                Store.setAuth(data);

                const payload = JSON.parse(atob(data.access_token.split('.')[1]));
                Store.setUser({
                    id: payload.sub,
                    role: payload.role || 'admin',
                    tenant_id: payload.tenant_id,
                });

                Components.toast('Conta criada com sucesso!', 'success');
                App.handleAuth();
            } catch (err) {
                Components.toast(err.message, 'error');
            } finally {
                btn.classList.remove('btn-loading');
                btn.disabled = false;
            }
        });
    },
};
