/**
 * LegalShield AI — Dashboard Page
 * Cards resumo + últimas análises + gráfico.
 */

const PageDashboard = {
    async render(container) {
        container.innerHTML = `
            <div class="dashboard-welcome animate-fade">
                <h2>Bem-vindo ao LegalShield AI</h2>
                <p class="text-muted">Visão geral das suas análises jurídicas</p>
            </div>
            <div class="grid grid-4 stagger" id="dash-stats">
                ${Components.skeleton('card', 4)}
            </div>
            <div class="grid grid-2 mt-6">
                <div class="card" id="dash-chart-card">
                    <div class="card-header">
                        <span class="card-title">Análises nos últimos 30 dias</span>
                    </div>
                    <div class="chart-container"><canvas id="dash-chart"></canvas></div>
                </div>
                <div class="card" id="dash-recent">
                    <div class="card-header">
                        <span class="card-title">Últimas Análises</span>
                        <a class="btn btn-sm btn-secondary" onclick="App.navigateTo('history')">Ver todas</a>
                    </div>
                    <div id="dash-recent-list">${Components.skeleton('text', 5)}</div>
                </div>
            </div>
        `;
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        this.loadData();
    },

    async loadData() {
        try {
            const [contractsData, analysesData] = await Promise.all([
                API.listContracts(1, 1),
                API.listAnalyses(null, 1),
            ]);

            const totalContracts = contractsData.total || 0;
            const totalAnalyses = analysesData.total || 0;
            const analyses = analysesData.analyses || [];

            // Calcular score médio
            const completedAnalyses = analyses.filter(a => a.status === 'completed' && a.score_risco > 0);
            const avgScore = completedAnalyses.length > 0
                ? Math.round(completedAnalyses.reduce((sum, a) => sum + a.score_risco, 0) / completedAnalyses.length)
                : 0;

            // Stat cards
            document.getElementById('dash-stats').innerHTML = `
                ${Components.statCard('file-text', totalContracts, 'Contratos Totais', null, 'primary')}
                ${Components.statCard('scan', totalAnalyses, 'Análises Realizadas', null, 'accent')}
                ${Components.statCard('alert-triangle', avgScore + '/100', 'Score Médio de Risco', null, avgScore > 60 ? 'danger' : 'success')}
                ${Components.statCard('shield-check', completedAnalyses.length, 'Análises Concluídas', null, 'success')}
            `;

            // Recent analyses
            const recent = analyses.slice(0, 5);
            if (recent.length === 0) {
                document.getElementById('dash-recent-list').innerHTML = Components.emptyState(
                    'scan', 'Nenhuma análise', 'Faça sua primeira análise de contrato',
                    '<button class="btn btn-primary" onclick="App.navigateTo(\'analysis/new\')"><i data-lucide="plus"></i> Nova Análise</button>'
                );
            } else {
                let html = '<div class="recent-analyses">';
                recent.forEach(a => {
                    html += `
                        <div class="analysis-mini-row" onclick="App.navigateTo('analysis/${a.id}')">
                            <span style="flex:1">${a.resumo_executivo?.substring(0, 60) || a.mode}...</span>
                            <span>${Components.modeLabel(a.mode)}</span>
                            ${Components.statusBadge(a.status)}
                            <span class="text-muted text-xs">${Components.formatDate(a.created_at)}</span>
                        </div>
                    `;
                });
                html += '</div>';
                document.getElementById('dash-recent-list').innerHTML = html;
            }

            // Chart
            this.renderChart(analyses);
            lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });
        } catch (err) {
            Components.toast('Erro ao carregar dashboard: ' + err.message, 'error');
        }
    },

    renderChart(analyses) {
        const canvas = document.getElementById('dash-chart');
        if (!canvas) return;

        // Agregar por dia nos últimos 30 dias
        const days = [];
        const counts = [];
        for (let i = 29; i >= 0; i--) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            const key = d.toISOString().split('T')[0];
            days.push(d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }));
            counts.push(analyses.filter(a => a.created_at?.startsWith(key)).length);
        }

        new Chart(canvas, {
            type: 'line',
            data: {
                labels: days,
                datasets: [{
                    label: 'Análises',
                    data: counts,
                    borderColor: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
                    backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--color-primary-light').trim(),
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: { color: '#6B6B8D', maxTicksLimit: 7, font: { size: 11 } },
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: { color: '#6B6B8D', stepSize: 1, font: { size: 11 } },
                        beginAtZero: true,
                    },
                },
            },
        });
    },
};
