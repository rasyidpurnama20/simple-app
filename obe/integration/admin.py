from django.contrib import admin

from obe.integration.models import IdentifierAlias, IntegrationBatch, IntegrationContract

admin.site.register(IntegrationBatch)
admin.site.register(IdentifierAlias)
admin.site.register(IntegrationContract)
