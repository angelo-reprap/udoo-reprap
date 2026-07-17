// core-register.js - Registrierungs-Funktionen

// Passwort sichtbar/unsichtbar toggle
function togglePassword(fieldId) {
    const field = document.getElementById(fieldId);
    const button = field.nextElementSibling;
    const icon = button.querySelector('i');
    
    if (field.type === 'password') {
        field.type = 'text';
        icon.classList.remove('bi-eye');
        icon.classList.add('bi-eye-slash');
    } else {
        field.type = 'password';
        icon.classList.remove('bi-eye-slash');
        icon.classList.add('bi-eye');
    }
}

// Client-side Passwort-Validierung
function validatePassword() {
    const pwd1 = document.getElementById('password1');
    const pwd2 = document.getElementById('password2');
    const errorDiv = document.getElementById('password-error');
    
    if (pwd1 && pwd2 && pwd1.value !== pwd2.value) {
        if (errorDiv) errorDiv.style.display = 'block';
        return false;
    }
    if (errorDiv) errorDiv.style.display = 'none';
    return true;
}

// E-Mail Validierung
function validateEmail(email) {
    const re = /^[^\s@]+@([^\s@]+\.)+[^\s@]+$/;
    return re.test(email);
}

// Formular-Validierung vor dem Absenden
function validateForm() {
    const email = document.getElementById('email');
    const pwd1 = document.getElementById('password1');
    const pwd2 = document.getElementById('password2');
    
    if (!validateEmail(email.value)) {
        alert('Bitte geben Sie eine gültige E-Mail Adresse ein.');
        email.focus();
        return false;
    }
    
    if (pwd1.value !== pwd2.value) {
        alert('Die Passwörter stimmen nicht überein.');
        pwd1.focus();
        return false;
    }
    
    if (pwd1.value.length < 6) {
        alert('Das Passwort muss mindestens 6 Zeichen lang sein.');
        pwd1.focus();
        return false;
    }
    
    return true;
}

// Echtzeit-Passwort-Übereinstimmung prüfen
document.addEventListener('DOMContentLoaded', function() {
    const pwd1 = document.getElementById('password1');
    const pwd2 = document.getElementById('password2');
    
    if (pwd1 && pwd2) {
        pwd2.addEventListener('keyup', validatePassword);
        pwd1.addEventListener('keyup', validatePassword);
    }
});

// Globale Funktionen verfügbar machen
window.togglePassword = togglePassword;
window.validateForm = validateForm;
