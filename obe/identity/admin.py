from django.contrib import admin

from obe.identity.models import AccountSecurity, LecturerProfile, MFAChallenge, RoleAssignment

admin.site.register(RoleAssignment)
admin.site.register(AccountSecurity)
admin.site.register(MFAChallenge)
admin.site.register(LecturerProfile)
