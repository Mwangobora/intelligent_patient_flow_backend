from django.contrib import admin

from .models import Facility, FacilityType, Organization

admin.site.register(Organization)
admin.site.register(FacilityType)
admin.site.register(Facility)
