from .settings import *

INSTALLED_APPS += [
	'siteapp'
]

DE_API = environment.get('democracyengine')

SERVER_EMAIL = 'newdems error <errors@mail.if.then.fund>'

