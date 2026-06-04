/**
 * LegalShield AI Enterprise — Full SPA App
 * Login, Dashboard, Contratos, Análises, Config BYOK — tudo em um arquivo.
 */
const EApp = {
    token: localStorage.getItem('e_token'),
    routes: {
        'dashboard':  { title: 'Dashboard',    icon: 'layout-dashboard', render: 'renderDashboard' },
        'contracts':  { title: 'Contratos',    icon: 'file-text',        render: 'renderContracts' },
        'analysis':   { title: 'Nova Análise', icon: 'scan',             render: 'renderAnalysis' },
        'stats':      { title: 'Estatísticas', icon: 'bar-chart-3',     render: 'renderStats' },
        'settings':   { title: 'Configurações',icon: 'settings',        render: 'renderSettings' },
    },

    init() {
        window.addEventListener('hashchange', () => this.navigate());
        document.getElementById('login-form')?.addEventListener('submit', e => { e.preventDefault(); this.login(); });
        setTimeout(() => this.handleAuth(), 500);
    },

    toast(msg, type='t-ok') {
        const c = document.getElementById('toasts');
        const t = document.createElement('div'); t.className = `toast ${type}`;
        t.innerHTML = `<span style="flex:1;font-size:0.8125rem;">${msg}</span>`;
        c.appendChild(t); setTimeout(() => t.remove(), 3500);
    },

    modal(html) {
        document.getElementById('modal').innerHTML = html;
        document.getElementById('modal-bg').style.display = 'flex';
        document.getElementById('modal-bg').onclick = e => { if (e.target.id === 'modal-bg') this.closeModal(); };
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    },
    closeModal() { document.getElementById('modal-bg').style.display = 'none'; },

    async api(method, path, body) {
        const h = { 'Authorization': `Bearer ${this.token}` };
        const opts = { method, headers: h };
        if (body && !(body instanceof FormData)) { h['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
        else if (body) { opts.body = body; }
        const r = await fetch(`/api${path}`, opts);
        if (r.status === 401) { this.logout(); throw new Error('Sessão expirada'); }
        if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `Erro ${r.status}`); }
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('json')) return r.json();
        if (ct.includes('pdf')) return r.blob();
        return r.text();
    },

    handleAuth() {
        document.getElementById('loading').style.display = 'none';
        if (this.token) {
            document.getElementById('auth').style.display = 'none';
            document.getElementById('app').style.display = 'flex';
            this.buildNav();
            if (!location.hash || location.hash === '#/login') location.hash = '#/dashboard';
            else this.navigate();
        } else {
            document.getElementById('app').style.display = 'none';
            document.getElementById('auth').style.display = 'flex';
        }
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    },

    async login() {
        const btn = document.getElementById('btn-login'); btn.disabled = true;
        try {
            const r = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: document.getElementById('inp-user').value, password: document.getElementById('inp-pass').value }) });
            if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'Credenciais inválidas'); }
            const data = await r.json();
            this.token = data.access_token;
            localStorage.setItem('e_token', this.token);
            this.handleAuth();
        } catch (err) { this.toast(err.message, 't-err'); }
        btn.disabled = false;
    },

    logout() { this.token = null; localStorage.removeItem('e_token'); this.handleAuth(); },

    buildNav() {
        const nav = document.getElementById('nav');
        nav.innerHTML = Object.entries(this.routes).map(([k, v]) =>
            `<button class="nav-item" data-route="${k}" onclick="EApp.go('${k}')"><i data-lucide="${v.icon}"></i><span>${v.title}</span></button>`
        ).join('');
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    },

    go(path) { location.hash = `#/${path}`; },

    navigate() {
        const hash = location.hash.replace('#/', '') || 'dashboard';
        let route = this.routes[hash];
        let params = {};
        if (!route && hash.startsWith('analysis/')) { route = this.routes['analysis']; params.id = hash.split('/')[1]; }
        if (!route) { location.hash = '#/dashboard'; return; }
        document.getElementById('page-title').textContent = route.title;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.route === hash));
        const page = document.getElementById('page');
        if (this[route.render]) this[route.render](page, params);
    },

    // === Dashboard ===
    async renderDashboard(el) {
        el.innerHTML = '<div class="grid grid-3" id="d-stats"></div><div class="card"><div class="card-title">Últimas Análises</div><div id="d-recent"></div></div>';
        try {
            const [contracts, analyses] = await Promise.all([this.api('GET', '/contracts'), this.api('GET', '/analysis')]);
            const completed = analyses.filter(a => a.status === 'completed');
            document.getElementById('d-stats').innerHTML = `
                <div class="card stat-card"><div class="icon" style="background:var(--primary-light);color:var(--primary);"><i data-lucide="file-text"></i></div><div class="value">${contracts.length}</div><div class="label">Contratos</div></div>
                <div class="card stat-card"><div class="icon" style="background:var(--accent-light);color:var(--accent);"><i data-lucide="scan"></i></div><div class="value">${analyses.length}</div><div class="label">Análises</div></div>
                <div class="card stat-card"><div class="icon" style="background:rgba(0,184,148,0.15);color:var(--success);"><i data-lucide="check-circle"></i></div><div class="value">${completed.length}</div><div class="label">Concluídas</div></div>`;
            if (!analyses.length) { document.getElementById('d-recent').innerHTML = '<div class="empty"><i data-lucide="scan"></i><p>Nenhuma análise ainda</p></div>'; }
            else { document.getElementById('d-recent').innerHTML = '<table class="tbl"><thead><tr><th>Modo</th><th>Status</th><th>Score</th><th>Data</th></tr></thead><tbody>' +
                analyses.slice(0, 5).map(a => `<tr style="cursor:pointer" onclick="EApp.go('analysis/${a.id}')"><td>${a.mode}</td><td><span class="badge ${a.status === 'completed' ? 'b-ok' : 'b-err'}">${a.status}</span></td><td>${a.score_risco || 0}</td><td>${new Date(a.created_at).toLocaleDateString('pt-BR')}</td></tr>`).join('') + '</tbody></table>'; }
            lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        } catch (err) { this.toast(err.message, 't-err'); }
    },

    // === Contracts ===
    async renderContracts(el) {
        el.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;"><h2>Contratos</h2><button class="btn-primary" style="width:auto;padding:10px 20px;" onclick="EApp.showUpload()"><i data-lucide="upload" style="width:16px;height:16px;"></i> Enviar</button></div><div id="c-list"></div>';
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        try {
            const contracts = await this.api('GET', '/contracts');
            if (!contracts.length) { document.getElementById('c-list').innerHTML = '<div class="empty"><i data-lucide="file-text"></i><p>Nenhum contrato</p></div>'; lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' }); return; }
            document.getElementById('c-list').innerHTML = '<table class="tbl"><thead><tr><th>Arquivo</th><th>Tipo</th><th>Tamanho</th><th>Status</th><th>Data</th><th>Ações</th></tr></thead><tbody>' +
                contracts.map(c => `<tr><td>${c.filename}</td><td>${c.file_type.toUpperCase()}</td><td>${(c.file_size_bytes/1024).toFixed(1)} KB</td><td><span class="badge ${c.status==='analyzed'?'b-ok':'b-info'}">${c.status}</span></td><td>${new Date(c.created_at).toLocaleDateString('pt-BR')}</td><td><button class="btn-sm btn-action" onclick="EApp.go('analysis?c=${c.id}')">Analisar</button> <button class="btn-sm btn-del" onclick="EApp.delContract('${c.id}')">Excluir</button></td></tr>`).join('') + '</tbody></table>';
        } catch (err) { this.toast(err.message, 't-err'); }
    },

    showUpload() {
        this.modal(`<h3 style="margin-bottom:16px;">Enviar Contrato</h3>
            <div class="upload-zone" onclick="document.getElementById('e-file').click()"><i data-lucide="cloud-upload"></i><p>Arraste ou clique — PDF, DOCX, TXT</p><input type="file" id="e-file" accept=".pdf,.docx,.txt" style="display:none"></div>
            <div id="e-prog" style="margin-top:12px;display:none;"><div class="progress"><div class="progress-fill" id="e-fill" style="width:0%"></div></div></div>`);
        document.getElementById('e-file').addEventListener('change', async e => {
            if (!e.target.files.length) return;
            document.getElementById('e-prog').style.display = 'block';
            document.getElementById('e-fill').style.width = '60%';
            try { const fd = new FormData(); fd.append('file', e.target.files[0]);
                await this.api('POST', '/contracts/upload', fd);
                document.getElementById('e-fill').style.width = '100%';
                this.toast('Contrato enviado!');
                setTimeout(() => { this.closeModal(); this.go('contracts'); }, 600);
            } catch (err) { this.toast(err.message, 't-err'); }
        });
    },

    async delContract(id) { try { await this.api('DELETE', `/contracts/${id}`); this.toast('Excluído!'); this.go('contracts'); } catch (e) { this.toast(e.message, 't-err'); } },

    // === Analysis ===
    async renderAnalysis(el, params) {
        if (params.id) return this.renderResult(el, params.id);
        const qs = new URLSearchParams(location.hash.split('?')[1] || '');
        const cid = qs.get('c');
        let opts = ''; try { const cs = await this.api('GET', '/contracts'); opts = cs.map(c => `<option value="${c.id}" ${c.id===cid?'selected':''}>${c.filename}</option>`).join(''); } catch (e) {}
        el.innerHTML = `<h2 style="margin-bottom:24px;">Nova Análise</h2>
            <div class="fg"><label>Contrato</label><select id="a-contract">${opts||'<option>Nenhum</option>'}</select></div>
            <label style="display:block;font-size:0.8125rem;font-weight:500;color:var(--text2);margin-bottom:12px;">Modo</label>
            <div class="grid grid-4" style="margin-bottom:24px;">
                <div class="mode-card" onclick="EApp._selMode('defensive',this)"><div style="font-size:24px;">🛡️</div><div class="mn">Defensivo</div><div class="md">Identifica riscos</div></div>
                <div class="mode-card" onclick="EApp._selMode('offensive',this)"><div style="font-size:24px;">⚔️</div><div class="mn">Ofensivo</div><div class="md">Encontra brechas</div></div>
                <div class="mode-card" onclick="EApp._selMode('audit',this)"><div style="font-size:24px;">🔍</div><div class="mn">Auditoria</div><div class="md">Compliance total</div></div>
                <div class="mode-card" onclick="EApp._selMode('shield',this)"><div style="font-size:24px;">🏛️</div><div class="mn">Shield</div><div class="md">Proteção completa</div></div>
            </div>
            <button class="btn-primary" id="btn-run" disabled onclick="EApp.runAnalysis()"><i data-lucide="scan" style="width:18px;height:18px;"></i> Iniciar Análise</button>
            <div id="a-prog" style="display:none;margin-top:24px;text-align:center;padding:32px;"><div style="animation:spin 1.5s linear infinite;display:inline-block;"><i data-lucide="loader-2" style="width:40px;height:40px;color:var(--primary);"></i></div><p style="margin-top:12px;">Analisando...</p><div class="progress" style="margin-top:12px;max-width:300px;margin-left:auto;margin-right:auto;"><div class="progress-fill" id="a-fill" style="width:10%;"></div></div></div>`;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    },

    _mode: null,
    _selMode(m, el) { this._mode = m; document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('sel')); el.classList.add('sel'); document.getElementById('btn-run').disabled = false; },

    async runAnalysis() {
        const cid = document.getElementById('a-contract').value;
        if (!cid || !this._mode) return;
        document.getElementById('btn-run').disabled = true;
        document.getElementById('a-prog').style.display = 'block';
        let pct = 10; const fill = document.getElementById('a-fill');
        const iv = setInterval(() => { pct = Math.min(pct + Math.random() * 15, 90); fill.style.width = pct + '%'; }, 800);
        try { const r = await this.api('POST', '/analysis', { contract_id: cid, mode: this._mode });
            clearInterval(iv); fill.style.width = '100%';
            this.toast('Análise concluída!');
            setTimeout(() => this.go(`analysis/${r.id}`), 600);
        } catch (err) { clearInterval(iv); this.toast(err.message, 't-err'); document.getElementById('btn-run').disabled = false; document.getElementById('a-prog').style.display = 'none'; }
    },

    async renderResult(el, id) {
        try { const a = await this.api('GET', `/analysis/${id}`);
            const rc = a.score_risco >= 80 ? 'var(--danger)' : a.score_risco >= 60 ? '#FF6B6B' : a.score_risco >= 40 ? 'var(--warning)' : 'var(--success)';
            el.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;"><h2>${a.mode.charAt(0).toUpperCase()+a.mode.slice(1)} — Resultado</h2><button class="btn-sm btn-action" onclick="EApp.exportPDF('${a.id}')"><i data-lucide="download" style="width:14px;height:14px;"></i> PDF</button></div>
                <div class="grid grid-2"><div class="card"><div class="card-title">Resumo</div><p style="color:var(--text2);line-height:1.6;font-size:0.8125rem;">${a.resumo_executivo || 'Sem resumo.'}</p>
                <div style="display:flex;gap:24px;margin-top:16px;"><div><span style="font-size:0.6875rem;color:var(--text3);text-transform:uppercase;">Modelo</span><div style="font-weight:600;">${a.model_used || 'N/A'}</div></div><div><span style="font-size:0.6875rem;color:var(--text3);text-transform:uppercase;">Tokens</span><div style="font-weight:600;">${a.tokens_used || 0}</div></div><div><span style="font-size:0.6875rem;color:var(--text3);text-transform:uppercase;">Custo</span><div style="font-weight:600;">$${(a.cost_usd || 0).toFixed(4)}</div></div></div></div>
                <div class="card" style="text-align:center;"><div style="width:100px;height:100px;border-radius:50%;border:5px solid ${rc};display:flex;align-items:center;justify-content:center;margin:0 auto;"><span style="font-size:1.75rem;font-weight:800;color:${rc};">${a.score_risco||0}</span></div><p style="margin-top:8px;color:var(--text2);font-size:0.8125rem;">Score de Risco</p></div></div>
                <div class="card"><div class="card-title">Achados (${a.total_achados||0})</div><div id="findings">${(a.achados||[]).map((f,i)=>`<div class="finding" id="f-${i}"><div class="finding-hdr" onclick="document.getElementById('f-${i}').classList.toggle('open')"><span class="badge ${f.severidade==='CRÍTICO'||f.severidade==='CRITICO'?'b-err':f.severidade==='ALTO'?'b-warn':'b-info'}">${f.severidade}</span><span style="flex:1;font-weight:600;">${f.titulo}</span><i data-lucide="chevron-down" style="width:14px;height:14px;"></i></div><div class="finding-body">${f.clausula?`<div class="finding-lbl">Cláusula</div><div class="finding-val">${f.clausula}</div>`:''}${f.descricao?`<div class="finding-lbl">Descrição</div><div class="finding-val">${f.descricao}</div>`:''}${f.recomendacao?`<div class="finding-lbl">Recomendação</div><div class="finding-val">${f.recomendacao}</div>`:''}</div></div>`).join('')}</div></div>`;
            lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        } catch (err) { el.innerHTML = '<div class="empty"><p>Erro ao carregar análise.</p></div>'; this.toast(err.message, 't-err'); }
    },

    async exportPDF(id) { try { const blob = await this.api('POST', `/reports/export/${id}`); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `relatorio_${id.substring(0,8)}.pdf`; a.click(); this.toast('PDF exportado!'); } catch (e) { this.toast(e.message, 't-err'); } },

    // === Stats ===
    async renderStats(el) {
        el.innerHTML = '<h2 style="margin-bottom:24px;">Estatísticas de Uso</h2><div class="grid grid-3" id="s-stats"></div><div class="card"><div class="card-title">Análises por Modo</div><div class="chart-box"><canvas id="s-chart"></canvas></div></div>';
        try {
            const analyses = await this.api('GET', '/analysis');
            const total = analyses.length, completed = analyses.filter(a => a.status === 'completed').length;
            const totalTokens = analyses.reduce((s, a) => s + (a.tokens_used || 0), 0);
            document.getElementById('s-stats').innerHTML = `
                <div class="card stat-card"><div class="icon" style="background:var(--primary-light);color:var(--primary);"><i data-lucide="scan"></i></div><div class="value">${total}</div><div class="label">Total Análises</div></div>
                <div class="card stat-card"><div class="icon" style="background:rgba(0,184,148,0.15);color:var(--success);"><i data-lucide="check-circle"></i></div><div class="value">${completed}</div><div class="label">Concluídas</div></div>
                <div class="card stat-card"><div class="icon" style="background:rgba(253,203,110,0.15);color:var(--warning);"><i data-lucide="coins"></i></div><div class="value">${totalTokens.toLocaleString()}</div><div class="label">Tokens Usados</div></div>`;
            lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
            const modes = {}; analyses.forEach(a => { modes[a.mode] = (modes[a.mode] || 0) + 1; });
            new Chart(document.getElementById('s-chart'), { type: 'bar', data: { labels: Object.keys(modes), datasets: [{ label: 'Análises', data: Object.values(modes), backgroundColor: ['#6C5CE7', '#FF6B6B', '#FDCB6E', '#00B894'], borderRadius: 8 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { color: '#6B6B8D' } }, y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#6B6B8D' }, beginAtZero: true } } } });
        } catch (err) { this.toast(err.message, 't-err'); }
    },

    // === Settings (BYOK) ===
    async renderSettings(el) {
        el.innerHTML = '<h2 style="margin-bottom:24px;">Configurações — Modelos IA</h2><div id="s-form"></div>';
        try { const s = await this.api('GET', '/settings/byok');
            el.querySelector('#s-form').innerHTML = `<div class="card">
                <div class="grid grid-2"><div class="fg"><label>Modelo Primário</label><input id="s-pm" value="${s.primary_model}"></div><div class="fg"><label>Modelo Fallback</label><input id="s-fm" value="${s.fallback_model}"></div></div>
                <div class="fg"><label>Temperature (${s.temperature})</label><input type="range" id="s-temp" min="0" max="2" step="0.1" value="${s.temperature}" style="width:100%;"></div>
                <div style="display:flex;gap:12px;margin-top:12px;">
                    <span class="badge ${s.openai_configured ? 'b-ok' : 'b-err'}">OpenAI ${s.openai_configured ? '✓' : '✗'}</span>
                    <span class="badge ${s.anthropic_configured ? 'b-ok' : 'b-err'}">Anthropic ${s.anthropic_configured ? '✓' : '✗'}</span>
                </div>
                <h3 style="margin-top:24px;margin-bottom:12px;font-size:0.875rem;">Atualizar API Keys</h3>
                <div class="fg"><label>OpenAI Key</label><input type="password" id="s-oai" placeholder="sk-..."></div>
                <div class="fg"><label>Anthropic Key</label><input type="password" id="s-ant" placeholder="sk-ant-..."></div>
                <button class="btn-primary" onclick="EApp.saveSettings()"><i data-lucide="save" style="width:16px;height:16px;"></i> Salvar</button>
            </div>`;
            lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        } catch (err) { this.toast(err.message, 't-err'); }
    },

    async saveSettings() {
        const data = {};
        const pm = document.getElementById('s-pm').value; if (pm) data.primary_model = pm;
        const fm = document.getElementById('s-fm').value; if (fm) data.fallback_model = fm;
        data.temperature = parseFloat(document.getElementById('s-temp').value);
        const oai = document.getElementById('s-oai').value; if (oai) data.openai_api_key = oai;
        const ant = document.getElementById('s-ant').value; if (ant) data.anthropic_api_key = ant;
        try { await this.api('PUT', '/settings/byok', data); this.toast('Configurações salvas!'); } catch (e) { this.toast(e.message, 't-err'); }
    },
};

document.addEventListener('DOMContentLoaded', () => EApp.init());
