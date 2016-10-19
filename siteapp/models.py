from django.db import models, transaction
from django.utils.timezone import now

from jsonfield import JSONField

import decimal

alg = {
  "min_contrib": decimal.Decimal("5.00"), # dollars
  "max_contrib": decimal.Decimal("250000.00"), # dollars
  "limits": {
    "candidate": decimal.Decimal("2700"), # dollars, per election
    "pac": decimal.Decimal("5000"), # dollars, per year
    "c4": decimal.Decimal("100000"), # dollars, we chose this limit to not be insane
  }
}

class Organization(models.Model):
  """An organization is a Newco client."""

  name = models.CharField(max_length=200, help_text="The name of the Organization.")
  slug = models.SlugField(max_length=200, help_text="The unique URL slug for this Organization.")

  description = models.TextField(blank=True, help_text="Descriptive text describing the Organization.")

  # Additional data.
  extra = JSONField(blank=True, help_text="Additional information stored with this object.")
  created = models.DateTimeField(auto_now_add=True, db_index=True)
  updated = models.DateTimeField(auto_now=True, db_index=True)

  def __repr__(self):
    return "<Organization(%d, %s)>" % (self.id, repr(self.name))

  def __str__(self):
    return "#%d %s" % (self.id, repr(self.name))

class Campaign(models.Model):
  """A call to action."""

  # Metadata
  owner = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="campaigns", help_text="The organization which owns the Campaign.")
  title = models.CharField(max_length=200, help_text="The title for the campaign.")
  slug = models.SlugField(max_length=200, help_text="The URL slug for this campaign.")
  active = models.BooleanField(default=False, help_text="Is this campaign active?")

  # Content
  headline = models.CharField(max_length=256, help_text="Headline/call-to-action text for the page.")
  subhead = models.TextField(help_text="Short sub-heading text for use in list pages and the meta description tag, in CommonMark format.")
  body = models.TextField(help_text="Body text, in CommonMark format.")
  suggested_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="The suggested contribution amount -- the initial amount displayed to the user.")

  # Recipients.
  recipients = JSONField(default=[], blank=True, help_text="A list of contribution recipients.")

  # Totals.
  total_contributors = models.IntegerField(default=0, help_text="A running total of the number of individuals who made a contribution through this Campaign.")
  total_contributions = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="A running total of contributions made through this Campaign.")

  # Additional data.
  extra = JSONField(blank=True, help_text="Additional information stored with this object.")
  created = models.DateTimeField(auto_now_add=True, db_index=True)
  updated = models.DateTimeField(auto_now=True, db_index=True)

  def __repr__(self):
    return "<Campaign(%d, %s, %s)>" % (self.id, repr(self.owner), repr(self.title))

  def __str__(self):
    return "#%d %s (%s)" % (self.id, self.title, str(self.owner))

class NoMassDeleteManager(models.Manager):
  class CustomQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
      # Can't do a mass delete because it would not update Trigger.total_pledged,
      # in the case of the Pledge model.
      #
      # Instead call delete() on each instance, which handles the constraint.
      for obj in self:
        obj.delete(*args, **kwargs)
  def get_queryset(self):
    return NoMassDeleteManager.CustomQuerySet(self.model, using=self._db)

class Contribution(models.Model):
  """A contribution made by a user."""

  # Main fields.
  campaign = models.ForeignKey(Campaign, related_name="contributions", on_delete=models.PROTECT, help_text="The Campaign that this Contribution was made for.")
  contributor = JSONField(help_text="Contributor name, address, occupation, and employer.")
  amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="The contribution amount, in dollars --- the same amount the user's credit card was charged.")
  cclastfour = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a Contribution from a credit card number.")

  # Execution
  recipients = JSONField(help_text="A list of contribution recipients and the amount each recipient is receiving.")
  transaction = JSONField(blank=True, help_text="The Democracy Engine transaction record.")

  # Meta.
  ref_code = models.CharField(max_length=24, blank=True, null=True, db_index=True, help_text="An optional referral code that lead the user to take this action, e.g. from a utm_campaign query string argument.")

  # Additional data.
  extra = JSONField(blank=True, help_text="Additional information stored with this object.")
  created = models.DateTimeField(auto_now_add=True, db_index=True)
  updated = models.DateTimeField(auto_now=True, db_index=True)

  objects = NoMassDeleteManager()

  def __repr__(self):
    return "<Contribution(%d, %s, %s, %s)>" % (self.id, repr(self.campaign), repr(self.contributor_summary), repr(self.amount))

  # SAVE/DELETE

  def save(self, *args, **kwargs):
    # Override .save() so on the INSERT of a new Contribution we increment
    # counters on the Campaign.
    is_new = (not self.id) # if the pk evaluates to false, Django does an INSERT

    # Actually save().
    super(Contribution, self).save(*args, **kwargs)

    # For a new object, increment the Campaign's counters.
    if is_new:
      self.campaign.total_contributors = models.F('total_contributors') + 1
      self.campaign.total_contributions = models.F('total_contributions') + self.amount
      self.campaign.save(update_fields=['total_contributors', 'total_contributions'])

  def delete(self):
    if self.transaction:
      # ContributionFormView deletes Contribution instances that fail at the payment stage.
      raise Exception("Cannot delete a Contribution that has been processed.")
    self.decrement()
    super(Contribution, self).delete()  

  def decrement(self):
    self.campaign.total_contributors = models.F('total_contributors') - 1
    self.campaign.total_contributions = models.F('total_contributions') - self.amount
    self.campaign.save(update_fields=['total_contributors', 'total_contributions'])

  def void(self):
    # A user has asked us to void a transaction.

    from .views import DemocracyEngineAPI
    from .de import HumanReadableValidationError

    if not self.extra: self.extra = { }

    # Is there anything to void?
    if self.extra.get("void"):
      raise ValueError("Contribution has already been voided.")
    
    # Void or refund the transaction. There should be only one, but
    # just in case get a list of all mentioned transactions for the
    # donation.
    output = []
    voids = []
    txns = set(item['transaction_guid'] for item in self.transaction['line_items'])
    successful = False
    for txn_guid in txns:
      # This raises a 404 exception if the transaction info is not
      # yet available.
      try:
        txn = DemocracyEngineAPI.get_transaction(txn_guid)
      except Exception as e:
        output.append((txn_guid, "Error: " + str(e)))
        continue

      # Validate.
      if txn['status'] not in ("authorized", "captured", "voided", "credited"):
        output.append((txn_guid, "Not sure what to do with a transaction with status %s." % txn['status']))
        continue

      # Prepare some return status information.
      ret = {
        "txn": txn,
        "timestamp": now().isoformat(),
      }
      voids.append(ret)

      if txn['status'] in ("voided", "credited"):
        ret["method"] = "reconciled"
        successful = True
        output.append((txn_guid, "OK. Status on Democracy Engine is already %s." % txn['status']))
        continue

      # Attempt void.
      try:
        DemocracyEngineAPI.void_transaction(txn_guid)
        output.append((txn_guid, "Voided."))
        ret["method"] = "void"
        successful = True
      except HumanReadableValidationError as e:
        # Void failed.

        # The transaction exists but is not captured yet, so
        # we can't do anything.
        if str(e) == "please wait until the transaction has captured before voiding or crediting":
          output.append((txn_guid, str(e)))
          continue

        # Try credit.
        ret["void_error"] = str(e)
        try:
          DemocracyEngineAPI.credit_transaction(txn_guid)
          output.append((txn_guid, "Credited."))
          ret["method"] = "credit"
          successful = True
        except Exception as e1:
          ret["credit_error"] = str(e1)
          output.append((txn_guid, str(e) + "/" + str(e1)))
          continue

    # Store result.
    if len(voids) > 0:
      self.extra['void'] = voids
      self.save(update_fields=["extra"])

    if successful:
      self.decrement()

    # Return status info.
    return "\n".join((ret[0] + ": " + ret[1]) for ret in output)

  # STATIC

  @staticmethod
  def createRandomContributor():
    # For testing!
    import random
    return {
      "nameFirst": random.choice(["Jeanie", "Lucrecia", "Marvin", "Jasper", "Carlo", "Millicent", "Zack", "Raul", "Johnny", "Margarette"]),
      "nameLast": random.choice(["Ramm", "Berns", "Wannamaker", "McCarroll", "Bumbrey", "Caudle", "Bridwell", "Pacelli", "Crowley", "Montejano"]),
      "phone": "(202) 555-1234",
      "address": "%d %s %s" % (random.randint(10, 200), random.choice(["Fir", "Maple", "Cedar", "Dogwood", "Persimmon", "Beech"]), random.choice([ "St", "Ave", "Ct"])),
      "city": random.choice(["Rudy", "La Ward", "Marenisco", "Nara Visa"]),
      "state": random.choice(["NY", "CA", "WY", "KS"]),
      "zip": random.randint(10000, 88888),
      "employer": random.choice(["self", "Pear Inc.", "Woogle"]),
      "occupation": random.choice(["retired", "chief executive", "staffer"]),
    }

  # STRINGS

  @property
  def contributor_summary(self):
    return ' '.join(
      self.contributor[k] for k in ('email', 'nameFirst', 'nameLast', 'city', 'state')
      )
