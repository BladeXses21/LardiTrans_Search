from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    telegram_id = models.BigIntegerField(unique=True)
    notification_status = models.BooleanField(default=False)
    notification_time = models.DateTimeField(auto_now_add=True, null=True)
    cargo_skip = models.JSONField(blank=True, null=True)
    extra_data = models.JSONField(blank=True, null=True) # Для додаткових налаштувань

    def __str__(self):
        return f"{self.user.username} (Telegram ID: {self.telegram_id})"
