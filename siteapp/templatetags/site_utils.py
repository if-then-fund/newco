from django import template
from django.utils import safestring
from django.template.defaultfilters import stringfilter, strip_tags

import locale

import CommonMark

register = template.Library()

@register.filter(is_safe=True)
def currency(value, hide_zero_cents=True):
	locale.setlocale(locale.LC_ALL, '')
	s = locale.currency(value, grouping=True)
	if hide_zero_cents and s.endswith(".00"):
		# drop cents
		s = s[:-3]
	return s

@register.filter(is_safe=True)
@stringfilter
def markdown(value):
	value = CommonMark.commonmark(value)
	return safestring.mark_safe(value)
