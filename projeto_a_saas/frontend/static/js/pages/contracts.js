/**
 * LegalShield AI — Contracts Page
 */
const PageContracts = {
    currentPage: 1,
    async render(container) {
        container.innerHTML = `
            <div class="contracts-toolbar animate-fade">
                <div class="search-box"><i data-lucide="search"></i>
                    <input class="form-input" type="text" id="search-contracts" placeholder="Buscar contratos..."></div>
                <div class="tag-selector">
                    <button class="tag-option active" data-tag="all" onclick="PageContracts.filterTag('all')">Todos</button>
                    <button class="tag-option" data-tag="existente" onclick="PageContracts.filterTag('existente')">📄 Existente</button>
                    <button class="tag-option" data-tag="enviar" onclick="PageContracts.filterTag('enviar')">📤 A Enviar</button>
                    <button class="tag-option" data-tag="receber" onclick="PageContracts.filterTag('receber')">📥 A Receber</button>
                </div>
                <button class="btn btn-primary" onclick="PageContracts.showUpload()"><i data-lucide="upload"></i> Enviar</button>
            </div>
            <div id="contracts-list">${Components.skeleton('card', 3)}</div>`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        this.loadContracts();
    },
    async loadContracts() {
        try {
            const data = await API.listContracts(this.currentPage, 20);
            const c = data.contracts||[];
            if(!c.length){document.getElementById('contracts-list').innerHTML=Components.emptyState('file-text','Nenhum contrato','Envie seu primeiro contrato.','<button class="btn btn-primary" onclick="PageContracts.showUpload()"><i data-lucide="upload"></i> Enviar</button>');lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});return;}
            const cols=[
                {label:'Arquivo',render:r=>`<div class="flex items-center gap-3"><i data-lucide="file-text" style="width:18px;height:18px;color:var(--color-primary)"></i><div><div class="text-semibold">${r.filename}</div><div class="text-xs text-muted">${Components.formatFileSize(r.file_size_bytes)} · ${r.file_type.toUpperCase()}</div></div></div>`},
                {label:'Status',render:r=>Components.statusBadge(r.status)},
                {label:'Análises',key:'analysis_count'},
                {label:'Data',render:r=>Components.formatDate(r.created_at)},
            ];
            const actions=row=>`<button class="btn btn-sm btn-primary" onclick="App.navigateTo('analysis/new?contract=${row.id}')"><i data-lucide="scan" style="width:14px;height:14px"></i></button><button class="btn btn-sm btn-secondary" onclick="PageContracts.confirmDelete('${row.id}')"><i data-lucide="trash-2" style="width:14px;height:14px"></i></button>`;
            document.getElementById('contracts-list').innerHTML=Components.dataTable(cols,c,actions)+Components.pagination(this.currentPage,Math.ceil((data.total||0)/20),'PageContracts.goPage');
            lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        } catch(err){Components.toast(err.message,'error');}
    },
    filterTag(t){document.querySelectorAll('.tag-option').forEach(b=>b.classList.toggle('active',b.dataset.tag===t));this.loadContracts();},
    goPage(p){this.currentPage=p;this.loadContracts();},
    showUpload(){
        Components.showModal(`<div class="modal-header"><h3 class="modal-title">Enviar Contrato</h3><button class="btn-icon" onclick="Components.closeModal()"><i data-lucide="x"></i></button></div>
            <div class="form-group"><label class="form-label">Tipo</label><select class="form-select" id="upload-tag"><option value="existente">📄 Existente</option><option value="enviar">📤 A Enviar</option><option value="receber">📥 A Receber</option></select></div>
            <div class="upload-zone" id="upload-zone" onclick="document.getElementById('file-input').click()"><i data-lucide="cloud-upload"></i><h3>Arraste ou clique</h3><p>PDF, DOCX, TXT — Max 50MB</p><input type="file" id="file-input" accept=".pdf,.docx,.txt" style="display:none"></div>
            <div id="upload-progress" class="mt-4 hidden"><div class="progress-bar"><div class="progress-fill" id="upload-fill" style="width:0%"></div></div></div>`);
        const zone=document.getElementById('upload-zone');
        zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('drag-over');});
        zone.addEventListener('dragleave',()=>zone.classList.remove('drag-over'));
        zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('drag-over');if(e.dataTransfer.files.length)this.doUpload(e.dataTransfer.files[0]);});
        document.getElementById('file-input').addEventListener('change',e=>{if(e.target.files.length)this.doUpload(e.target.files[0]);});
    },
    async doUpload(file){
        document.getElementById('upload-progress').classList.remove('hidden');
        document.getElementById('upload-fill').style.width='60%';
        try{await API.uploadContract(file);document.getElementById('upload-fill').style.width='100%';Components.toast('Contrato enviado!','success');setTimeout(()=>{Components.closeModal();this.loadContracts();},800);}catch(err){Components.toast(err.message,'error');}
    },
    confirmDelete(id){Components.showModal(`<div class="modal-header"><h3 class="modal-title">Excluir?</h3><button class="btn-icon" onclick="Components.closeModal()"><i data-lucide="x"></i></button></div><p class="text-muted">Ação irreversível.</p><div class="modal-actions"><button class="btn btn-secondary" onclick="Components.closeModal()">Cancelar</button><button class="btn btn-danger" onclick="PageContracts.doDelete('${id}')">Excluir</button></div>`);},
    async doDelete(id){try{await API.deleteContract(id);Components.toast('Excluído','success');Components.closeModal();this.loadContracts();}catch(err){Components.toast(err.message,'error');}},
};
