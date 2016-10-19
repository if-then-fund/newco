from .settings import *

INSTALLED_APPS += [
	'siteapp'
]

DE_API = environment.get('democracyengine')
MIXPANEL_KEY = environment.get('mixpanel_key')

SERVER_EMAIL = 'newdems error <errors@mail.if.then.fund>'
RECEIPT_FROM_EMAIL = 'no-reply@mail.if.then.fund'
RECEIPT_REPLY_TO = 'ideas@if.then.fund'
