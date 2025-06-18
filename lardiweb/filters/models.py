from django.db import models

from users.models import UserProfile


class LardiSearchFilter(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    direction_from = models.JSONField(default=dict) # directionFrom
    direction_to = models.JSONField(default=dict) # directionTo
    mass1 = models.FloatField(null=True, blank=True)
    mass2 = models.FloatField(null=True, blank=True)
    volume1 = models.FloatField(null=True, blank=True)
    volume2 = models.FloatField(null=True, blank=True)
    date_from_iso = models.CharField(max_length=32, null=True, blank=True)
    body_type_ids = models.JSONField(default=list, blank=True)
    load_types = models.JSONField(default=list, blank=True)
    payment_from_ids = models.JSONField(default=list, blank=True)
    groupage = models.BooleanField(default=False)
    photos = models.BooleanField(default=False)
    show_ignore = models.BooleanField(default=False)
    only_actual = models.BooleanField(default=False)
    only_new = models.BooleanField(default=False)
    only_shippers = models.BooleanField(default=False)
    only_carrier = models.BooleanField(default=False)
    only_expedition = models.BooleanField(default=False)
    only_with_stavka = models.BooleanField(default=False)
    distance_km_from = models.IntegerField(null=True, blank=True)
    distance_km_to = models.IntegerField(null=True, blank=True)
    only_partners = models.BooleanField(default=False)
    partner_groups = models.JSONField(default=list, blank=True)
    cargos = models.JSONField(default=list, blank=True)
    cargo_packaging_ids = models.JSONField(default=list, blank=True)
    exclude_cargos = models.JSONField(default=list, blank=True)
    cargo_body_type_properties = models.JSONField(default=list, blank=True)
    payment_currency_id = models.IntegerField(default=4)
    payment_value = models.FloatField(null=True, blank=True)
    payment_value_type = models.CharField(max_length=32, default='TOTAL')
    company_ref_id = models.CharField(max_length=64, null=True, blank=True)
    company_name = models.CharField(max_length=256, null=True, blank=True)
    length1 = models.FloatField(null=True, blank=True)
    length2 = models.FloatField(null=True, blank=True)
    width1 = models.FloatField(null=True, blank=True)
    width2 = models.FloatField(null=True, blank=True)
    height1 = models.FloatField(null=True, blank=True)
    height2 = models.FloatField(null=True, blank=True)
    include_documents = models.JSONField(default=list, blank=True)
    exclude_documents = models.JSONField(default=list, blank=True)
    adr = models.CharField(max_length=32, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Фільтр користувача {self.user} ({self.created_at})"