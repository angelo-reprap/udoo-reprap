# apps/abpe_crm/views_auth.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings

def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or settings.LOGIN_REDIRECT_URL
            return redirect(next_url)
        else:
            messages.error(request, 'Benutzername oder Passwort falsch.')

    return render(request, 'abpe_crm/login.html', {
        'current_lang': request.session.get('language', 'de'),
    })

def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)
