#!/bin/bash

# On a new machine, run:
# sudo deployment/setup.sh

#########################################

set -euo pipefail # "strict mode"

DOMAIN=newdems-demo.ifthenfund.com

# THE SYSTEM
############

# Update system packages.
sudo apt-get update && apt-get upgrade -y

# NGINX
#######

# Install packages.
sudo apt-get install -y \
	unzip \
	python3 python-virtualenv python3-pip \
	python3-yaml \
	nginx uwsgi-plugin-python3 supervisor \
	memcached

# Turn off nginx's default website.
sudo rm -f /etc/nginx/sites-enabled/default

# Put in our nginx site config.
cat `pwd`/deployment/nginx.conf | \
	sed s/DOMAIN/$DOMAIN/ | \
	cat - > /tmp/site.conf \
	&& sudo mv /tmp/site.conf /etc/nginx/sites-enabled/site.conf

# Install TLS cert provisioning tool.
sudo apt-get install -y build-essential libssl-dev libffi-dev python3-dev python3-pip
sudo pip3 install free_tls_certificates

# Generate a self-signed cert so that nginx can start.
sudo free_tls_certificate $DOMAIN /etc/ssl/local/ssl_certificate.key /etc/ssl/local/ssl_certificate.crt /home/ubuntu/public_html /home/ubuntu/acme-le-account

# Restart nginx.
sudo service nginx restart

# Create cron job to refresh cert.
cat > /tmp/cronjob <<EOF;
free_tls_certificate $DOMAIN /etc/ssl/local/ssl_certificate.key /etc/ssl/local/ssl_certificate.crt /home/ubuntu/public_html /home/ubuntu/acme-le-account \
	&& sudo service nginx restart
EOF
chmod +x /tmp/cronjob
sudo mv /tmp/cronjob /etc/cron.daily/letsencrypt

# Procure real TLS certificate now that nginx is up.
sudo /etc/cron.daily/letsencrypt
sudo service nginx restart

# WSGI
######

# Supervisor, which runs uwsgi
ln -sf `pwd`/deployment/supervisor.conf /etc/supervisor/conf.d/site.conf

# Place for static assets.
mkdir -p ../public_html/static

# Install dependencies.
pip3 install -r requirements.txt

# After getting up for the first time-

# Create an 'admin' user.
#python3 manage.py createsuperuser --username=admin --email=admin@$DOMAIN --noinput
# gain access with: ./manage.py changepassword admin

# sudo service supervisor restart
