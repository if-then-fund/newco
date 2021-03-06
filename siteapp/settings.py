################################################################
# Good defaults for a setttings.py, plus logic for bringing    #
# in settings from various normal places you might store them. #
################################################################

import os, os.path, json

# What's the name of the app containing this file? That determines
# the module for the main URLconf etc.
primary_app = os.path.basename(os.path.dirname(__file__))

# LOAD ENVIRONMENT SETTINGS #
#############################

# shortcut function for getting a file in a 'local' subdirectory
# of the main Django project path (one up for this directory).
def local(fn):
	return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local', fn)

if os.path.exists(local("environment.json")):
	environment = json.load(open(local("environment.json")))
else:
	# Make some defaults.

	# This is how 'manage.py startproject' does it:
	def make_secret_key():
		from django.utils.crypto import get_random_string
		return get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')

	environment = {
		"secret-key": make_secret_key(),
		"debug": True,
		"host": "localhost:8000",
		"https": False,
	}

	print("Create a local/environment.json file! It should contain something like this:")
	print(json.dumps(environment, sort_keys=True, indent=2))
	
# DJANGO SETTINGS #
###################

# The SECRET_KEY must be specified in the environment.
SECRET_KEY = environment["secret-key"]

# The DEBUG flag must be set in the environment.
DEBUG = environment["debug"]

# The ADMINS field is optional. If set, it must be a list of lists
# like [['John', 'john@example.com'], ['Mary', 'mary@example.com']].
ADMINS = environment.get("admins", [])

# Set ALLOWED_HOSTS from the host environment. If it has a port, strip it.
# (The port is used in SITE_ROOT_URL must must be removed from ALLOWED_HOSTS.)
ALLOWED_HOSTS = [environment["host"].split(':')[0]]

# The allauth app requires the use of the sites framework, and many other
# apps do too, so set the SITE_ID.
SITE_ID = 1

# Add standard apps to INSTALLED_APPS.
INSTALLED_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.staticfiles',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.humanize',
]

# Add standard middleware.
MIDDLEWARE_CLASSES = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
]
if environment["debug"] and os.path.exists(os.path.join(os.path.dirname(__file__), 'helper_middleware.py')):
	MIDDLEWARE_CLASSES.append(primary_app+'.helper_middleware.DumpErrorsToConsole')

# Load templates for app directories and from a main `templates` directory located
# at the project root. Add standard context processors.
TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')],
		'OPTIONS': {
			'debug': DEBUG,
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
				'django.template.context_processors.static',
				'django.template.context_processors.tz',
				'django.template.context_processors.request', # allauth
			],
			'loaders': [
					'django.template.loaders.filesystem.Loader',
					'django.template.loaders.app_directories.Loader',
				],
		},
	},
]

# When in production, cache the templates once loaded from disk.
if not DEBUG:
	# Wrap the template loaders in the cached loader.
	TEMPLATES[0]['OPTIONS']['loaders'] = [
		('django.template.loaders.cached.Loader', TEMPLATES[0]['OPTIONS']['loaders'])
	]

# Use an Sqlite database at local/db.sqlite, until other database
# settings have been set in the environment.
DATABASES = {
	'default': {
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': local('db.sqlite3'),
	}
}
if not environment.get('db'):
	# Ensure the 'local' directory exists for the default Sqlite
	# database.
	if not os.path.exists(os.path.dirname(local('.'))):
		os.mkdir(os.path.dirname(local('.')))
else:
	# Enable database connection pooling (unless overridden in the
	# environment settings).
	DATABASES['default']['CONN_MAX_AGE'] = 60
	DATABASES['default'].update(environment['db'])

# Setup the cache. The default is a LocMemCache.
CACHES = {
	'default': {
		'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
		'LOCATION': '127.0.0.1:11211',
	}
}
if environment.get('memcached'):
	# But if the 'memcached' environment setting is true,
	# enable a memcached cache using the default host/port
	# (see above) *and* enable the cached_db session backend.
	CACHES['default']['BACKEND'] = 'django.core.cache.backends.memcached.MemcachedCache'
	SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Settings that have normal values based on the primary app
# (the app this file resides in).

ROOT_URLCONF = primary_app + '.urls'
WSGI_APPLICATION = primary_app + '.wsgi.application'

# Turn on TZ-aware datetimes. Store times in UTC in the database.

TIME_ZONE = 'UTC'
USE_TZ = True

# Use localization but not internationalization. You probably will
# want to change these if you are not making a U.S.-focused website.

LANGUAGE_CODE = 'en-us'
USE_I18N = False
USE_L10N = True

# Dump outbound emails to the console by default for debugging.
# If the "email" environment setting is present, it is a dictionary
# providing an SMTP server to send outbound emails to. TLS is
# always turned on.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_SUBJECT_PREFIX = '[' + environment['host'] + '] '
if environment.get("email"):
	EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
	EMAIL_HOST = environment["email"]["host"]
	EMAIL_PORT = environment["email"]["port"]
	EMAIL_HOST_USER = environment["email"]["user"]
	EMAIL_HOST_PASSWORD = environment["email"]["pw"]
	EMAIL_USE_TLS = True

# If the "https" environment setting is true, set the settings
# that keep sessions and cookies secure.
if environment["https"]:
	SESSION_COOKIE_HTTPONLY = True
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_HTTPONLY = True
	CSRF_COOKIE_SECURE = True

# Put static files in the virtual path "/static/". When the "static"
# environment setting is present, then it's a local directory path
# where "collectstatic" will put static files. The ManifestStaticFilesStorage
# is activated.
STATIC_URL = '/static/'
if environment.get("static"):
	STATIC_ROOT = environment["static"]
	STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Add a convenience setting "SITE_ROOT_URL" that stores the root URL
# of the website, constructed from the "https" and "host" environment
# settings
SITE_ROOT_URL = "%s://%s" % (("http" if not environment["https"] else "https"), environment["host"])

# Load all additional settings from settings_application.py.
from .settings_application import *
