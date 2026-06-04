/**
 * LegalShield AI — Analysis Page
 * Nova análise (seleção de modo) + visualização de resultado.
 */
const PageAnalysis = {
    async render(container, params={}) {
        if(params.id){return this.renderResult(container,params.id);}
        const qs=new URLSearchParams(window.location.hash.split('?')[1]||'');
        const contractId=qs.get('contract');
        container.innerHTML=`<div class="animate-fade">
            <h2 class="mb-6">Nova Análise Jurídica</h2>
            ${contractId?`<input type="hidden" id="analysis-contract" value="${contractId}"><p class="text-muted mb-6">Contrato selecionado: <strong>${contractId.substring(0,8)}...</strong></p>`:`
            <div class="form-group"><label class="form-label">Selecione o Contrato</label><select class="form-select" id="analysis-contract"><option value="">Carregando...</option></select></div>`}
            <label class="form-label">Modo de Análise</label>
            <div class="grid grid-4 mb-6" id="mode-selector">
                <div class="mode-card" data-mode="defensive" onclick="PageAnalysis.selectMode('defensive')">
                    <div class="mode-icon" style="background:var(--color-info-light);color:var(--color-info);">🛡️</div>
                    <div class="mode-name">Defensivo</div>
                    <div class="mode-desc">Identifica riscos e cláusulas desfavoráveis para o seu cliente</div></div>
                <div class="mode-card" data-mode="offensive" onclick="PageAnalysis.selectMode('offensive')">
                    <div class="mode-icon" style="background:var(--color-danger-light);color:var(--color-danger);">⚔️</div>
                    <div class="mode-name">Ofensivo</div>
                    <div class="mode-desc">Encontra brechas e oportunidades de argumentação</div></div>
                <div class="mode-card" data-mode="audit" onclick="PageAnalysis.selectMode('audit')">
                    <div class="mode-icon" style="background:var(--color-warning-light);color:var(--color-warning);">🔍</div>
                    <div class="mode-name">Auditoria</div>
                    <div class="mode-desc">Análise completa de conformidade e compliance</div></div>
                <div class="mode-card" data-mode="shield" onclick="PageAnalysis.selectMode('shield')">
                    <div class="mode-icon" style="background:var(--color-success-light);color:var(--color-success);">🏛️</div>
                    <div class="mode-name">Shield</div>
                    <div class="mode-desc">Proteção total com todas as perspectivas combinadas</div></div>
            </div>
            <button class="btn btn-primary btn-lg btn-block" id="btn-analyze" disabled onclick="PageAnalysis.startAnalysis()">
                <i data-lucide="scan"></i> <span class="btn-text">Iniciar Análise</span></button>
            <div id="analysis-progress" class="mt-6 hidden"><div class="card" style="text-align:center;padding:var(--space-10);">
                <div style="animation:spin 1.5s linear infinite;display:inline-block;"><i data-lucide="loader-2" style="width:48px;height:48px;color:var(--color-primary);"></i></div>
                <h3 class="mt-4">Analisando contrato...</h3><p class="text-muted">A IA está processando o documento. Aguarde.</p>
                <div class="progress-bar mt-4" style="max-width:300px;margin:0 auto;"><div class="progress-fill" id="analyze-fill" style="width:10%;"></div></div>
            </div></div></div>`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        if(!contractId)this.loadContracts();
    },
    selectedMode:null,
    selectMode(mode){
        this.selectedMode=mode;
        document.querySelectorAll('.mode-card').forEach(c=>c.classList.toggle('selected',c.dataset.mode===mode));
        document.getElementById('btn-analyze').disabled=false;
    },
    async loadContracts(){
        try{const d=await API.listContracts(1,100);const sel=document.getElementById('analysis-contract');if(!sel)return;
        sel.innerHTML=(d.contracts||[]).map(c=>`<option value="${c.id}">${c.filename} (${Components.formatDate(c.created_at)})</option>`).join('');
        if(!d.contracts?.length)sel.innerHTML='<option value="">Nenhum contrato disponível</option>';
        }catch(err){Components.toast(err.message,'error');}
    },
    async startAnalysis(){
        const contractId=document.getElementById('analysis-contract')?.value;
        if(!contractId||!this.selectedMode){Components.toast('Selecione contrato e modo','warning');return;}
        document.getElementById('btn-analyze').disabled=true;
        document.getElementById('btn-analyze').classList.add('btn-loading');
        document.getElementById('analysis-progress').classList.remove('hidden');
        let fill=document.getElementById('analyze-fill');
        let pct=10;const iv=setInterval(()=>{pct=Math.min(pct+Math.random()*15,90);fill.style.width=pct+'%';},800);
        try{const result=await API.createAnalysis(contractId,this.selectedMode);
        clearInterval(iv);fill.style.width='100%';
        Components.toast('Análise concluída!','success');
        setTimeout(()=>App.navigateTo(`analysis/${result.id}`),800);
        }catch(err){clearInterval(iv);Components.toast(err.message,'error');
        document.getElementById('btn-analyze').disabled=false;
        document.getElementById('btn-analyze').classList.remove('btn-loading');
        document.getElementById('analysis-progress').classList.add('hidden');}
    },
    async renderResult(container,id){
        container.innerHTML=Components.skeleton('card',2);
        try{const a=await API.getAnalysis(id);
        container.innerHTML=`<div class="animate-fade">
            <div class="flex items-center justify-between mb-6">
                <h2>${Components.modeLabel(a.mode)} — Resultado</h2>
                <button class="btn btn-secondary" onclick="PageAnalysis.exportPDF('${a.id}')"><i data-lucide="download"></i> Exportar PDF</button>
            </div>
            <div class="analysis-result-header">
                <div class="analysis-summary">
                    <h3 class="mb-4">Resumo Executivo</h3>
                    <div class="executive-summary">${a.resumo_executivo||'Sem resumo disponível.'}</div>
                    <div class="analysis-meta">
                        <div class="meta-item"><span class="meta-label">Modelo</span><span class="meta-value">${a.model_used||'N/A'}</span></div>
                        <div class="meta-item"><span class="meta-label">Tokens</span><span class="meta-value">${a.tokens_used?.toLocaleString()||0}</span></div>
                        <div class="meta-item"><span class="meta-label">Custo</span><span class="meta-value">$${(a.cost_usd||0).toFixed(4)}</span></div>
                        <div class="meta-item"><span class="meta-label">Data</span><span class="meta-value">${Components.formatDateTime(a.created_at)}</span></div>
                    </div>
                </div>
                <div style="text-align:center;min-width:180px;">
                    <div style="width:120px;height:120px;border-radius:50%;border:6px solid ${Components.riskColor(a.score_risco)};display:flex;align-items:center;justify-content:center;margin:0 auto;">
                        <span style="font-size:2rem;font-weight:800;color:${Components.riskColor(a.score_risco)}">${a.score_risco||0}</span>
                    </div>
                    <div class="text-sm text-muted mt-2">Score de Risco</div>
                </div>
            </div>
            <h3 class="mb-4">Achados (${a.total_achados||0})</h3>
            <div class="flex flex-col gap-3" id="findings-list">
                ${(a.achados||[]).map((f,i)=>`
                    <div class="finding-card" id="finding-${i}">
                        <div class="finding-header" onclick="document.getElementById('finding-${i}').classList.toggle('expanded')">
                            <span>${Components.severityBadge(f.severidade)}</span>
                            <span class="text-semibold" style="flex:1">${f.titulo}</span>
                            <i data-lucide="chevron-down" style="width:16px;height:16px;"></i>
                        </div>
                        <div class="finding-body">
                            ${f.clausula?`<div class="finding-detail"><div class="finding-detail-label">Cláusula</div><div class="finding-detail-value">${f.clausula}</div></div>`:''}
                            <div class="finding-detail"><div class="finding-detail-label">Descrição</div><div class="finding-detail-value">${f.descricao}</div></div>
                            ${f.fundamentacao_legal?`<div class="finding-detail"><div class="finding-detail-label">Fundamentação Legal</div><div class="finding-detail-value">${f.fundamentacao_legal}</div></div>`:''}
                            ${f.recomendacao?`<div class="finding-detail"><div class="finding-detail-label">Recomendação</div><div class="finding-detail-value">${f.recomendacao}</div></div>`:''}
                        </div>
                    </div>`).join('')}
            </div></div>`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        }catch(err){container.innerHTML=Components.emptyState('alert-circle','Erro','Não foi possível carregar a análise.');Components.toast(err.message,'error');}
    },
    async exportPDF(id){
        try{const blob=await API.exportPDF(id);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`relatorio_${id.substring(0,8)}.pdf`;a.click();URL.revokeObjectURL(url);Components.toast('PDF exportado!','success');}
        catch(err){Components.toast(err.message,'error');}
    },
};
