#!/bin/sh

VENDOR=siteapp/static/vendor

rm -rf $VENDOR
mkdir -p $VENDOR
wget -qO $VENDOR/jquery.payment.js https://raw.githubusercontent.com/stripe/jquery.payment/3dbada6a8c7fbb0d13ac121d0581a738d9576f53/lib/jquery.payment.js
wget -qO $VENDOR/mailcheck.min.js https://raw.githubusercontent.com/mailcheck/mailcheck/v1.1.1/src/mailcheck.min.js
wget -qO $VENDOR/jquery.selectric.min.js https://raw.githubusercontent.com/lcdsantos/jQuery-Selectric/1.11.0/public/jquery.selectric.min.js
wget -qO $VENDOR/selectric.css https://raw.githubusercontent.com/lcdsantos/jQuery-Selectric/1.11.0/public/selectric.css
