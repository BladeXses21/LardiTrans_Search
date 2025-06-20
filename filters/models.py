from django.db import models

from users.models import UserProfile


class LardiSearchFilter(models.Model):
    """
    Модель Django для зберігання фільтрів пошуку вантажів Lardi-Trans для кожного користувача.
    """
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, unique=True,
                             help_text="Користувач, якому належить цей фільтр.")

    # Поля напрямків
    direction_from = models.JSONField(default=dict, blank=True,
                                     help_text="Параметри напрямку завантаження (directionFrom).")
    direction_to = models.JSONField(default=dict, blank=True,
                                   help_text="Параметри напрямку вивантаження (directionTo).")

    # Параметри вантажу
    mass1 = models.FloatField(null=True, blank=True, help_text="Мінімальна маса вантажу (тонни).")
    mass2 = models.FloatField(null=True, blank=True, help_text="Максимальна маса вантажу (тонни).")
    volume1 = models.FloatField(null=True, blank=True, help_text="Мінімальний об'єм вантажу (м³).")
    volume2 = models.FloatField(null=True, blank=True, help_text="Максимальний об'єм вантажу (м³).")
    length1 = models.FloatField(null=True, blank=True, help_text="Мінімальна довжина вантажу (метри).")
    length2 = models.FloatField(null=True, blank=True, help_text="Максимальна довжина вантажу (метри).")
    width1 = models.FloatField(null=True, blank=True, help_text="Мінімальна ширина вантажу (метри).")
    width2 = models.FloatField(null=True, blank=True, help_text="Максимальна ширина вантажу (метри).")
    height1 = models.FloatField(null=True, blank=True, help_text="Мінімальна висота вантажу (метри).")
    height2 = models.FloatField(null=True, blank=True, help_text="Максимальна висота вантажу (метри).")

    # Дати
    date_from_iso = models.CharField(max_length=32, null=True, blank=True,
                                     help_text="Дата завантаження від (ISO формат).")
    date_to_iso = models.CharField(max_length=32, null=True, blank=True,
                                   help_text="Дата завантаження до (ISO формат).") # ДОДАНО ЦЕ ПОЛЕ

    # Типи кузова та завантаження
    body_type_ids = models.JSONField(default=list, blank=True,
                                     help_text="Список ID типів кузова.")
    load_types = models.JSONField(default=list, blank=True,
                                  help_text="Список типів завантаження (top, side, back тощо).")

    # Форми оплати
    payment_from_ids = models.JSONField(default=list, blank=True,
                                        help_text="Список ID форм оплати.")
    payment_currency_id = models.IntegerField(default=4, help_text="ID валюти оплати (4 для UAH).")
    payment_value = models.FloatField(null=True, blank=True, help_text="Значення оплати.")
    payment_value_type = models.CharField(max_length=32, default='TOTAL',
                                          help_text="Тип значення оплати (TOTAL, PER_KG, PER_M3 тощо).")

    # Додаткові опції (булеві)
    groupage = models.BooleanField(default=False, help_text="Чи шукати збірні вантажі.")
    photos = models.BooleanField(default=False, help_text="Чи шукати вантажі з фото.")
    show_ignore = models.BooleanField(default=False, help_text="Чи показувати ігноровані вантажі.")
    only_actual = models.BooleanField(default=False, help_text="Чи показувати тільки актуальні вантажі.")
    only_new = models.BooleanField(default=False, help_text="Чи показувати тільки нові вантажі.")
    only_relevant = models.BooleanField(default=False, help_text="Чи показувати тільки релевантні вантажі.") # ДОДАНО ЦЕ ПОЛЕ
    only_shippers = models.BooleanField(default=False, help_text="Чи показувати тільки відправників.")
    only_carrier = models.BooleanField(default=False, help_text="Чи показувати тільки перевізників.")
    only_expedition = models.BooleanField(default=False, help_text="Чи показувати тільки експедиторів.")
    only_with_stavka = models.BooleanField(default=False, help_text="Чи показувати тільки вантажі зі ставкою.")
    only_partners = models.BooleanField(default=False, help_text="Чи показувати тільки вантажі партнерів.")

    # Відстань
    distance_km_from = models.IntegerField(null=True, blank=True, help_text="Мінімальна відстань (км).")
    distance_km_to = models.IntegerField(null=True, blank=True, help_text="Максимальна відстань (км).")

    # Інші фільтри
    partner_groups = models.JSONField(default=list, blank=True,
                                      help_text="ID груп партнерів.")
    cargos = models.JSONField(default=list, blank=True,
                              help_text="Список конкретних вантажів.")
    cargo_packaging_ids = models.JSONField(default=list, blank=True,
                                           help_text="Список ID типів упаковки вантажу.")
    exclude_cargos = models.JSONField(default=list, blank=True,
                                      help_text="Список вантажів, які потрібно виключити.")
    cargo_body_type_properties = models.JSONField(default=list, blank=True,
                                                   help_text="Властивості типу кузова вантажу.")
    company_ref_id = models.CharField(max_length=64, null=True, blank=True,
                                      help_text="ID компанії-відправника.")
    company_name = models.CharField(max_length=256, null=True, blank=True,
                                    help_text="Назва компанії-відправника.")
    include_documents = models.JSONField(default=list, blank=True,
                                         help_text="Документи, що мають бути включені.")
    exclude_documents = models.JSONField(default=list, blank=True,
                                         help_text="Документи, що мають бути виключені.")
    adr = models.BooleanField(null=True, blank=True, help_text="Чи є вантаж ADR.") # не default=False, бо може бути None

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Фільтр пошуку Lardi"
        verbose_name_plural = "Фільтри пошуку Lardi"

    def __str__(self):
        return f"Фільтр для користувача {self.user.user.username}"
