from django.contrib import admin

from obe.integration.models import IdentifierAlias, IntegrationBatch

admin.site.register(IntegrationBatch)
admin.site.register(IdentifierAlias)
