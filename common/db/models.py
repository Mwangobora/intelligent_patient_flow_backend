import uuid 

from django.conf import settings
from django.db import models
from django.utils import timezone

class UUIDPrimaryKeyModel(models.Model):
    """
    abstract base model for all tables that use UUID primary keys
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    class Meta:
        abstract = True

class CreatedAtModel(UUIDPrimaryKeyModel):
    """
    Abstract base model for append-only or history tables and used when the model has id and created fields
    """
    created_at = models.DateTimeField(
        default=timezone.now, editable= False
    )

    class Meta:
        abstract = True

class TimeStampedModel(UUIDPrimaryKeyModel):
    """
    use this when table has id, created_at and updated_at
    """

    created_at = models.DateTimeField(
        default= timezone.now,
        editable= False
    )
    updated_at = models.DateTimeField(
        auto_now = True
    )

    class Meta:
        abstract = True


class ActiveModel(models.Model):
    """
    Active mixin that supports active and inactive states
    """

    is_active = models.BooleanField(default= True)

    class Meta:
        abstract = True

class CreatedByModel(TimeStampedModel):
    """
    Abstract base model for tables track who created the record
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete= models.SET_NULL,
        null= True,
        blank= True,
        related_name= "+",
    )

    class Meta:
        abstract = True
