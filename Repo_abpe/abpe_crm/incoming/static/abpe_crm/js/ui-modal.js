// ui-modal.js - Modal Handling
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('show');
}
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('show');
}
function closeModalOnOutside(event, modalId) {
    if (event.target === document.getElementById(modalId)) closeModal(modalId);
}
