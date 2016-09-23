from django.db import models, transaction

from jsonfield import JSONField

import decimal

alg = {
  "min_contrib": decimal.Decimal("1.00"), # dollars
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

  # Recipients.
  recipients = JSONField(help_text="A list of contribution recipients.")
  overflow_recipient = models.CharField(max_length=64, help_text="The overflow recipient.")

  # Totals.
  total_contributors = models.IntegerField(default=0, help_text="A running total of the number of individuals who made a contribution through this Campaign.")
  total_contributions = models.DecimalField(max_digits=6, decimal_places=2, default=0, help_text="A running total of contributions made through this Campaign.")

  # Additional data.
  extra = JSONField(blank=True, help_text="Additional information stored with this object.")
  created = models.DateTimeField(auto_now_add=True, db_index=True)
  updated = models.DateTimeField(auto_now=True, db_index=True)

  def __repr__(self):
    return "<Campaign(%d, %s, %s)>" % (self.id, repr(self.owner), repr(self.title))

  def get_minimum_contribution(self):
    # The minimum pledge is one cent to all possible recipients, plus fees,
    # and at least a fixed minimum pledge.
    m = decimal.Decimal('0.01') * num_recipients * (1 + alg['fees_percent']) + alg['fees_fixed']
    m = m.quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_UP)
    return max(m, alg['min_contrib'])

  def get_suggested_contribution(self):
    # What's a nice round number to suggest the user pledge?
    m = decimal.Decimal('100.00')
    assert m >= self.get_minimum_pledge()
    return m

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
  amount = models.DecimalField(max_digits=6, decimal_places=2, help_text="The contribution amount, in dollars --- the same amount the user's credit card was charged.")
  fees = models.DecimalField(max_digits=6, decimal_places=2, help_text="The portion of the contribution allocated to fees.")
  cclastfour = models.CharField(max_length=4, blank=True, null=True, db_index=True, help_text="The last four digits of the user's credit card number, stored & indexed for fast look-up in case we need to find a Contribution from a credit card number.")

  # Execution
  recipients = JSONField(help_text="A list of contribution recipients and the amount each recipient is receiving.")
  transaction = JSONField(help_text="The Democracy Engine transaction record.")

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
    self.campaign.total_contributors = models.F('total_contributors') - 1
    self.campaign.total_contributions = models.F('total_contributions') - self.amount
    self.campaign.save(update_fields=['total_contributors', 'total_contributions'])
    super(Contribution, self).delete()  

  # STATIC

  @staticmethod
  def createRandomContributor():
    # For testing!
    import random
    return {
      "nameFirst": random.choice(["Jeanie", "Lucrecia", "Marvin", "Jasper", "Carlo", "Millicent", "Zack", "Raul", "Johnny", "Margarette"]),
      "nameLast": random.choice(["Ramm", "Berns", "Wannamaker", "McCarroll", "Bumbrey", "Caudle", "Bridwell", "Pacelli", "Crowley", "Montejano"]),
      "address": "%d %s %s" % (random.randint(10, 200), random.choice(["Fir", "Maple", "Cedar", "Dogwood", "Persimmon", "Beech"]), random.choice([ "St", "Ave", "Ct"])),
      "city": random.choice(["Rudy", "Hookerton", "La Ward", "Marenisco", "Nara Visa"]),
      "state": random.choice(["NQ", "BL", "PS"]),
      "zip": random.randint(10000, 88888),
      "employer": random.choice(["self", "Pear Inc.", "Woogle"]),
      "occupation": random.choice(["retired", "chief executive", "staffer"]),
    }

  # STRINGS

  @property
  def contributor_summary(self):
    return ' '.join(
      self.contributor[k] for k in ('nameFirst', 'nameLast', 'city', 'state')
      )
