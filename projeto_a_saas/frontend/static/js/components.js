/**
 * LegalShield AI — Reusable Components
 * Toast, Modal, Table, Pagination, Skeleton, etc.
 */

/**
 * Sanitiza string para inserção segura em HTML (previne XSS).
 * DEVE ser usada em todo dado vindo da API antes de usar innerHTML.
 * @param {string} str - Texto para sanitizar
 * @returns {string} Texto com caracteres HTML escapados
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const s = String(str);
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

const Components = {

    // === Toast Notifications ===
    toast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        const icons = {
            success: 'check-circle',
            error: 'x-circle',
            warning: 'alert-triangle',
            info: 'info',
        };
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon"><i data-lucide="${icons[type] || 'info'}"></i></span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.closest('.toast').remove()">
                <i data-lucide="x" style="width:14px;height:14px;"></i>
            </button>
        `;
        container.appendChild(toast);
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });

        setTimeout(() => {
            toast.classList.add('toast-exit');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    // === Modal ===
    showModal(content) {
        const overlay = document.getElementById('modal-overlay');
        const modalContent = document.getElementById('modal-content');
        modalContent.innerHTML = content;
        overlay.style.display = 'flex';
        lucide.createIcons({ attrs: { class: '' }, nameAttr: 'data-lucide' });

        overlay.onclick = (e) => {
            if (e.target === overlay) this.closeModal();
        };
    },

    closeModal() {
        document.getElementById('modal-overlay').style.display = 'none';
    },

    // === Skeleton Loading ===
    skeleton(type = 'card', count = 1) {
        let html = '';
        for (let i = 0; i < count; i++) {
            if (type === 'card') {
                html += '<div class="card skeleton skeleton-card"></div>';
            } else if (type === 'text') {
                html += '<div class="skeleton skeleton-text" style="width:' + (60 + Math.random() * 30) + '%"></div>';
            }
        }
        return html;
    },

    // === Empty State ===
    emptyState(icon, title, message, actionHtml = '') {
        return `
            <div class="empty-state animate-fade">
                <i data-lucide="${icon}"></i>
                <h3>${title}</h3>
                <p>${message}</p>
                ${actionHtml}
            </div>
        `;
    },

    // === Data Table ===
    dataTable(columns, rows, actions) {
        if (!rows || rows.length === 0) {
            return this.emptyState('inbox', 'Nenhum registro', 'Não há dados para exibir.');
        }
        let html = '<div class="table-container"><table class="data-table"><thead><tr>';
        columns.forEach(col => {
            html += `<th>${col.label}</th>`;
        });
        if (actions) html += '<th style="width:120px">Ações</th>';
        html += '</tr></thead><tbody>';

        rows.forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                const val = col.render ? col.render(row) : (row[col.key] || '—');
                html += `<td>${val}</td>`;
            });
            if (actions) {
                html += `<td><div class="flex gap-2">${actions(row)}</div></td>`;
            }
            html += '</tr>';
        });
        html += '</tbody></table></div>';
        return html;
    },

    // === Pagination ===
    pagination(currentPage, totalPages, onPageChange) {
        if (totalPages <= 1) return '';
        let html = '<div class="pagination">';
        html += `<button class="page-btn" onclick="${onPageChange}(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}><i data-lucide="chevron-left" style="width:14px;height:14px;"></i></button>`;

        const start = Math.max(1, currentPage - 2);
        const end = Math.min(totalPages, currentPage + 2);

        for (let i = start; i <= end; i++) {
            html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="${onPageChange}(${i})">${i}</button>`;
        }

        html += `<button class="page-btn" onclick="${onPageChange}(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}><i data-lucide="chevron-right" style="width:14px;height:14px;"></i></button>`;
        html += '</div>';
        return html;
    },

    // === Stat Card ===
    statCard(icon, value, label, trend = null, color = 'primary') {
        const colorMap = {
            primary: 'var(--color-primary)',
            success: 'var(--color-success)',
            warning: 'var(--color-warning)',
            danger: 'var(--color-danger)',
            accent: 'var(--color-accent)',
            info: 'var(--color-info)',
        };
        const c = colorMap[color] || colorMap.primary;
        let trendHtml = '';
        if (trend) {
            const trendClass = trend.direction === 'up' ? 'up' : 'down';
            const trendIcon = trend.direction === 'up' ? 'trending-up' : 'trending-down';
            trendHtml = `<div class="stat-trend ${trendClass}"><i data-lucide="${trendIcon}" style="width:12px;height:12px;"></i> ${trend.value}</div>`;
        }
        return `
            <div class="card stat-card">
                <div class="stat-icon" style="background:${c}20;color:${c};">
                    <i data-lucide="${icon}"></i>
                </div>
                <div class="stat-value">${value}</div>
                <div class="stat-label">${label}</div>
                ${trendHtml}
            </div>
        `;
    },

    // === Status Badge ===
    statusBadge(status) {
        const map = {
            uploaded: { class: 'badge-info', label: 'Enviado' },
            processing: { class: 'badge-warning', label: 'Processando' },
            analyzed: { class: 'badge-success', label: 'Analisado' },
            error: { class: 'badge-danger', label: 'Erro' },
            completed: { class: 'badge-success', label: 'Concluído' },
            failed: { class: 'badge-danger', label: 'Falhou' },
            pending: { class: 'badge-warning', label: 'Pendente' },
            active: { class: 'badge-success', label: 'Ativo' },
            suspended: { class: 'badge-warning', label: 'Suspenso' },
            cancelled: { class: 'badge-danger', label: 'Cancelado' },
            trial: { class: 'badge-info', label: 'Trial' },
            basic: { class: 'badge-primary', label: 'Basic' },
            pro: { class: 'badge-primary', label: 'Pro' },
            enterprise: { class: 'badge-success', label: 'Enterprise' },
        };
        const s = map[status] || { class: 'badge-info', label: status };
        return `<span class="badge ${s.class}">${s.label}</span>`;
    },

    // === Severity Badge ===
    severityBadge(severity) {
        const s = (severity || '').toUpperCase();
        const map = {
            'CRÍTICO': 'severity-critico',
            'CRITICO': 'severity-critico',
            'ALTO': 'severity-alto',
            'MÉDIO': 'severity-medio',
            'MEDIO': 'severity-medio',
            'BAIXO': 'severity-baixo',
        };
        return `<span class="badge ${map[s] || 'badge-info'}">${severity || 'N/A'}</span>`;
    },

    // === Contract Tag Badge ===
    contractTag(tag) {
        const map = {
            existente: { class: 'tag-existente', label: '📄 Existente' },
            enviar: { class: 'tag-enviar', label: '📤 A Enviar' },
            receber: { class: 'tag-receber', label: '📥 A Receber' },
        };
        const t = map[tag] || { class: 'badge-info', label: tag || 'Geral' };
        return `<span class="badge ${t.class}">${t.label}</span>`;
    },

    // === File Size Formatter ===
    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    },

    // === Date Formatter ===
    formatDate(dateStr) {
        if (!dateStr) return '—';
        const d = new Date(dateStr);
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    },

    formatDateTime(dateStr) {
        if (!dateStr) return '—';
        const d = new Date(dateStr);
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    },

    // === Risk Score Color ===
    riskColor(score) {
        if (score >= 80) return 'var(--severity-critico)';
        if (score >= 60) return 'var(--severity-alto)';
        if (score >= 40) return 'var(--color-warning)';
        return 'var(--color-success)';
    },

    // === Mode Labels ===
    modeLabel(mode) {
        const map = {
            defensive: '🛡️ Defensivo',
            offensive: '⚔️ Ofensivo',
            audit: '🔍 Auditoria',
            shield: '🏛️ Shield',
        };
        return map[mode] || mode;
    },
};
