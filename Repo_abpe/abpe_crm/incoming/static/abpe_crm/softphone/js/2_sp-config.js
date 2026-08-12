// sp-config.js — Config laden (Django API oder config.json)
// Priorität: 1. Django API /crm/api/user-settings/  2. config.json  3. window.SP_CONFIG
window.SP_CONFIG = window.SP_CONFIG || {
    api_base:     '/crm/api',
    contacts_url: '/crm/api/softphone/contacts/',
    ws:           '',
    extension:    '',
    password:     '',
    display:      '',
};
// TODO: Config von API laden und SP_CONFIG befüllen

// Standalone-Modus: Diese Seite IST das Softphone — kein Modal-Toggle nötig
window.SP_STANDALONE = false;
