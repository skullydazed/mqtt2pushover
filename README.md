# mqtt2pushover

Bridges MQTT messages to [Pushover](https://pushover.net) push notifications.

Subscribes to `pushover/#` MQTT topics and forwards each message to the Pushover API.

## Message formats

**Plain text** — the payload becomes the message body. The subtopic is used as the title, with `/` and `_` replaced by spaces and title-cased. For example, a message published to `pushover/front_door/alert` will arrive with title "Front Door Alert".

**JSON** — the payload is passed directly to the Pushover API as fields. `token` and `user` are set from environment variables but can be overridden. `message` is required. Any other Pushover API field is supported (`title`, `url`, `priority`, `sound`, `device`, etc.).

```bash
# Plain text
mosquitto_pub -t pushover/front_door/alert -m "Motion detected"

# JSON with URL
mosquitto_pub -t pushover/test -m '{"message":"Deploy finished","url":"https://example.com"}'
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USER` | `` | MQTT username |
| `MQTT_PASS` | `` | MQTT password |
| `MQTT_TOPIC` | `pushover/#` | MQTT topic to subscribe to |
| `PUSHOVER_TOKEN` | `` | Pushover app API token |
| `PUSHOVER_USER` | `` | Pushover user key |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp mqtt2pushover.service.example mqtt2pushover.service
# Edit mqtt2pushover.service with your PUSHOVER_TOKEN and PUSHOVER_USER
sudo ln -s $PWD/mqtt2pushover.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mqtt2pushover
```
