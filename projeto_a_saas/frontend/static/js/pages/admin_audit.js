/**
 * LegalShield AI — Admin Audit Logs
 */
const PageAdminAudit = {
    async render(container) {
        container.innerHTML=`<div class="animate-fade"><div class="flex items-center justify-between mb-6"><h2>Logs de Auditoria</h2>
            <div class="flex gap-3">
                <select class="form-select" id="audit-severity" style="width:auto;" onchange="PageAdminAudit.load()"><option value="">Severidade</option><option value="info">Info</option><option value="warning">Warning</option><option value="critical">Critical</option></select>
                <input class="form-input" type="number" id="audit-limit" value="50" style="width:80px;" onchange="PageAdminAudit.load()">
            </div></div>
            <div id="audit-list">${Components.skeleton('card',3)}</div></div>`;
        this.load();
    },
    async load(){
        try{const filters={limit:parseInt(document.getElementById('audit-limit')?.value||50)};
        const sev=document.getElementById('audit-severity')?.value;if(sev)filters.severity=sev;
        const logs=await API.getAuditLogs(filters);
        if(!logs.length){document.getElementById('audit-list').innerHTML=Components.emptyState('shield-alert','Nenhum log','Nenhuma atividade registrada.');return;}
        const cols=[
            {label:'Ação',render:r=>`<span class="text-semibold">${r.action}</span>`},
            {label:'Recurso',render:r=>`${r.resource_type||'—'}`},
            {label:'Severidade',render:r=>{const m={info:'badge-info',warning:'badge-warning',critical:'badge-danger'};return `<span class="badge ${m[r.severity]||'badge-info'}">${r.severity}</span>`;}},
            {label:'IP',render:r=>r.ip_address||'—'},
            {label:'Data',render:r=>Components.formatDateTime(r.created_at)},
        ];
        document.getElementById('audit-list').innerHTML=Components.dataTable(cols,logs);
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        }catch(err){Components.toast(err.message,'error');}
    },
};

// === Admin Themes (Cores por Empresa) — mapped as PageAdminThemes ===
const PageAdminThemes = {
    tenants:[],presets:{},
    async render(container) {
        container.innerHTML=`<div class="animate-fade"><h2 class="mb-2">🎨 Personalizar Cores por Empresa</h2><p class="text-muted mb-6">Altere as cores de cada empresa de advogado (white-label)</p>
            <div class="form-group"><label class="form-label">Selecione a Empresa</label><select class="form-select" id="theme-tenant" onchange="PageAdminThemes.loadTheme()"><option value="">Carregando...</option></select></div>
            <div id="theme-editor" class="hidden">
                <div class="grid grid-2">
                    <div class="card"><div class="card-header"><span class="card-title">Presets</span></div><div class="preset-grid" id="preset-grid"></div></div>
                    <div class="card"><div class="card-header"><span class="card-title">Cores Personalizadas</span></div>
                        <div class="form-group"><label class="form-label">Cor Primária</label><div class="color-picker-group"><input type="color" id="color-primary" value="#6C5CE7"><span id="color-primary-hex" class="text-sm text-muted">#6C5CE7</span></div></div>
                        <div class="form-group"><label class="form-label">Cor de Destaque</label><div class="color-picker-group"><input type="color" id="color-accent" value="#00D2D3"><span id="color-accent-hex" class="text-sm text-muted">#00D2D3</span></div></div>
                        <div class="form-group"><label class="form-label">Cor da Sidebar</label><div class="color-picker-group"><input type="color" id="color-sidebar" value="#1A1A2E"><span id="color-sidebar-hex" class="text-sm text-muted">#1A1A2E</span></div></div>
                        <div class="form-group"><label class="form-label">Cor de Fundo</label><div class="color-picker-group"><input type="color" id="color-bg" value="#0F0F23"><span id="color-bg-hex" class="text-sm text-muted">#0F0F23</span></div></div>
                        <button class="btn btn-primary btn-block" onclick="PageAdminThemes.saveCustom()"><i data-lucide="save"></i> Salvar Cores</button>
                    </div>
                </div>
                <div class="card mt-6"><div class="card-header"><span class="card-title">Pré-visualização</span></div>
                    <div class="theme-preview" id="theme-preview"><div class="theme-preview-sidebar" id="preview-sidebar"></div><div class="theme-preview-content" id="preview-content"><div class="theme-preview-card" id="preview-card1"></div><div class="theme-preview-card" id="preview-card2" style="width:60%;"></div></div></div>
                </div>
            </div></div>`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        this.loadTenants();
    },
    async loadTenants(){
        try{this.tenants=await API.listTenants();this.presets=await API.getThemePresets();
        const sel=document.getElementById('theme-tenant');
        sel.innerHTML='<option value="">Selecione...</option>'+this.tenants.map(t=>`<option value="${t.id}">${t.name}</option>`).join('');
        // Render presets
        document.getElementById('preset-grid').innerHTML=Object.entries(this.presets).map(([key,p])=>`<div class="preset-card" onclick="PageAdminThemes.applyPreset('${key}')"><div class="preset-colors"><div class="preset-color-dot" style="background:${p.primary_color}"></div><div class="preset-color-dot" style="background:${p.accent_color}"></div><div class="preset-color-dot" style="background:${p.sidebar_color}"></div></div><div class="preset-name">${p.name}</div></div>`).join('');
        }catch(err){Components.toast(err.message,'error');}
    },
    async loadTheme(){
        const tid=document.getElementById('theme-tenant').value;
        if(!tid){document.getElementById('theme-editor').classList.add('hidden');return;}
        document.getElementById('theme-editor').classList.remove('hidden');
        try{const t=await API.getTenantTheme(tid);
        document.getElementById('color-primary').value=t.primary_color;document.getElementById('color-primary-hex').textContent=t.primary_color;
        document.getElementById('color-accent').value=t.accent_color;document.getElementById('color-accent-hex').textContent=t.accent_color;
        document.getElementById('color-sidebar').value=t.sidebar_color;document.getElementById('color-sidebar-hex').textContent=t.sidebar_color;
        document.getElementById('color-bg').value=t.bg_color;document.getElementById('color-bg-hex').textContent=t.bg_color;
        this.updatePreview(t);
        // Bind change events
        ['primary','accent','sidebar','bg'].forEach(k=>{
            document.getElementById(`color-${k}`).oninput=e=>{document.getElementById(`color-${k}-hex`).textContent=e.target.value;this.updatePreview();};
        });
        }catch(err){Components.toast(err.message,'error');}
    },
    updatePreview(t){
        const p=t||{primary_color:document.getElementById('color-primary').value,accent_color:document.getElementById('color-accent').value,sidebar_color:document.getElementById('color-sidebar').value,bg_color:document.getElementById('color-bg').value};
        document.getElementById('preview-sidebar').style.background=p.sidebar_color;
        document.getElementById('preview-content').style.background=p.bg_color;
        document.getElementById('preview-card1').style.background=p.primary_color+'33';
        document.getElementById('preview-card2').style.background=p.accent_color+'33';
    },
    async applyPreset(name){
        const tid=document.getElementById('theme-tenant').value;if(!tid){Components.toast('Selecione empresa','warning');return;}
        try{await API.applyThemePreset(tid,name);Components.toast('Preset aplicado!','success');this.loadTheme();}catch(err){Components.toast(err.message,'error');}
    },
    async saveCustom(){
        const tid=document.getElementById('theme-tenant').value;if(!tid)return;
        try{await API.updateTenantTheme(tid,{
            primary_color:document.getElementById('color-primary').value,
            accent_color:document.getElementById('color-accent').value,
            sidebar_color:document.getElementById('color-sidebar').value,
            bg_color:document.getElementById('color-bg').value,
        });Components.toast('Cores salvas!','success');}catch(err){Components.toast(err.message,'error');}
    },
};
