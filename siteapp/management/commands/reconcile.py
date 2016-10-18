# Reconciles our records with Democracy Engine
# --------------------------------------------

from decimal import Decimal
import io

from django.core.management.base import BaseCommand, CommandError

from siteapp.views import DemocracyEngineAPI
from siteapp.models import Contribution

class Command(BaseCommand):
	args = ''
	help = 'Reports reconciliation issues between our records and Democracy Engine.'

	def handle(self, *args, **options):
		# Get recent donations from DE.
		donations = DemocracyEngineAPI.donations()

		# Process each donation that Democracy Engine knows.
		seen_contributions = set()
		for don in donations:
			self.process_de_donation(don, seen_contributions)

		# Anything missing from Democray Engine?
		first_contrib_id = min(seen_contributions)
		for c in Contribution.objects.filter(id__gt=first_contrib_id).exclude(id__in=seen_contributions):
			print("Contribution", c.id, "has no donation record on Democracy Engine.")

	def process_de_donation(self, don, seen_contributions):
		if don["authtest_request"]:
			# This was an authorization test. There's no need to
			# reconcile these. We don't do this on this site.
			return

		# This is an actual transaction.

		# Sanity checks.

		if not don["authcapture_request"]:
			print(don["donation_id"], "has authtest_request, authcapture_request both False")
			return

		if len(don["line_items"]) == 0:
			print(don["donation_id"], "has no line items")
			return

		txns = set()
		for line_item in don["line_items"]:
			txns.add(line_item["transaction_guid"])
		if len(txns) != 1:
			print(don["donation_id"], "has more than one transaction (should be one)")
			return

		if not isinstance(don["aux_data"], dict):
			print(don["donation_id"], "has invalid aux_data")
			return
		
		# What pledge does this correspond to?
		contribution_id = int(don["aux_data"]["contribution"])
		c = Contribution.objects.filter(id=contribution_id).first()
		if not c:
			print(don["donation_id"], "has invalid contribution ID")
			return

		# Remember that we've checked this Contribution.
		seen_contributions.add(contribution_id)

		# Check basic fields.
		for de_field, contrib_field in [
			("donor_first_name", "nameFirst"),
			("donor_last_name", "nameLast"),
			("donor_address1", "address"),
			("donor_city", "city"),
			("donor_state", "state"),
			("donor_zip", "zip"),
			("compliance_employer", "employer"),
			("compliance_occupation", "occupation"),
		]:
			if don.get(de_field) != c.contributor.get(contrib_field):
				print(don["donation_id"], "/", c.id, "has a mismatch in %s (%s, %s)" % (de_field, repr(don.get(de_field)), repr(c.contributor.get(contrib_field))))

		# Check recipients.
		recips = { r[0]["de_recipient_id"]: parse_decimal(r[1]) for r in c.recipients }
		for line_item in don["line_items"]:
			actual = parse_decimal(line_item["amount"].replace("$", ""))
			expected = recips.get(line_item["recipient_id"], Decimal(0))
			if actual != expected:
				print(don["donation_id"], "/", c.id, "has recipient mismatch %s got %s instead of %s"
					% (line_item["recipient_name"], actual, expected))
			if line_item["recipient_id"] in recips:
				del recips[line_item["recipient_id"]]

		# Anything orphaned?
		for r, expected in recips.items():
			print(don["donation_id"], "/", c.id, "has recipient mismatch %s got %s instead of %s"
				% (r, Decimal(0), expected))

def parse_decimal(s):
	# Parse and round to cents, because conversion from floats is inexact.
	return Decimal(s).quantize(Decimal('.01'))
