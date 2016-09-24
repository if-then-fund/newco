from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View

from .models import alg, Campaign, Contribution
from .templatetags.site_utils import currency

from email_validator import validate_email

import random
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_EVEN

def recipient_sort_key(recip):
  recip_sort_order = ["candidate", "pac", "c4"]
  return (recip_sort_order.index(recip["type"]), recip["name"])

# recipients = [
#   { "id": "A", "type": "candidate", "points": 2, "name": "A" },
#   { "id": "B", "type": "candidate", "points": 3, "name": "B" },
#   { "id": "C", "type": "candidate", "points": 4, "name": "C" },
#   { "id": "R1", "type": "pac", "name": "PAC" },
#   { "id": "R2", "type": "c4", "name": "C4" },
# ]

class ContributionFormView(View):
  def dispatch(self, request):
    self.campaign = get_object_or_404(Campaign, id=1, active=True)
    return super().dispatch(request)

  # Render the form page.
  def get(self, request):
      # Get the contribution limits for the campaign.
      limits = contribution_limits_for_display(
        compute_minimum_contribution(self.campaign.recipients),
        compute_maximum_contribution(self.campaign.recipients))

      # Get the suggested contribution amount from the Campaign but
      # make sure it is within limits.
      suggested_amount = min(max(self.campaign.suggested_amount, limits[0]), limits[1])

      return render(request, 'form-page.html', {
        "suggested_amount": int(suggested_amount), # suppress cents
        "min_contrib": limits[0],
        "max_contrib": limits[1],
        "recipients": sorted(self.campaign.recipients, key=recipient_sort_key),
        "rstate": random.getrandbits(32), # see split_contribution_to_recipients
        "random_user_info": Contribution.createRandomContributor(),
        "SITE_DOMAIN": "if.then.fund",
      })

  # Process the AJAX request on form submission.
  def post(self, request):
    # Parse just enough of the form to compute the line items
    # for the preview.

    try:
      amount = Decimal(request.POST['amount'])
    except ValueError:
      # Should be client-side validated.
      return JsonResponse({'status': 'error', 'message': 'Invalid contribution amount.'})

    # Compute line-items.
    random_seed = request.POST['rstate']
    line_items = compute_line_items(self.campaign.recipients, amount, random_seed)

    if request.POST.get("method") != "execute":
      # Format the amounts for display.
      line_items = [(line_item[0], currency(line_item[1], hide_zero_cents=False)) for line_item in line_items]
      
      # Return the line items.
      return JsonResponse({ 'line_items': line_items })

    # Create a Contribution record.

    try:
      contribution = Contribution.objects.create(
        campaign=self.campaign,
        contributor={
          "email": validate_email(request.POST["email"])["email"], # validate & normalize
          "nameFirst": request.POST["nameFirst"],
          "nameLast": request.POST["nameLast"],
          "address": request.POST["address"],
          "city": request.POST["city"],
          "state": request.POST["state"],
          "zip": request.POST["zip"],
          "occupation": request.POST["occupation"],
          "employer": request.POST["employer"],
        },
        amount=amount,
        cclastfour=request.POST["ccNum"][-4:],
        recipients=line_items,
        ref_code=request.POST["ref_code"],
      )
    except ValueError as e:
      return JsonResponse({'status': 'error', 'message': str(e)})

    # Execute the transaction.

    return JsonResponse({'status': 'ok'})

def compute_minimum_contribution(recipients):
  # The minimum contribution is 50 cents to the receipient with the
  # lowest points, then proportional amounts to the remaining recipients,
  # rounded up. It must be at least min_contrib. We use 50 cents and not
  # 1 cent because fees will be taken off later, so it shouldn't be too
  # small.
  min_points = min(Decimal(recip["points"]) for recip in recipients if "points" in recip)
  min_contribution = max(
    alg['min_contrib'],
      sum(
        round_to_cents(Decimal(recip["points"])/min_points*Decimal("0.50"), ROUND_UP)
        for recip in recipients if "points" in recip),
    )

  # sanity check that line items are computable
  assert compute_line_items(recipients, min_contribution, None)

  return min_contribution

def get_recipient_limit(recipient):
  r = alg['limits'][recipient['type']]
  if "limit" in recipient:
    r = min(r, recipient["limit"])
  return r

def compute_maximum_contribution(recipients):
  # The maximum contribution is the sum of the contribution limits
  # for each recipient and all overflow recipients. It must not
  # exceed 'max_contrib'.
  maximum_contribution = min(
    alg['max_contrib'],
    sum(get_recipient_limit(recip) for recip in recipients)
    )

  # sanity check that line items are computable
  assert compute_line_items(recipients, maximum_contribution, None)

  return maximum_contribution


def contribution_limits_for_display(min_contrib, max_contrib):
  # Adjust the limits for display purposes.

  from math import log

  # Try rounding the minimum up to the nearest number that is 1 and
  # a bunch of zeros.
  x = Decimal("10") ** int(log(min_contrib)/log(10)+1)
  if x < max_contrib/50:
    min_contrib = x

  # Try rounding the maximum down to the nearest number that is 1 and
  # a bunch of zeroes.
  x = Decimal("10") ** int(log(max_contrib)/log(10))
  if x > min_contrib*50:
    max_contrib = x

  return (min_contrib, max_contrib)


def compute_line_items(recipients, amount, random_seed):
  # Split the amount to the recipients that have 'points' fields.
  line_items = split_contribution_to_recipients(
    [recip for recip in recipients if "points" in recip],
    amount,
    random_seed)

  # Send the rest to overflow recipients.
  overflow_recipients = [recip for recip in recipients if "points" not in recip]
  while True:
    # How much remains?
    remaining = amount - sum(line_item[1] for line_item in line_items)
    if remaining == 0:
      break

    # Do we have an overflow recipient that can take it?
    if len(overflow_recipients) == 0:
      raise ValueError("The amount is greater than the maximum contribution by $%s." % remaining)

    # Add a line item for the next overflow recipient. The recipient
    # may have a limit.
    recip = overflow_recipients.pop(0)
    line_items.append( (recip, min(remaining, get_recipient_limit(recip)) ) )

  # Sanity check.
  assert amount == sum(line_item[1] for line_item in line_items)

  # Sort.
  line_items.sort(key = lambda line_item : recipient_sort_key(line_item[0]))

  return line_items


def split_contribution_to_recipients(recipients, amount, random_seed):
  # Split a contribution among recipients, with each recipient
  # getting an amount proportional to their "points", until
  # limits are hit.

  # recursive base case
  if len(recipients) == 0:
    return []

  # The recipients all have "points" to allow for some recipients to
  # receive more of the contribution than others. Each point is "worth"
  # amount/total_points.
  total_points = sum(Decimal(recip["points"]) for recip in recipients)

  # Compute the apportionment based on the points.
  fixed_line_items = []
  free_line_items = []
  for recip in recipients:
    recip_amount = round_to_cents(amount * recip["points"] / total_points, ROUND_DOWN)

    if recip_amount < Decimal("0.01"):
      raise ValueError("The amount is too small.")

    # But there are contribution limits. If any recipient exceeds its
    # limit, then fix its amount (both in the sense of "correct" its
    # amount and also "make static" its amount).
    if recip_amount > alg["limits"][recip["type"]]:
      # Set the amount to the limit.
      fixed_line_items.append( (recip, alg["limits"][recip["type"]]) )
    else:
      # Record the proportional amount.
      free_line_items.append( (recip, recip_amount) )

  # If no recipient exceeded limits, return them as-is.
  if len(fixed_line_items) == 0:
    # Each recipient got a certain number of cents, with rounding down. That
    # often leaves some cents remaining. Distribute those cents randomly to
    # any recipients that can take it. But seed the random number generator
    # with the given value so that the distribution is stable across calls,
    # so that whatever we show the user as a preview is what sticks at
    # submission.
    random.seed(random_seed)
    remaining_amount = amount - sum(line_item[1] for line_item in free_line_items)
    # For each cent that needs to be put somewhere...
    for i in range(int(remaining_amount*100)):
      # Which recipients have room for another cent?
      dist_recipients = [i for i, line_item in enumerate(free_line_items)
        if get_recipient_limit(line_item[0]) > line_item[1]]
      if len(dist_recipients) == 0:
        # Everyone is at limits now -- can't distribute any more.
        break
      # Pick a random line item and increment it by one cent.
      line_item_index = random.choice(dist_recipients)
      free_line_items[line_item_index] = (free_line_items[line_item_index][0], free_line_items[line_item_index][1]+Decimal("0.01"))

    return free_line_items

  # Since some recipients exceeded limits, re-apportion the overflow
  # to the remaining recipients by calling this function recursively
  # on the recipients that did not exceed limits, with the contribution
  # amount that remains after taking into account the ones that did
  # exceed limits.
  remaining_recipients = [line_item[0] for line_item in free_line_items]
  remaining_amount = amount - sum(line_item[1] for line_item in fixed_line_items)
  return fixed_line_items + split_contribution_to_recipients(remaining_recipients, remaining_amount, random_seed)

def round_to_cents(amount, rounding_type):
  return amount.quantize(Decimal('.01'), rounding=rounding_type)