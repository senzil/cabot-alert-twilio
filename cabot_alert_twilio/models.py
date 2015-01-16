from os import environ as env

from django.db import models
from django.conf import settings
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.template import Context, Template

from twilio.rest import TwilioRestClient
from twilio import twiml
import requests
import logging

from cabot.cabotapp.alert import AlertPlugin, AlertPluginUserData

telephone_template = "This is an urgent message from Arachnys monitoring. Service \"{{ service.name }}\" is erroring. Please check Cabot urgently."
sms_template = "Service {{ service.name }} {% if service.overall_status == service.PASSING_STATUS %}is back to normal{% else %}reporting {{ service.overall_status }} status{% endif %}: {{ scheme }}://{{ host }}{% url 'service' pk=service.id %}"

class TwilioPhoneCall(AlertPlugin):
    name = "Twilio Phone Call"
    author = "Jonathan Balls"
    def send_alert(service, users, duty_officers):
        # No need to call to say things are resolved
        if service.overall_status != service.CRITICAL_STATUS:
            return
        client = TwilioRestClient(
            settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        mobiles = [u.profile.prefixed_mobile_number for u in duty_officers if hasattr(
            u, 'profile') and u.profile.mobile_number]
        url = 'http://%s%s' % (settings.WWW_HTTP_HOST,
                               reverse('twiml-callback', kwargs={'service_id': service.id}))
        for mobile in mobiles:
            try:
                client.calls.create(
                    to=mobile,
                    from_=settings.TWILIO_OUTGOING_NUMBER,
                    url=url,
                    method='GET',
                )
            except Exception, e:
                logger.exception('Error making twilio phone call: %s' % e)

class TwilioSMS(AlertPlugin):
    name = "Twilio SMS"
    author = "Jonathan Balls"

    def send_alert(service, users, duty_officers):
        client = TwilioRestClient(
            settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        mobiles = [u.profile.prefixed_mobile_number for u in users if hasattr(
            u, 'profile') and u.profile.mobile_number]
        if service.is_critical:
            mobiles += [u.profile.prefixed_mobile_number for u in duty_officers if hasattr(
                u, 'profile') and u.profile.mobile_number]
        c = Context({
            'service': service,
            'host': settings.WWW_HTTP_HOST,
            'scheme': settings.WWW_SCHEME,
        })
        message = Template(sms_template).render(c)
        mobiles = list(set(mobiles))
        for mobile in mobiles:
            try:
                client.sms.messages.create(
                    to=mobile,
                    from_=settings.TWILIO_OUTGOING_NUMBER,
                    body=message,
                )
            except Exception, e:
                logger.exception('Error sending twilio sms: %s' % e)

class TwilioUserData(AlertPluginUserData):
    name = "Twilio Plugin"
    phone_number = models.CharField(max_length=30, blank=True, null=True)