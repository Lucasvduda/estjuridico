/**
 * LegalShield AI — Admin Models (Trocar Modelo IA)
 */
const PageAdminModels = {
    settings:null,
    async render(container) {
        container.innerHTML=`<div class="animate-fade"><h2 class="mb-2">Configuração de Modelos IA</h2><p class="text-muted mb-6">Troque o modelo primário e fallback sem mexer no código</p>
            <div class="model-status-grid" id="provider-status">${Components.skeleton('card',5)}</div>
            <div class="grid grid-2">
                <div class="card"><div class="card-header"><span class="card-title">Modelo Primário</span></div>
                    <select class="form-select" id="sel-primary"><option>Carregando...</option></select>
                    <div class="card-header mt-6"><span class="card-title">Modelo Fallback</span></div>
                    <select class="form-select" id="sel-fallback"><option>Carregando...</option></select>
                    <div class="grid grid-2 mt-6">
                        <div class="form-group"><label class="form-label">Temperature</label><input class="form-input" type="number" id="inp-temp" step="0.1" min="0" max="2"></div>
                        <div class="form-group"><label class="form-label">Max Tokens</label><input class="form-input" type="number" id="inp-tokens" step="256" min="256" max="32768"></div>
                    </div>
                    <button class="btn btn-primary btn-block mt-4" onclick="PageAdminModels.save()"><i data-lucide="save"></i> Salvar Configuração</button>
                </div>
                <div class="card"><div class="card-header"><span class="card-title">API Keys</span></div>
                    <div class="form-group"><label class="form-label">OpenAI</label><input class="form-input" type="password" id="key-openai" placeholder="sk-..."></div>
                    <div class="form-group"><label class="form-label">Google Gemini</label><input class="form-input" type="password" id="key-google" placeholder="AI..."></div>
                    <div class="form-group"><label class="form-label">Anthropic</label><input class="form-input" type="password" id="key-anthropic" placeholder="sk-ant-..."></div>
                    <div class="form-group"><label class="form-label">Mistral</label><input class="form-input" type="password" id="key-mistral" placeholder="..."></div>
                    <div class="form-group"><label class="form-label">Cohere</label><input class="form-input" type="password" id="key-cohere" placeholder="..."></div>
                    <button class="btn btn-secondary btn-block" onclick="PageAdminModels.saveKeys()"><i data-lucide="key"></i> Atualizar Keys</button>
                </div>
            </div></div>`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        this.load();
    },
    async load(){
        try{this.settings=await API.getLLMSettings();const s=this.settings;
        // Provider status
        const providers=[
            {name:'OpenAI',ok:s.openai_configured},{name:'Google',ok:s.google_configured},
            {name:'Anthropic',ok:s.anthropic_configured},{name:'Mistral',ok:s.mistral_configured},{name:'Cohere',ok:s.cohere_configured},
        ];
        document.getElementById('provider-status').innerHTML=providers.map(p=>`<div class="model-provider-card"><span class="provider-status ${p.ok?'configured':'not-configured'}"></span><span>${p.name}</span><span class="text-xs text-muted ml-auto">${p.ok?'✓ Configurado':'✗ Sem key'}</span></div>`).join('');
        // Selects
        const models=s.supported_models||[];
        const opts=models.map(m=>`<option value="${m.id}">${m.name} (${m.provider})</option>`).join('');
        document.getElementById('sel-primary').innerHTML=opts;
        document.getElementById('sel-fallback').innerHTML=opts;
        document.getElementById('sel-primary').value=s.primary_model;
        document.getElementById('sel-fallback').value=s.fallback_model;
        document.getElementById('inp-temp').value=s.temperature;
        document.getElementById('inp-tokens').value=s.max_tokens;
        }catch(err){Components.toast(err.message,'error');}
    },
    async save(){
        try{await API.updateLLMSettings({
            primary_model:document.getElementById('sel-primary').value,
            fallback_model:document.getElementById('sel-fallback').value,
            temperature:parseFloat(document.getElementById('inp-temp').value),
            max_tokens:parseInt(document.getElementById('inp-tokens').value),
        });Components.toast('Modelo atualizado com sucesso!','success');}catch(err){Components.toast(err.message,'error');}
    },
    async saveKeys(){
        const data={};
        const k=document.getElementById('key-openai').value;if(k)data.openai_api_key=k;
        const g=document.getElementById('key-google').value;if(g)data.google_api_key=g;
        const a=document.getElementById('key-anthropic').value;if(a)data.anthropic_api_key=a;
        const m=document.getElementById('key-mistral').value;if(m)data.mistral_api_key=m;
        const c=document.getElementById('key-cohere').value;if(c)data.cohere_api_key=c;
        if(!Object.keys(data).length){Components.toast('Nenhuma key preenchida','warning');return;}
        try{await API.updateLLMSettings(data);Components.toast('API Keys atualizadas!','success');this.load();}catch(err){Components.toast(err.message,'error');}
    },
};
