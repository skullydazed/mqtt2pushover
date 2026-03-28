import json
import logging
import sys
import unittest.mock

import pytest
import requests


class MockMsg:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


@pytest.fixture(scope='module')
def mod():
    sys.modules.pop('mqtt2pushover', None)
    mock_gourd_instance = unittest.mock.MagicMock()
    # subscribe() is used as a decorator — it must return the function unchanged
    mock_gourd_instance.subscribe.return_value = lambda f: f
    with unittest.mock.patch('gourd.Gourd', return_value=mock_gourd_instance):
        import mqtt2pushover

        return mqtt2pushover


# --- validate_config tests ---


@pytest.mark.parametrize(
    'token,user',
    [
        ('', ''),
        ('tok', ''),
        ('', 'usr'),
    ],
)
def test_validate_config_missing_raises(mod, token, user, monkeypatch):
    monkeypatch.setattr(mod, 'PUSHOVER_TOKEN', token)
    monkeypatch.setattr(mod, 'PUSHOVER_USER', user)
    with pytest.raises(SystemExit) as exc:
        mod.validate_config()
    assert 'ERROR' in str(exc.value)


def test_validate_config_ok(mod, monkeypatch):
    monkeypatch.setattr(mod, 'PUSHOVER_TOKEN', 'tok')
    monkeypatch.setattr(mod, 'PUSHOVER_USER', 'usr')
    mod.validate_config()  # must not raise


# --- send_pushover tests ---


def test_send_pushover_success(mod):
    data = {'token': 't', 'user': 'u', 'message': 'hello'}
    with (
        unittest.mock.patch('requests.post') as mock_post,
        unittest.mock.patch.object(mod, 'publish_status') as mock_status,
    ):
        mock_post.return_value.raise_for_status.return_value = None
        mod.send_pushover(data, 'pushover/alerts')
    mock_post.assert_called_once_with(mod.PUSHOVER_URL, json=data)
    mock_post.return_value.raise_for_status.assert_called_once()
    mock_status.assert_called_once_with('pushover/alerts', True)


def test_send_pushover_http_error(mod, caplog):
    data = {'token': 't', 'user': 'u', 'message': 'hello'}
    with (
        unittest.mock.patch('requests.post') as mock_post,
        unittest.mock.patch.object(mod, 'publish_status') as mock_status,
        caplog.at_level(logging.ERROR, logger='mqtt2pushover'),
    ):
        mock_post.return_value.raise_for_status.side_effect = requests.HTTPError('403')
        mod.send_pushover(data, 'pushover/alerts')  # must not raise
    assert '403' in caplog.text
    args = mock_status.call_args[0]
    assert args[1] is False
    assert '403' in args[2]


def test_send_pushover_network_error(mod, caplog):
    data = {'token': 't', 'user': 'u', 'message': 'hello'}
    with (
        unittest.mock.patch(
            'requests.post', side_effect=requests.ConnectionError('refused')
        ),
        unittest.mock.patch.object(mod, 'publish_status') as mock_status,
        caplog.at_level(logging.ERROR, logger='mqtt2pushover'),
    ):
        mod.send_pushover(data, 'pushover/alerts')  # must not raise
    assert 'refused' in caplog.text
    assert mock_status.call_args[0][1] is False


# --- publish_status tests ---


def test_publish_status_success(mod):
    with unittest.mock.patch.object(mod, 'mqtt') as mock_mqtt:
        mod.publish_status('pushover/alerts', True)
    mock_mqtt.publish.assert_called_once_with(
        'pushover/alerts/status', json.dumps({'sent': True})
    )


def test_publish_status_failure(mod):
    with unittest.mock.patch.object(mod, 'mqtt') as mock_mqtt:
        mod.publish_status('pushover/alerts', False, "required field 'message' missing")
    payload = json.loads(mock_mqtt.publish.call_args[0][1])
    assert payload == {'sent': False, 'error': "required field 'message' missing"}


# --- on_message tests ---


def test_on_message_json_dict_payload(mod):
    msg = MockMsg(topic='pushover/alerts', payload='{"message": "fire", "priority": 1}')
    with unittest.mock.patch.object(mod, 'send_pushover') as mock_send:
        mod.on_message(msg)
    mock_send.assert_called_once()
    data, topic = mock_send.call_args[0]
    assert data['message'] == 'fire'
    assert data['priority'] == 1
    assert data['token'] == mod.PUSHOVER_TOKEN
    assert data['user'] == mod.PUSHOVER_USER
    assert 'title' not in data
    assert topic == 'pushover/alerts'


def test_on_message_json_missing_message(mod):
    msg = MockMsg(topic='pushover/alerts', payload='{"title": "oops"}')
    with (
        unittest.mock.patch.object(mod, 'send_pushover') as mock_send,
        unittest.mock.patch.object(mod, 'publish_status') as mock_status,
    ):
        mod.on_message(msg)
    mock_send.assert_not_called()
    mock_status.assert_called_once_with(
        'pushover/alerts', False, "required field 'message' missing"
    )


def test_on_message_json_non_dict_payload(mod):
    msg = MockMsg(topic='pushover/alerts', payload='["not", "a", "dict"]')
    with unittest.mock.patch.object(mod, 'send_pushover') as mock_send:
        mod.on_message(msg)
    mock_send.assert_called_once()
    data, topic = mock_send.call_args[0]
    assert data['message'] == '["not", "a", "dict"]'
    assert data['title'] == 'Alerts'


def test_on_message_plain_text_with_subtopic(mod):
    msg = MockMsg(topic='pushover/front_door/motion', payload='motion detected')
    with unittest.mock.patch.object(mod, 'send_pushover') as mock_send:
        mod.on_message(msg)
    data, topic = mock_send.call_args[0]
    assert data['message'] == 'motion detected'
    assert data['title'] == 'Front Door Motion'


def test_on_message_plain_text_without_subtopic(mod):
    msg = MockMsg(topic='pushover/', payload='bare message')
    with unittest.mock.patch.object(mod, 'send_pushover') as mock_send:
        mod.on_message(msg)
    data, topic = mock_send.call_args[0]
    assert data['message'] == 'bare message'
    assert 'title' not in data


@pytest.mark.parametrize(
    'topic,expected_title',
    [
        ('pushover/front_door', 'Front Door'),
        ('pushover/smoke_alarm', 'Smoke Alarm'),
        ('pushover/a/b/c', 'A B C'),
        ('pushover/already_Title_Case', 'Already Title Case'),
    ],
)
def test_on_message_subtopic_formatting(mod, topic, expected_title):
    msg = MockMsg(topic=topic, payload='test')
    with unittest.mock.patch.object(mod, 'send_pushover') as mock_send:
        mod.on_message(msg)
    data, _ = mock_send.call_args[0]
    assert data['title'] == expected_title
