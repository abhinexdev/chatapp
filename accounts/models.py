"""
accounts/models.py — Custom User model with profile picture & presence, plus OTP verification
"""
import secrets
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True)
    bio = models.CharField(max_length=160, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'accounts_user'

    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            try:
                return self.avatar.url
            except Exception:
                pass
        return '/static/images/default_avatar.png'

    def update_last_seen(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])

    def set_online(self, status: bool):
        self.is_online = status
        if not status:
            self.last_seen = timezone.now()
        self.save(update_fields=['is_online', 'last_seen'])

    def __str__(self):
        return self.username


class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        """Check if OTP is still usable."""
        return (
            not self.is_used
            and timezone.now() < self.expires_at
            and self.attempts < 5
        )

    @classmethod
    def create_for_user(cls, user):
        """Generate a new 6-digit OTP for the user, expires in 10 minutes."""
        otp_code = str(secrets.randbelow(900000) + 100000)  # 100000-999999
        expires = timezone.now() + timedelta(minutes=10)
        return cls.objects.create(
            user=user,
            otp=otp_code,
            expires_at=expires,
        )

    def __str__(self):
        return f"OTP({self.user.username}, used={self.is_used})"
