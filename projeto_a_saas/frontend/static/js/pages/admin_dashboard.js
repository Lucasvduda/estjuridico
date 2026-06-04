/**
 * LegalShield AI — Admin Dashboard (Analytics)
 */
const PageAdminDashboard = {
    period:'month',
    async render(container) {
        container.innerHTML=`<div class="animate-fade">
            <div class="flex items-center justify-between mb-6"><h2>Dashboard Analytics</h2>
                <div class="tabs" id="period-tabs">
                    <button class="tab-btn" onclick="PageAdminDashboard.setPeriod('day')">Dia</button>
                    <button class="tab-btn" onclick="PageAdminDashboard.setPeriod('week')">Semana</button>
                    <button class="tab-btn active" onclick="PageAdminDashboard.setPeriod('month')">Mês</button>
                </div></div>
            <div class="grid grid-4 stagger" id="admin-stats">${Components.skeleton('card',4)}</div>
            <div class="grid grid-2 mt-6">
                <div class="card"><div class="card-header"><span class="card-title">Análises por Empresa</span></div><div class="chart-container"><canvas id="chart-by-tenant"></canvas></div></div>
                <div class="card"><div class="card-header"><span class="card-title">Consumo de Tokens</span></div><div class="chart-container"><canvas id="chart-tokens"></canvas></div></div>
            </div>
            <div class="card mt-6"><div class="card-header"><span class="card-title">Top Empresas por Uso</span></div><div id="top-tenants">${Components.skeleton('text',5)}</div></div>
        </div>`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        this.load();
    },
    setPeriod(p){
        this.period=p;
        document.querySelectorAll('#period-tabs .tab-btn').forEach((b,i)=>{
            b.classList.toggle('active',['day','week','month'][i]===p);
        });
        this.load();
    },
    async load(){
        try{const usage=await API.getUsage(this.period);
        const totalTokens=usage.reduce((s,u)=>s+u.total_tokens,0);
        const totalCost=usage.reduce((s,u)=>s+u.total_cost_usd,0);
        const totalAnalyses=usage.reduce((s,u)=>s+u.analysis_count,0);
        document.getElementById('admin-stats').innerHTML=`
            ${Components.statCard('building-2',usage.length,'Empresas Ativas',null,'primary')}
            ${Components.statCard('scan',totalAnalyses,'Total Análises',null,'accent')}
            ${Components.statCard('coins',totalTokens.toLocaleString(),'Tokens Consumidos',null,'warning')}
            ${Components.statCard('dollar-sign','$'+totalCost.toFixed(2),'Custo Total',null,'danger')}`;
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        // Charts
        this.renderBarChart(usage);this.renderDoughnutChart(usage);
        // Top tenants table
        const sorted=[...usage].sort((a,b)=>b.analysis_count-a.analysis_count);
        const cols=[
            {label:'Empresa',key:'tenant_name'},
            {label:'Análises',key:'analysis_count'},
            {label:'Tokens',render:r=>r.total_tokens.toLocaleString()},
            {label:'Custo',render:r=>'$'+r.total_cost_usd.toFixed(4)},
        ];
        document.getElementById('top-tenants').innerHTML=Components.dataTable(cols,sorted.slice(0,10));
        lucide.createIcons({attrs:{class:''},nameAttr:'data-lucide'});
        }catch(err){Components.toast(err.message,'error');}
    },
    renderBarChart(usage){
        const canvas=document.getElementById('chart-by-tenant');if(!canvas)return;
        new Chart(canvas,{type:'bar',data:{labels:usage.map(u=>u.tenant_name.substring(0,15)),datasets:[{label:'Análises',data:usage.map(u=>u.analysis_count),backgroundColor:getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()+'99',borderRadius:6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:'#6B6B8D',font:{size:10}}},y:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6B6B8D'},beginAtZero:true}}}});
    },
    renderDoughnutChart(usage){
        const canvas=document.getElementById('chart-tokens');if(!canvas)return;
        const colors=['#6C5CE7','#00D2D3','#FF6B6B','#FDCB6E','#00B894','#74B9FF','#A855F7'];
        new Chart(canvas,{type:'doughnut',data:{labels:usage.map(u=>u.tenant_name),datasets:[{data:usage.map(u=>u.total_tokens),backgroundColor:usage.map((_,i)=>colors[i%colors.length]),borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{color:'#A0A0C0',font:{size:11},padding:12}}},cutout:'65%'}});
    },
};
