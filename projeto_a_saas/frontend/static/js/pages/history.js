/**
 * LegalShield AI — History Page
 */
const PageHistory = {
    page:1,
    async render(container) {
        container.innerHTML=`<div class="animate-fade"><div class="flex items-center justify-between mb-6"><h2>Histórico de Análises</h2></div><div id="history-list">${Components.skeleton('card',3)}</div></div>`;
        this.load();
    },
    async load(){
        try{const d=await API.listAnalyses(null,this.page);const a=d.analyses||[];
        if(!a.length){document.getElementById('history-list').innerHTML=Components.emptyState('history','Nenhuma análise','Faça sua primeira análise.');return;}
        const cols=[
            {label:'Modo',render:r=>Components.modeLabel(r.mode)},
            {label:'Status',render:r=>Components.statusBadge(r.status)},
            {label:'Score',render:r=>`<span style="color:${Components.riskColor(r.score_risco)};font-weight:700;">${r.score_risco||0}</span>`},
            {label:'Achados',key:'total_achados'},
            {label:'Modelo',render:r=>`<span class="text-xs">${r.model_used||'—'}</span>`},
            {label:'Data',render:r=>Components.formatDate(r.created_at)},
        ];
        const actions=row=>`<button class="btn btn-sm btn-primary" onclick="App.navigateTo('analysis/${row.id}')"><i data-lucide="eye" style="width:14px;height:14px"></i></button>`;
        document.getElementById('history-list').innerHTML=Components.dataTable(cols,a,actions)+Components.pagination(this.page,Math.ceil((d.total||0)/20),'PageHistory.goPage');
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        }catch(err){Components.toast(err.message,'error');}
    },
    goPage(p){this.page=p;this.load();},
};
