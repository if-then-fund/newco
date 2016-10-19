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
	list_display = ['id', 'campaign', 'contributor_summary', 'amount_', 'ref_code', 'created']
	raw_id_fields = ['campaign']
	search_fields = ['cclastfour']

	def amount_(self, obj):
		if obj.extra and obj.extra.get("void"):
			return "voided"
		else:
			return obj.amount

	# remove the Delete action?, add our void action
	actions = ['void']
	def void(modeladmin, request, queryset):
		# Void selected pledge executions. Collect return
		# values and exceptions.
		voids = []
		for c in queryset:
			try:
				voids.append([c.id, c.void()])
			except Exception as e:
				voids.append([c.id, str(e)])
		return json_response(voids)

admin.site.register(Contribution, ContributionAdmin)

def json_response(data):
	import json
	from django.http import HttpResponse
	response = HttpResponse(content_type="application/json")
	json.dump(data, response)
	return response
