from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
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

            # 1. Admin-Benachrichtigung
            try:
                send_mail(
                    subject=f'[ABpE] Neuer Benutzer: {username}',
                    message=f"""Neuer Benutzer registriert:

Name:        {first_name} {last_name}
Benutzername: {username}
E-Mail:      {email}
Telefon:     {request.POST.get('phone', '–')}
Mobil:       {request.POST.get('mobile', '–')}
Adresse:     {request.POST.get('address', '–')}

Portal: https://abpe.win.abcona.info/admin_portal/users/
""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.DEFAULT_FROM_EMAIL],
                    fail_silently=True,
                )
            except Exception:
                pass

            # 2. Willkommens-Mail an neuen User (HTML + Text)
            try:
                text_body = f"""Hallo {first_name} {last_name},

willkommen im ABpE Portal! Ihr Konto wurde erfolgreich erstellt.

Ihre Zugangsdaten:
  Benutzername: {username}
  E-Mail:       {email}

Erste Schritte:
  1. Anmelden:  https://abpe.win.abcona.info/login/
  2. Profil vervollständigen (oben rechts → Profil)
  3. Einstellungen anpassen (Sprache, Theme)

Bei Fragen: cv_scan@abcona.de

Mit freundlichen Grüßen
Ihr ABpE Portal Team
ABpE - Automatisiertes Berater Profil Erfassungssystem"""

                html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:30px 0;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

        <!-- HEADER -->
        <tr>
          <td style="background:#163258;padding:28px 40px;text-align:center;">
            <div style="color:white;font-size:22px;font-weight:bold;letter-spacing:1px;">ABpE Portal</div>
            <div style="color:#8ba8c8;font-size:12px;margin-top:4px;">Automatisiertes Berater Profil Erfassungssystem</div>
          </td>
        </tr>

        <!-- WILLKOMMEN BANNER -->
        <tr>
          <td style="background:#1e4a7a;padding:20px 40px;text-align:center;">
            <div style="color:white;font-size:18px;font-weight:600;">Willkommen, {first_name}! 👋</div>
            <div style="color:#b8d0e8;font-size:13px;margin-top:6px;">Ihr Konto wurde erfolgreich erstellt</div>
          </td>
        </tr>

        <!-- BODY -->
        <tr>
          <td style="padding:32px 40px;">
            <p style="color:#333;font-size:15px;line-height:1.6;margin:0 0 20px;">
              Hallo <strong>{first_name} {last_name}</strong>,<br>
              vielen Dank für Ihre Registrierung im ABpE Portal. Ihr Konto ist aktiviert und einsatzbereit.
            </p>

            <!-- ZUGANGSDATEN BOX -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;border-radius:6px;margin-bottom:24px;">
              <tr><td style="padding:20px 24px;">
                <div style="font-size:12px;font-weight:bold;color:#163258;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;">Ihre Zugangsdaten</div>
                <table>
                  <tr>
                    <td style="color:#666;font-size:13px;padding:4px 16px 4px 0;width:120px;">Benutzername</td>
                    <td style="color:#163258;font-size:13px;font-weight:bold;">{username}</td>
                  </tr>
                  <tr>
                    <td style="color:#666;font-size:13px;padding:4px 16px 4px 0;">E-Mail</td>
                    <td style="color:#163258;font-size:13px;font-weight:bold;">{email}</td>
                  </tr>
                </table>
              </td></tr>
            </table>

            <!-- ERSTE SCHRITTE -->
            <div style="font-size:12px;font-weight:bold;color:#163258;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;">Erste Schritte</div>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:8px 0;vertical-align:top;">
                  <span style="display:inline-block;background:#163258;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;font-weight:bold;margin-right:10px;">1</span>
                  <span style="color:#333;font-size:14px;">Im Portal anmelden</span>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 0;vertical-align:top;">
                  <span style="display:inline-block;background:#163258;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;font-weight:bold;margin-right:10px;">2</span>
                  <span style="color:#333;font-size:14px;">Profil vervollständigen <span style="color:#888;font-size:12px;">(oben rechts → Profil)</span></span>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 0;vertical-align:top;">
                  <span style="display:inline-block;background:#163258;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;font-weight:bold;margin-right:10px;">3</span>
                  <span style="color:#333;font-size:14px;">Einstellungen anpassen <span style="color:#888;font-size:12px;">(Sprache, Theme)</span></span>
                </td>
              </tr>
            </table>

            <!-- LOGIN BUTTON -->
            <div style="text-align:center;margin:28px 0 8px;">
              <a href="https://abpe.win.abcona.info/login/"
                 style="background:#163258;color:white;text-decoration:none;padding:12px 32px;border-radius:6px;font-size:15px;font-weight:600;display:inline-block;">
                Jetzt anmelden →
              </a>
            </div>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f0f4f8;padding:20px 40px;text-align:center;border-top:1px solid #e0e8f0;">
            <p style="color:#888;font-size:12px;margin:0;">
              Bei Fragen: <a href="mailto:cv_scan@abcona.de" style="color:#163258;">cv_scan@abcona.de</a>
            </p>
            <p style="color:#aaa;font-size:11px;margin:8px 0 0;">
              © 2026 abcona GmbH · ABpE Portal · Diese E-Mail wurde automatisch generiert
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

                msg = EmailMultiAlternatives(
                    subject='Willkommen im ABpE Portal!',
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                msg.attach_alternative(html_body, "text/html")
                msg.send(fail_silently=True)
            except Exception:
                pass

            return redirect('abpe_ui:dashboard')

    return render(request, 'abpe_ui/register.html', {
        'current_lang': request.session.get('language', 'de'),
    })

# Für API-Tests CSRF exempt (optional)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect

# register_view bleibt mit CSRF Schutz (für Web)
# Für curl Tests: temporär ausschalten
