"""
accounts/views.py — Auth views + OTP password reset system
"""
import secrets
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .forms import RegisterForm, LoginForm, ProfileUpdateForm
from .models import User, OTPVerification
from .forms import BLOCKED_DOMAINS


# ─── Registration ───────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('chat:index')

    form = RegisterForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome, {user.username}!')
        return redirect('chat:index')

    return render(request, 'register.html', {'form': form})


# ─── Login ───────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('chat:index')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect(request.GET.get('next', 'chat:index'))

    return render(request, 'login.html', {'form': form})


# ─── Logout ───────────────────────────────────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('accounts:login')


# ─── Profile ─────────────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('accounts:profile')

    return render(request, 'profile.html', {'form': form})


# ─── Search Users ────────────────────────────────────────────────────────────────

@login_required
@require_GET
def search_users(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        username__icontains=query
    ).exclude(id=request.user.id).values(
        'id', 'username', 'is_online', 'last_seen', 'avatar'
    )[:10]

    results = []
    for u in users:
        if u['avatar']:
            avatar_url = '/media/' + u['avatar']
        else:
            avatar_url = '/static/images/default_avatar.png'

        results.append({
            'id': u['id'],
            'username': u['username'],
            'is_online': u['is_online'],
            'avatar': avatar_url,
        })

    return JsonResponse({'users': results})


# ─── Validate Email (AJAX) ───────────────────────────────────────────────────────

def validate_email_view(request):
    """Real-time email validation endpoint (GET or POST)."""
    email = request.GET.get('email', '') or request.POST.get('email', '')
    email = email.strip().lower()

    if not email or '@' not in email:
        return JsonResponse({'valid': False, 'error': 'Invalid email format.'})

    domain = email.split('@')[-1]
    if domain in BLOCKED_DOMAINS:
        return JsonResponse({'valid': False, 'error': 'Disposable email addresses are not allowed.'})

    exists = User.objects.filter(email__iexact=email).exists()
    if exists:
        return JsonResponse({'valid': False, 'error': 'This email is already registered.'})

    return JsonResponse({'valid': True, 'error': ''})


# ─── OTP Password Reset ─────────────────────────────────────────────────────────

def _send_otp_email(user, otp_code):
    """Send OTP via email (prints to console in DEBUG mode if no SMTP configured)."""
    subject = 'Your Pulse Chat Password Reset Code'
    body = (
        f"Hello {user.username},\n\n"
        f"Your one-time password reset code is:\n\n"
        f"  {otp_code}\n\n"
        f"This code expires in 10 minutes. Do not share it with anyone.\n\n"
        f"If you did not request this, ignore this email.\n\n"
        f"– The Pulse Chat Team"
    )
    if settings.DEBUG:
        print(f"\n{'='*50}\nPULSE CHAT OTP CODE FOR {user.email}: {otp_code}\n{'='*50}\n")
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception:
        pass


def forgot_password_view(request):
    """Step 1: Enter email → send OTP."""
    if request.user.is_authenticated:
        return redirect('chat:index')

    error = ''
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            error = 'Please enter your email address.'
        else:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                # Security: don't reveal if email exists
                request.session['otp_email'] = email
                return redirect('accounts:verify_otp')

            # Rate limit: max 3 OTP requests per email per hour
            one_hour_ago = timezone.now() - timedelta(hours=1)
            recent_count = OTPVerification.objects.filter(
                user=user,
                created_at__gte=one_hour_ago
            ).count()
            if recent_count >= 3:
                error = 'Too many OTP requests. Please wait before trying again.'
            else:
                otp_obj = OTPVerification.create_for_user(user)
                _send_otp_email(user, otp_obj.otp)
                request.session['otp_email'] = email
                return redirect('accounts:verify_otp')

    return render(request, 'forgot_password.html', {'error': error})


def verify_otp_view(request):
    """Step 2: Enter the 6-digit OTP."""
    if request.user.is_authenticated:
        return redirect('chat:index')

    email = request.session.get('otp_email')
    if not email:
        return redirect('accounts:forgot_password')

    # Mask email for display: ab***@gmail.com
    parts = email.split('@')
    if len(parts[0]) > 2:
        masked = parts[0][:2] + '***@' + parts[1]
    else:
        masked = '***@' + parts[1]

    error = ''
    if request.method == 'POST':
        entered = request.POST.get('otp', '').strip()
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return redirect('accounts:forgot_password')

        # Find latest valid OTP
        otp_obj = OTPVerification.objects.filter(
            user=user,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if not otp_obj:
            error = 'OTP expired or not found. Please request a new one.'
        elif otp_obj.attempts >= 5:
            error = 'Too many incorrect attempts. Please request a new OTP.'
        elif otp_obj.otp != entered:
            otp_obj.attempts += 1
            otp_obj.save(update_fields=['attempts'])
            remaining = 5 - otp_obj.attempts
            error = f'Incorrect code. {remaining} attempt(s) remaining.'
        else:
            otp_obj.is_used = True
            otp_obj.save(update_fields=['is_used'])
            request.session['otp_verified'] = True
            return redirect('accounts:reset_password')

    return render(request, 'verify_otp.html', {
        'masked_email': masked,
        'error': error,
    })


def resend_otp_view(request):
    """Resend OTP — POST only, 60-second cooldown enforced client-side."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    email = request.session.get('otp_email')
    if not email:
        return JsonResponse({'error': 'Session expired'}, status=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return JsonResponse({'ok': True})  # Silent — don't reveal if email exists

    # Rate limit
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_count = OTPVerification.objects.filter(
        user=user, created_at__gte=one_hour_ago
    ).count()
    if recent_count >= 3:
        return JsonResponse({'error': 'Rate limit exceeded. Please wait.'}, status=429)

    otp_obj = OTPVerification.create_for_user(user)
    _send_otp_email(user, otp_obj.otp)
    return JsonResponse({'ok': True})


def reset_password_view(request):
    """Step 3: Enter new password."""
    if request.user.is_authenticated:
        return redirect('chat:index')

    if not request.session.get('otp_verified'):
        return redirect('accounts:forgot_password')

    email = request.session.get('otp_email')
    if not email:
        return redirect('accounts:forgot_password')

    error = ''
    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not password1 or len(password1) < 8:
            error = 'Password must be at least 8 characters.'
        elif password1 != password2:
            error = 'Passwords do not match.'
        else:
            try:
                user = User.objects.get(email__iexact=email)
                user.set_password(password1)
                user.save()
                # Clean up session
                del request.session['otp_verified']
                del request.session['otp_email']
                messages.success(request, 'Password reset successfully. Please log in.')
                return redirect('accounts:login')
            except User.DoesNotExist:
                return redirect('accounts:forgot_password')

    return render(request, 'reset_password.html', {'error': error})
