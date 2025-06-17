from django.db import models
from django.contrib.auth.models import AbstractUser, Permission
# Create your models here.
class MyUser(AbstractUser):
    first_name = models.CharField(max_length=30)  # Making first name mandatory
    last_name = models.CharField(max_length=150)  # Making last name mandatory
    phone_number_1 = models.CharField(max_length=250, blank=True, null=True)
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='myuse_t',  # Changed related_name for uniqueness
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='myuse_permissions_t',  # Changed related_name for uniqueness
        verbose_name='user permissions'
    )

    def __str__(self):
        return self.username