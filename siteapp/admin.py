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
	list_display = ['id', 'campaign', 'contributor_summary', 'amount', 'ref_code', 'status', 'created']
	raw_id_fields = ['campaign']
	search_fields = ['cclastfour']

	def status(self, obj):
		status = []
		if not obj.transaction:
			status.append("no transaction")
		elif obj.transaction.get("error"):
			status.append("ERROR")
		if obj.extra and obj.extra.get("void"):
			status.append( "/".join(v.get("method") or "ERROR" for v in obj.extra["void"]) )
		if obj.extra and obj.extra.get("error_sending_receipt"):
			status.append("receipt email error")
		if len(status) == 0: status.append("ok")
		return ", ".join(status)

	# remove the Delete action?, add our void action
	actions = ['void', 'send_receipt']
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

	def send_receipt(modeladmin, request, queryset):
		from .views import send_receipt as do_send_receipt
		response = []
		for c in queryset:
			try:
				response.append( (c.id, do_send_receipt(c)) )
			except Exception as e:
				response.append( (c.id, str(e)) )
		return json_response(response)


admin.site.register(Contribution, ContributionAdmin)

def json_response(data):
	import json
	from django.http import HttpResponse
	response = HttpResponse(content_type="application/json")
	json.dump(data, response)
	return response
