from .settings import *

INSTALLED_APPS += [
	'siteapp'
]

DE_API = environment.get('democracyengine')
