from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

def login_view(request):
    if request.user.is_authenticated:
        return redirect('abpe_ui:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            next_url = request.POST.get('next', '/')
            return redirect(next_url)
        else:
            messages.error(request, _('login_error'))

    return render(request, 'abpe_ui/login.html', {
        'current_lang': request.session.get('language', 'de'),
    })

def logout_view(request):
    logout(request)
    return render(request, 'abpe_ui/logged_out.html', {'current_lang': request.session.get('language', 'de')})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('abpe_ui:dashboard')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        username = request.POST.get('username', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        errors = []

        if not first_name or not last_name:
            errors.append(_('required_fields'))
        if not email:
            errors.append(_('required_fields'))
        elif User.objects.filter(email=email).exists():
            errors.append(_('email_exists'))
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors.append(_('invalid_email'))

        if not username:
            errors.append(_('required_fields'))
        elif User.objects.filter(username=username).exists():
            errors.append(_('username_exists'))

        if not password1:
            errors.append(_('required_fields'))
        elif len(password1) < 6:
            errors.append(_('password_too_short'))
        elif password1 != password2:
            errors.append(_('passwords_not_match'))

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, _('register_success'))
            return redirect('abpe_ui:dashboard')

    return render(request, 'abpe_ui/register.html', {
        'current_lang': request.session.get('language', 'de'),
    })

# Für API-Tests CSRF exempt (optional)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect

# register_view bleibt mit CSRF Schutz (für Web)
# Für curl Tests: temporär ausschalten
