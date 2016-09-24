from django.contrib import admin

from .models import Organization, Campaign, Contribution

class OrganizationAdmin(admin.ModelAdmin):
	list_display = ['name', 'slug', 'created']
	search_fields = ['name', 'slug', 'description']

admin.site.register(Organization, OrganizationAdmin)

class CampaignAdmin(admin.ModelAdmin):
	list_display = ['title', 'slug', 'owner', 'active', 'created', 'total_contributors', 'total_contributions']
	search_fields = ['title', 'slug', 'owner']
	raw_id_fields = ['owner']
	readonly_fields = ['total_contributors', 'total_contributions']

admin.site.register(Campaign, CampaignAdmin)

class ContributionAdmin(admin.ModelAdmin):
	list_display = ['id', 'campaign', 'contributor_summary', 'amount', 'ref_code', 'created']
	raw_id_fields = ['campaign']
	search_fields = ['cclastfour']

admin.site.register(Contribution, ContributionAdmin)
