/**
 * LegalShield AI — Admin Testing Page
 * Área completa de testes: IA + Simulação de Contratos por tipo
 */
const PageAdminTesting = {
    async render(container) {
        let models = [];
        try { const s = await API.getLLMSettings(); models = s.supported_models || []; } catch (e) {}
        const opts = models.map(m => `<option value="${m.id}">${m.name} (${m.provider})</option>`).join('');

        container.innerHTML = `<div class="animate-fade">
            <h2 class="mb-2">🧪 Área de Testes</h2>
            <p class="text-muted mb-6">Teste modelos de IA e simule cenários de contratos</p>

            <!-- Tabs -->
            <div class="tabs mb-6">
                <button class="tab-btn active" onclick="PageAdminTesting.showTab('ia')">🤖 Testar Modelo IA</button>
                <button class="tab-btn" onclick="PageAdminTesting.showTab('upload')">📎 Testar com Arquivo</button>
                <button class="tab-btn" onclick="PageAdminTesting.showTab('contratos')">📄 Simular Contratos</button>
            </div>

            <!-- Tab: IA Test -->
            <div id="tab-ia">
                <div class="card">
                    <div class="grid grid-2">
                        <div class="form-group">
                            <label class="form-label">Modelo</label>
                            <select class="form-select" id="test-model">${opts}</select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Cenário de Teste</label>
                            <select class="form-select" id="test-scenario" onchange="PageAdminTesting.loadScenario()">
                                <option value="custom">📝 Prompt Personalizado</option>
                                <option value="existente">📄 Contrato Existente (já assinado)</option>
                                <option value="enviar">📤 Contrato a Enviar (para assinatura)</option>
                                <option value="receber">📥 Contrato a Receber (de terceiros)</option>
                                <option value="risco">⚠️ Contrato com Cláusulas Abusivas</option>
                                <option value="compliance">✅ Verificação de Compliance</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Prompt de Teste</label>
                        <textarea class="form-textarea" id="test-prompt" rows="6">Responda em uma frase: Qual é a função principal de um contrato jurídico?</textarea>
                    </div>
                    <button class="btn btn-primary" id="btn-test" onclick="PageAdminTesting.runTest()">
                        <i data-lucide="play"></i> Executar Teste
                    </button>
                </div>
                <div id="test-result" class="hidden"></div>
            </div>

            <!-- Tab: Upload & Analyze -->
            <div id="tab-upload" style="display:none;">
                <div class="card mb-6">
                    <h3 class="mb-2">📎 Enviar Contrato para Análise</h3>
                    <p class="text-muted text-sm mb-6">Faça upload de um arquivo (PDF, DOCX, TXT) e execute a análise de IA em tempo real.</p>

                    <div class="upload-zone" id="dev-upload-zone"
                         onclick="document.getElementById('dev-file-input').click()"
                         ondragover="event.preventDefault(); this.classList.add('drag-over')"
                         ondragleave="this.classList.remove('drag-over')"
                         ondrop="event.preventDefault(); this.classList.remove('drag-over'); PageAdminTesting.handleFileDrop(event)">
                        <i data-lucide="upload-cloud"></i>
                        <h3>Arraste o arquivo aqui</h3>
                        <p>ou clique para selecionar — PDF, DOCX ou TXT (até 20MB)</p>
                        <input type="file" id="dev-file-input" accept=".pdf,.docx,.txt,.doc" style="display:none"
                               onchange="PageAdminTesting.handleFileSelect(event)">
                    </div>

                    <div id="dev-file-info" class="hidden mt-4">
                        <div class="flex items-center gap-3 p-4" style="background:var(--bg-secondary);border-radius:var(--radius-md);">
                            <i data-lucide="file-text" style="color:var(--color-primary);"></i>
                            <div style="flex:1;">
                                <div class="text-semibold" id="dev-file-name"></div>
                                <div class="text-xs text-muted" id="dev-file-size"></div>
                            </div>
                            <button class="btn-icon" onclick="PageAdminTesting.clearFile()" title="Remover">
                                <i data-lucide="x"></i>
                            </button>
                        </div>
                    </div>

                    <div class="grid grid-2 mt-6">
                        <div class="form-group">
                            <label class="form-label">Modelo de IA</label>
                            <select class="form-select" id="dev-upload-model">${opts}</select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Modo de Análise</label>
                            <select class="form-select" id="dev-upload-mode">
                                <option value="defensive">🛡️ Defensivo</option>
                                <option value="offensive">⚔️ Ofensivo</option>
                                <option value="audit">🔍 Auditoria</option>
                                <option value="shield">🏛️ Shield (Completo)</option>
                            </select>
                        </div>
                    </div>

                    <button class="btn btn-primary btn-lg" id="btn-upload-analyze" onclick="PageAdminTesting.uploadAndAnalyze()" disabled>
                        <i data-lucide="sparkles"></i> Enviar e Analisar
                    </button>
                </div>

                <div id="dev-upload-result" class="hidden"></div>
            </div>

            <!-- Tab: Contract Simulation -->
            <div id="tab-contratos" style="display:none;">
                <div class="grid grid-3 mb-6 stagger">
                    <!-- Contrato Existente -->
                    <div class="card" style="border-left:3px solid var(--tag-existente);">
                        <div class="flex items-center gap-3 mb-4">
                            <span style="font-size:28px;">📄</span>
                            <div>
                                <div class="text-semibold">Contrato Existente</div>
                                <div class="text-xs text-muted">Já assinado — análise de riscos retroativa</div>
                            </div>
                        </div>
                        <p class="text-sm text-muted mb-4">
                            Simula a análise de um contrato que já foi assinado. O sistema identifica cláusulas 
                            problemáticas, riscos ocultos e sugere ações corretivas.
                        </p>
                        <div class="flex gap-2">
                            <button class="btn btn-sm btn-primary" onclick="PageAdminTesting.simulateContract('existente','defensive')">
                                🛡️ Defensivo
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="PageAdminTesting.simulateContract('existente','audit')">
                                🔍 Auditoria
                            </button>
                        </div>
                    </div>

                    <!-- Contrato a Enviar -->
                    <div class="card" style="border-left:3px solid var(--tag-enviar);">
                        <div class="flex items-center gap-3 mb-4">
                            <span style="font-size:28px;">📤</span>
                            <div>
                                <div class="text-semibold">Contrato a Enviar</div>
                                <div class="text-xs text-muted">Para assinatura — revisão antes do envio</div>
                            </div>
                        </div>
                        <p class="text-sm text-muted mb-4">
                            Simula a revisão de um contrato que será enviado para a outra parte. 
                            O foco é garantir que protege seus interesses antes da assinatura.
                        </p>
                        <div class="flex gap-2">
                            <button class="btn btn-sm btn-primary" onclick="PageAdminTesting.simulateContract('enviar','offensive')">
                                ⚔️ Ofensivo
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="PageAdminTesting.simulateContract('enviar','shield')">
                                🏛️ Shield
                            </button>
                        </div>
                    </div>

                    <!-- Contrato a Receber -->
                    <div class="card" style="border-left:3px solid var(--tag-receber);">
                        <div class="flex items-center gap-3 mb-4">
                            <span style="font-size:28px;">📥</span>
                            <div>
                                <div class="text-semibold">Contrato a Receber</div>
                                <div class="text-xs text-muted">De terceiros — análise antes de aceitar</div>
                            </div>
                        </div>
                        <p class="text-sm text-muted mb-4">
                            Simula a análise de um contrato recebido de outra empresa. 
                            O sistema identifica termos desfavoráveis e cláusulas a negociar.
                        </p>
                        <div class="flex gap-2">
                            <button class="btn btn-sm btn-primary" onclick="PageAdminTesting.simulateContract('receber','defensive')">
                                🛡️ Defensivo
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="PageAdminTesting.simulateContract('receber','offensive')">
                                ⚔️ Ofensivo
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Resultado da Simulação -->
                <div id="sim-result" class="hidden"></div>
            </div>
        </div>`;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    },

    _selectedFile: null,

    // === Tab switching ===
    showTab(tab) {
        const tabs = { ia: 0, upload: 1, contratos: 2 };
        ['tab-ia', 'tab-upload', 'tab-contratos'].forEach((id, i) => {
            document.getElementById(id).style.display = Object.values(tabs)[i] === tabs[tab] ? 'block' : 'none';
        });
        document.querySelectorAll('.tabs .tab-btn').forEach((btn, i) => {
            btn.classList.toggle('active', i === tabs[tab]);
        });
        if (tab === 'upload') {
            lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        }
    },

    // === File Upload Handlers ===
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) this._setFile(file);
    },

    handleFileDrop(event) {
        const file = event.dataTransfer.files[0];
        if (file) this._setFile(file);
    },

    _setFile(file) {
        const maxSize = 20 * 1024 * 1024;
        const allowed = ['.pdf', '.docx', '.doc', '.txt'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        if (!allowed.includes(ext)) {
            Components.toast('Formato não suportado. Use PDF, DOCX ou TXT.', 'warning');
            return;
        }
        if (file.size > maxSize) {
            Components.toast('Arquivo muito grande. Máximo: 20MB.', 'warning');
            return;
        }

        this._selectedFile = file;
        document.getElementById('dev-file-info').classList.remove('hidden');
        document.getElementById('dev-file-name').textContent = file.name;
        document.getElementById('dev-file-size').textContent = this._formatSize(file.size);
        document.getElementById('dev-upload-zone').style.display = 'none';
        document.getElementById('btn-upload-analyze').disabled = false;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
    },

    clearFile() {
        this._selectedFile = null;
        document.getElementById('dev-file-info').classList.add('hidden');
        document.getElementById('dev-upload-zone').style.display = '';
        document.getElementById('btn-upload-analyze').disabled = true;
        document.getElementById('dev-file-input').value = '';
    },

    _formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    // === Upload & Analyze ===
    async uploadAndAnalyze() {
        if (!this._selectedFile) { Components.toast('Selecione um arquivo', 'warning'); return; }

        const btn = document.getElementById('btn-upload-analyze');
        btn.disabled = true; btn.classList.add('btn-loading');

        const mode = document.getElementById('dev-upload-mode').value;
        const resultDiv = document.getElementById('dev-upload-result');
        resultDiv.classList.remove('hidden');
        resultDiv.innerHTML = `<div class="card" style="text-align:center;padding:var(--space-8);">
            <div style="animation:spin 1.5s linear infinite;display:inline-block;">
                <i data-lucide="loader-2" style="width:40px;height:40px;color:var(--color-primary);"></i>
            </div>
            <h3 class="mt-4">Enviando contrato...</h3>
            <p class="text-muted">Fazendo upload e preparando análise</p>
            <div class="progress-bar mt-4" style="max-width:300px;margin:0 auto;">
                <div class="progress-fill" id="upload-progress" style="width:15%;"></div>
            </div>
        </div>`;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });

        const fill = document.getElementById('upload-progress');
        let pct = 15;
        const iv = setInterval(() => { pct = Math.min(pct + Math.random() * 8, 90); fill.style.width = pct + '%'; }, 800);

        try {
            // 1. Upload
            fill.style.width = '30%';
            const contract = await API.uploadContract(this._selectedFile);
            const contractId = contract.id || contract.contract_id;

            // 2. Analyze
            fill.style.width = '60%';
            resultDiv.querySelector('h3').textContent = 'Analisando com IA...';
            resultDiv.querySelector('p').textContent = 'Modo: ' + mode;

            const analysis = await API.createAnalysis(contractId, mode);

            clearInterval(iv);
            fill.style.width = '100%';

            setTimeout(() => {
                const score = analysis.score_risco || 0;
                const scoreColor = score >= 70 ? 'var(--severity-critico)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-success)';
                const achados = analysis.achados || analysis.findings || [];

                resultDiv.innerHTML = `<div class="card animate-fade">
                    <div class="flex items-center justify-between mb-4">
                        <h3>Resultado da Análise</h3>
                        <span class="badge badge-success">✓ Concluído</span>
                    </div>

                    <div class="grid grid-3 mb-6">
                        <div class="meta-item">
                            <span class="meta-label">Arquivo</span>
                            <span class="meta-value">${this._selectedFile.name}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Modo</span>
                            <span class="meta-value">${mode}</span>
                        </div>
                        <div style="text-align:center;">
                            <div style="width:70px;height:70px;border-radius:50%;border:4px solid ${scoreColor};display:flex;align-items:center;justify-content:center;margin:0 auto;">
                                <span style="font-size:1.3rem;font-weight:800;color:${scoreColor};">${score}</span>
                            </div>
                            <div class="text-xs text-muted mt-1">Score de Risco</div>
                        </div>
                    </div>

                    ${analysis.resumo_executivo ? `
                        <h4 class="mb-2">Resumo Executivo</h4>
                        <div style="background:var(--bg-primary);border:1px solid var(--glass-border);border-radius:var(--radius-md);padding:var(--space-5);margin-bottom:var(--space-5);">
                            <p style="color:var(--text-secondary);line-height:1.7;font-size:var(--font-size-sm);white-space:pre-wrap;">${analysis.resumo_executivo}</p>
                        </div>
                    ` : ''}

                    ${achados.length ? `
                        <h4 class="mb-3">Achados (${achados.length})</h4>
                        ${achados.map(a => `
                            <div class="finding-card mb-3">
                                <div class="finding-header" onclick="this.parentElement.classList.toggle('expanded')">
                                    <span class="badge severity-${(a.severidade||'medio').toLowerCase()}">${a.severidade||'MÉDIO'}</span>
                                    <span style="flex:1;">${a.titulo||'Achado'}</span>
                                    <i data-lucide="chevron-down" style="width:16px;height:16px;"></i>
                                </div>
                                <div class="finding-body">
                                    ${a.descricao ? `<div class="finding-detail"><div class="finding-detail-label">Descrição</div><div class="finding-detail-value">${a.descricao}</div></div>` : ''}
                                    ${a.clausula ? `<div class="finding-detail"><div class="finding-detail-label">Cláusula</div><div class="finding-detail-value">${a.clausula}</div></div>` : ''}
                                    ${a.recomendacao ? `<div class="finding-detail"><div class="finding-detail-label">Recomendação</div><div class="finding-detail-value">${a.recomendacao}</div></div>` : ''}
                                </div>
                            </div>
                        `).join('')}
                    ` : ''}

                    <div class="flex gap-3 mt-6">
                        <button class="btn btn-secondary" onclick="PageAdminTesting.clearFile(); PageAdminTesting.showTab('upload');">
                            <i data-lucide="plus"></i> Novo Teste
                        </button>
                        <button class="btn btn-primary" onclick="window.location.hash='#/analysis/${analysis.id}'">
                            <i data-lucide="external-link"></i> Ver Análise Completa
                        </button>
                    </div>
                </div>`;
                lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
            }, 500);

        } catch (err) {
            clearInterval(iv);
            resultDiv.innerHTML = `<div class="card">
                <div class="flex items-center gap-3 mb-3">
                    <span class="badge badge-danger">✗ Erro</span>
                </div>
                <p class="text-muted">${err.message}</p>
                <p class="text-sm text-muted mt-4">💡 Verifique se a API key do modelo está configurada em <strong>Modelos IA</strong>.</p>
            </div>`;
        }

        btn.disabled = false; btn.classList.remove('btn-loading');
    },

    // === Prompt Scenarios ===
    SCENARIOS: {
        existente: `Analise este contrato JÁ ASSINADO entre as partes. Identifique:
1. Cláusulas que podem gerar riscos futuros para o contratante
2. Obrigações que podem ter sido descumpridas
3. Prazo de vigência e condições de rescisão
4. Penalidades previstas

Contrato de exemplo:
---
CONTRATO DE PRESTAÇÃO DE SERVIÇOS Nº 2024/0847
CONTRATANTE: Empresa Alpha Ltda. / CONTRATADA: TechServ S.A.
Vigência: 01/01/2024 a 31/12/2026 (36 meses)
Cláusula 5 — A CONTRATADA poderá alterar unilateralmente os preços mediante aviso prévio de 15 dias.
Cláusula 8 — O foro para resolver litígios será o da comarca da sede da CONTRATADA.
Cláusula 12 — Multa rescisória de 50% do valor restante do contrato.
Cláusula 15 — Renovação automática por período igual se não houver denúncia com 90 dias de antecedência.
---`,

        enviar: `Revise este contrato que SERÁ ENVIADO para assinatura da outra parte. Verifique:
1. Se as cláusulas protegem adequadamente nossos interesses
2. Se há termos que a outra parte pode rejeitar
3. Se está em conformidade com o Código Civil e CDC
4. Sugestões de melhoria antes do envio

Contrato de exemplo:
---
CONTRATO DE LOCAÇÃO COMERCIAL
LOCADOR: Investimentos Beta S.A. / LOCATÁRIO: (aguardando)
Valor mensal: R$ 15.000,00 com reajuste anual pelo IGPM
Cláusula 3 — Garantia de 6 meses de aluguel em caução.
Cláusula 7 — Locatário é responsável por TODAS as manutenções, inclusive estruturais.
Cláusula 9 — Proibida a sublocação ou cessão sem autorização prévia por escrito.
Cláusula 11 — Em caso de desocupação antecipada, multa de 3 aluguéis vigentes.
---`,

        receber: `Analise este contrato RECEBIDO de outra empresa antes de aceitarmos. Identifique:
1. Cláusulas desfavoráveis ou abusivas para nossa empresa
2. Termos que devemos negociar antes de assinar
3. Riscos financeiros e obrigações excessivas
4. Comparação com práticas de mercado

Contrato de exemplo:
---
CONTRATO DE FORNECIMENTO DE SOFTWARE (SaaS)
FORNECEDOR: CloudTech Corp. / CLIENTE: (nossa empresa)
Valor: R$ 8.500/mês com mínimo de 24 meses
Cláusula 4 — O FORNECEDOR poderá suspender os serviços em caso de atraso superior a 5 dias.
Cláusula 6 — Dados inseridos na plataforma pertencem ao FORNECEDOR durante a vigência.
Cláusula 9 — Limitação de responsabilidade do FORNECEDOR ao valor de 1 (uma) mensalidade.
Cláusula 13 — Reajuste anual podendo superar a inflação em até 5 pontos percentuais.
Cláusula 16 — Non-compete de 12 meses após rescisão para soluções similares.
---`,

        risco: `Analise este contrato que contém cláusulas potencialmente abusivas:
---
CONTRATO DE ADESÃO DE SERVIÇOS
Cláusula 2 — A empresa pode alterar qualquer termo deste contrato sem aviso prévio.
Cláusula 5 — O cliente renuncia ao direito de reclamação em qualquer instância.
Cláusula 8 — Multa de 100% do valor total em caso de cancelamento.
Cláusula 11 — Eleição de foro em comarca distante da residência do consumidor.
Cláusula 14 — Dados pessoais podem ser compartilhados sem restrições.
---`,

        compliance: `Faça uma análise de compliance deste contrato verificando:
1. Conformidade com LGPD (Lei 13.709/2018)
2. Aderência ao Código de Defesa do Consumidor
3. Normas trabalhistas aplicáveis
4. Regulamentações setoriais

Contrato de exemplo:
---
TERMO DE USO E POLÍTICA DE PRIVACIDADE
Coleta de dados: nome, CPF, endereço, dados bancários, biometria facial
Finalidade: "melhorar a experiência do usuário e parceiros comerciais"
Compartilhamento: com "empresas do grupo e parceiros selecionados"
Retenção: "pelo tempo necessário para cumprir as finalidades descritas"
Consentimento: obtido por checkbox pré-marcado na página de cadastro
---`,
    },

    loadScenario() {
        const scenario = document.getElementById('test-scenario').value;
        const prompt = document.getElementById('test-prompt');
        if (scenario !== 'custom' && this.SCENARIOS[scenario]) {
            prompt.value = this.SCENARIOS[scenario];
        }
    },

    // === Run IA Test ===
    async runTest() {
        const model = document.getElementById('test-model').value;
        const prompt = document.getElementById('test-prompt').value;
        if (!prompt.trim()) { Components.toast('Preencha o prompt', 'warning'); return; }

        const btn = document.getElementById('btn-test');
        btn.disabled = true; btn.classList.add('btn-loading');

        const resultDiv = document.getElementById('test-result');
        resultDiv.classList.remove('hidden');
        resultDiv.innerHTML = `<div class="test-result-panel">
            <div class="flex items-center gap-3">
                <div style="animation:spin 1s linear infinite;">
                    <i data-lucide="loader-2" style="width:20px;height:20px;color:var(--color-primary)"></i>
                </div>
                <span>Testando <strong>${model}</strong>...</span>
            </div>
        </div>`;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });

        try {
            const r = await API.testLLM(model, prompt);
            resultDiv.innerHTML = `<div class="test-result-panel">
                <div class="flex items-center gap-3 mb-4">
                    ${r.success
                        ? '<span class="badge badge-success">✓ Sucesso</span>'
                        : '<span class="badge badge-danger">✗ Falhou</span>'}
                    <span class="text-semibold">${r.model}</span>
                </div>
                ${r.success ? `
                    <div class="flex gap-6 mb-4">
                        <div class="meta-item">
                            <span class="meta-label">Tokens</span>
                            <span class="meta-value">${r.tokens_used}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Latência</span>
                            <span class="meta-value">${r.latency_seconds}s</span>
                        </div>
                    </div>
                    <h4 class="mb-2">Resposta:</h4>
                    <pre>${r.response}</pre>
                ` : `
                    <h4 class="mb-2">Erro:</h4>
                    <pre style="color:var(--color-danger)">${r.error}</pre>
                `}
            </div>`;
        } catch (err) {
            resultDiv.innerHTML = `<div class="test-result-panel">
                <span class="badge badge-danger">Erro de Conexão</span>
                <pre style="color:var(--color-danger)">${err.message}</pre>
            </div>`;
        }
        btn.disabled = false; btn.classList.remove('btn-loading');
    },

    // === Simulate Contract Analysis ===
    async simulateContract(contractType, mode) {
        const typeLabels = {
            existente: '📄 Contrato Existente (já assinado)',
            enviar: '📤 Contrato a Enviar',
            receber: '📥 Contrato a Receber',
        };
        const modeLabels = {
            defensive: '🛡️ Defensivo',
            offensive: '⚔️ Ofensivo',
            audit: '🔍 Auditoria',
            shield: '🏛️ Shield',
        };

        const resultDiv = document.getElementById('sim-result');
        resultDiv.classList.remove('hidden');
        resultDiv.innerHTML = `<div class="card" style="text-align:center;padding:var(--space-8);">
            <div style="animation:spin 1.5s linear infinite;display:inline-block;">
                <i data-lucide="loader-2" style="width:40px;height:40px;color:var(--color-primary);"></i>
            </div>
            <h3 class="mt-4">Simulando análise...</h3>
            <p class="text-muted">${typeLabels[contractType]} · Modo ${modeLabels[mode]}</p>
            <div class="progress-bar mt-4" style="max-width:300px;margin:0 auto;">
                <div class="progress-fill" id="sim-fill" style="width:10%;"></div>
            </div>
        </div>`;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });

        // Progress animation
        let pct = 10;
        const fill = document.getElementById('sim-fill');
        const iv = setInterval(() => { pct = Math.min(pct + Math.random() * 12, 85); fill.style.width = pct + '%'; }, 600);

        try {
            // Try to get model settings
            let model = 'openai/gpt-4o';
            try { const s = await API.getLLMSettings(); model = s.primary_model; } catch (e) {}

            const prompt = this.SCENARIOS[contractType];
            const r = await API.testLLM(model, `Modo de análise: ${mode.toUpperCase()}\n\n${prompt}`);

            clearInterval(iv);
            fill.style.width = '100%';

            setTimeout(() => {
                const riskScore = contractType === 'receber' ? 72 : contractType === 'existente' ? 55 : 35;
                const riskColor = riskScore >= 70 ? 'var(--severity-critico)' : riskScore >= 50 ? 'var(--color-warning)' : 'var(--color-success)';

                resultDiv.innerHTML = `<div class="card animate-fade">
                    <div class="flex items-center justify-between mb-4">
                        <h3>Resultado da Simulação</h3>
                        <div class="flex gap-2">
                            ${Components.contractTag(contractType)}
                            <span class="badge badge-primary">${modeLabels[mode]}</span>
                        </div>
                    </div>

                    <div class="grid grid-2 mb-6">
                        <div>
                            <div class="flex gap-6 mb-4">
                                <div class="meta-item">
                                    <span class="meta-label">Modelo</span>
                                    <span class="meta-value">${r.model || model}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Tokens</span>
                                    <span class="meta-value">${r.tokens_used || 0}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Latência</span>
                                    <span class="meta-value">${r.latency_seconds || 0}s</span>
                                </div>
                            </div>
                        </div>
                        <div style="text-align:center;">
                            <div style="width:80px;height:80px;border-radius:50%;border:4px solid ${riskColor};display:flex;align-items:center;justify-content:center;margin:0 auto;">
                                <span style="font-size:1.5rem;font-weight:800;color:${riskColor};">${riskScore}</span>
                            </div>
                            <div class="text-xs text-muted mt-2">Score Estimado</div>
                        </div>
                    </div>

                    ${r.success ? `
                        <h4 class="mb-2">Análise da IA:</h4>
                        <div style="background:var(--bg-primary);border:1px solid var(--glass-border);border-radius:var(--radius-md);padding:var(--space-5);max-height:400px;overflow-y:auto;">
                            <pre style="white-space:pre-wrap;word-break:break-word;color:var(--text-secondary);font-size:var(--font-size-sm);line-height:1.7;">${r.response}</pre>
                        </div>
                    ` : `
                        <div class="flex items-center gap-3 mb-4">
                            <span class="badge badge-danger">✗ Erro no modelo</span>
                        </div>
                        <pre style="color:var(--color-danger);font-size:var(--font-size-sm);">${r.error}</pre>
                        <p class="text-sm text-muted mt-4">💡 Verifique se a API key do modelo está configurada em <strong>Modelos IA → API Keys</strong></p>
                    `}

                    <div class="flex gap-3 mt-6">
                        <button class="btn btn-secondary" onclick="PageAdminTesting.simulateContract('${contractType}','${mode}')">
                            <i data-lucide="refresh-cw"></i> Repetir
                        </button>
                        <button class="btn btn-primary" onclick="PageAdminTesting.showTab('ia')">
                            <i data-lucide="settings"></i> Ajustar Modelo
                        </button>
                    </div>
                </div>`;
                lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
            }, 500);

        } catch (err) {
            clearInterval(iv);
            resultDiv.innerHTML = `<div class="card">
                <span class="badge badge-danger">✗ Erro</span>
                <p class="text-muted mt-2">${err.message}</p>
                <p class="text-sm text-muted mt-4">💡 Configure uma API key em <strong>Modelos IA</strong> para testar.</p>
            </div>`;
        }
    },
};
