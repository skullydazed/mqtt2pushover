#!/usr/bin/env python3

import json
import os
import sys

import requests
from gourd import Gourd

MQTT_CLIENT_ID = os.environ.get('MQTT_CLIENT_ID', 'mqtt2pushover')
MQTT_HOST = os.environ.get('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_USER = os.environ.get('MQTT_USER', '')
MQTT_PASS = os.environ.get('MQTT_PASS', '')
MQTT_TOPIC_PREFIX = os.environ.get('MQTT_TOPIC', 'pushover')
MQTT_TOPIC = MQTT_TOPIC_PREFIX + '/#'

PUSHOVER_TOKEN = os.environ.get('PUSHOVER_TOKEN', '')
PUSHOVER_USER = os.environ.get('PUSHOVER_USER', '')
PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'

mqtt = Gourd(app_name=MQTT_CLIENT_ID, mqtt_host=MQTT_HOST, mqtt_port=MQTT_PORT, username=MQTT_USER, password=MQTT_PASS)


def validate_config():
    missing = [name for name, val in [('PUSHOVER_TOKEN', PUSHOVER_TOKEN), ('PUSHOVER_USER', PUSHOVER_USER)] if not val]
    if missing:
        sys.exit(f"ERROR: required environment variable(s) not set: {', '.join(missing)}")


def send_pushover(data):
    """Send a message to Pushover. data must include token, user, message."""
    try:
        response = requests.post(PUSHOVER_URL, json=data)
        response.raise_for_status()
        print(f'Sent Pushover message: {data.get("message", "")!r}')
    except requests.RequestException as e:
        print(f'ERROR sending Pushover message: {e}')


@mqtt.subscribe(MQTT_TOPIC)
def on_message(msg):
    """Forward MQTT messages to Pushover."""
    # Try to parse as JSON first
    try:
        payload = json.loads(msg.payload)
        if isinstance(payload, dict):
            data = {'token': PUSHOVER_TOKEN, 'user': PUSHOVER_USER}
            data.update(payload)
            send_pushover(data)
            return
    except (json.JSONDecodeError, ValueError):
        pass

    # Plain text: use subtopic as title if present
    subtopic = msg.topic.removeprefix(MQTT_TOPIC_PREFIX).strip('/').replace('/', ' ').replace('_', ' ').title()
    data = {
        'token': PUSHOVER_TOKEN,
        'user': PUSHOVER_USER,
        'message': msg.payload,
    }
    if subtopic:
        data['title'] = subtopic
    send_pushover(data)


if __name__ == '__main__':
    validate_config()
    mqtt.run_forever()
