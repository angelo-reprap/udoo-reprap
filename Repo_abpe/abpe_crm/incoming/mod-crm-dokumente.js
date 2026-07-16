/* ============================================================
   ABpE CRM — mod-crm-dokumente.js
   Upload Modal, Datei-Icons
   ============================================================ */

const CRM_Dokumente = {

    uploadModal: null,

    showUpload() {
        const modal = document.getElementById('crm-upload-modal');
        if (modal) modal.classList.add('show');
    },

    hideUpload() {
        const modal = document.getElementById('crm-upload-modal');
        if (modal) modal.classList.remove('show');
    },

    getIcon(docType, mimeType) {
        if (docType === 'cv')       return 'bi-file-person';
        if (docType === 'contract') return 'bi-file-earmark-text';
        if (docType === 'invoice')  return 'bi-file-earmark-invoice';
        if (docType === 'email')    return 'bi-envelope';
        if (mimeType?.includes('pdf'))  return 'bi-file-earmark-pdf';
        if (mimeType?.includes('word')) return 'bi-file-earmark-word';
        return 'bi-file-earmark';
    },

    getIconColor(docType) {
        const colors = {
            cv:       '#163258',
            contract: '#1e40af',
            invoice:  '#065f46',
            email:    '#92400e',
            other:    '#6c757d',
        };
        return colors[docType] || '#6c757d';
    },
};

window.CRM_Dokumente = CRM_Dokumente;
window.crmUploadDokument = () => CRM_Dokumente.showUpload();
