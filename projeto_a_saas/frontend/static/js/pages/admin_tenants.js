/**
 * LegalShield AI — Admin Tenants (Gerenciar Empresas/Logins)
 */
const PageAdminTenants = {
    async render(container) {
        container.innerHTML=`<div class="animate-fade"><div class="flex items-center justify-between mb-6"><h2>Gerenciar Empresas</h2></div><div id="tenants-list">${Components.skeleton('card',3)}</div></div>`;
        this.load();
    },
    async load(){
        try{const tenants=await API.listTenants();
        if(!tenants.length){document.getElementById('tenants-list').innerHTML=Components.emptyState('building-2','Nenhuma empresa','Nenhum tenant cadastrado.');return;}
        const cols=[
            {label:'Empresa',render:r=>`<div class="flex items-center gap-2"><span class="tenant-status-dot ${r.is_blocked?'blocked':r.subscription_status==='active'?'active':'suspended'}"></span><div><div class="text-semibold">${r.name}</div><div class="text-xs text-muted">${r.slug} · ${r.email}</div></div></div>`},
            {label:'Plano',render:r=>Components.statusBadge(r.subscription_plan)},
            {label:'Status',render:r=>r.is_blocked?'<span class="badge badge-danger">🚫 Bloqueado</span>':Components.statusBadge(r.subscription_status)},
            {label:'Limite',render:r=>`${r.max_analyses_per_month}/mês`},
            {label:'Usuários',render:r=>`Max ${r.max_users}`},
            {label:'Criado',render:r=>Components.formatDate(r.created_at)},
        ];
        const actions=row=>{
            if(row.is_blocked){return `<button class="btn btn-sm btn-success" onclick="PageAdminTenants.unblock('${row.id}')"><i data-lucide="check" style="width:14px;height:14px"></i></button>`;}
            return `<button class="btn btn-sm btn-secondary" onclick="PageAdminTenants.edit('${row.id}','${row.name}',${row.max_analyses_per_month},${row.max_users},'${row.subscription_plan}')"><i data-lucide="settings" style="width:14px;height:14px"></i></button><button class="btn btn-sm btn-danger" onclick="PageAdminTenants.blockModal('${row.id}','${row.name}')"><i data-lucide="ban" style="width:14px;height:14px"></i></button>`;
        };
        document.getElementById('tenants-list').innerHTML=Components.dataTable(cols,tenants,actions);
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        }catch(err){Components.toast(err.message,'error');}
    },
    blockModal(id,name){
        Components.showModal(`<div class="modal-header"><h3 class="modal-title">Bloquear ${name}</h3><button class="btn-icon" onclick="Components.closeModal()"><i data-lucide="x"></i></button></div>
            <div class="form-group"><label class="form-label">Motivo do bloqueio</label><textarea class="form-textarea" id="block-reason" placeholder="Ex: Inadimplência, violação de termos..." required></textarea></div>
            <div class="modal-actions"><button class="btn btn-secondary" onclick="Components.closeModal()">Cancelar</button><button class="btn btn-danger" onclick="PageAdminTenants.doBlock('${id}')">🚫 Bloquear</button></div>`);
    },
    async doBlock(id){
        const reason=document.getElementById('block-reason')?.value;
        if(!reason||reason.length<5){Components.toast('Informe o motivo','warning');return;}
        try{await API.blockTenant(id,reason);Components.toast('Empresa bloqueada!','success');Components.closeModal();this.load();}catch(err){Components.toast(err.message,'error');}
    },
    async unblock(id){
        try{await API.unblockTenant(id);Components.toast('Empresa desbloqueada!','success');this.load();}catch(err){Components.toast(err.message,'error');}
    },
    edit(id,name,maxAnalyses,maxUsers,plan){
        Components.showModal(`<div class="modal-header"><h3 class="modal-title">Editar ${name}</h3><button class="btn-icon" onclick="Components.closeModal()"><i data-lucide="x"></i></button></div>
            <div class="form-group"><label class="form-label">Plano</label><select class="form-select" id="edit-plan"><option ${plan==='trial'?'selected':''}>trial</option><option ${plan==='basic'?'selected':''}>basic</option><option ${plan==='pro'?'selected':''}>pro</option><option ${plan==='enterprise'?'selected':''}>enterprise</option></select></div>
            <div class="form-group"><label class="form-label">Análises/mês</label><input class="form-input" type="number" id="edit-max-analyses" value="${maxAnalyses}"></div>
            <div class="form-group"><label class="form-label">Max usuários</label><input class="form-input" type="number" id="edit-max-users" value="${maxUsers}"></div>
            <div class="modal-actions"><button class="btn btn-secondary" onclick="Components.closeModal()">Cancelar</button><button class="btn btn-primary" onclick="PageAdminTenants.doEdit('${id}')">Salvar</button></div>`);
    },
    async doEdit(id){
        try{await API.updateTenant(id,{
            subscription_plan:document.getElementById('edit-plan').value,
            max_analyses_per_month:parseInt(document.getElementById('edit-max-analyses').value),
            max_users:parseInt(document.getElementById('edit-max-users').value),
        });Components.toast('Atualizado!','success');Components.closeModal();this.load();}catch(err){Components.toast(err.message,'error');}
    },
};
