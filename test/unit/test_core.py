import io
import json

import pytest

from shuntly import shunt, SinkStream

# ------------------------------------------------------------------------------
# anthropic


class _Messages:
    def create(self, **kwargs):
        return {'id': 'msg_fake', 'content': 'hello'}

    def stream(self, **kwargs):
        return {'id': 'msg_fake', 'content': 'hello'}


class _MockAnthropicClient:
    def __init__(self):
        self.messages = _Messages()


# Make it look like anthropic.Anthropic to the registry
_MockAnthropicClient.__module__ = 'anthropic'
_MockAnthropicClient.__qualname__ = 'Anthropic'


# ------------------------------------------------------------------------------
# openai


class _Completions:
    def create(self, **kwargs):
        return {'id': 'chatcmpl_fake', 'choices': []}


class _Chat:
    def __init__(self):
        self.completions = _Completions()


class _MockOpenAIClient:
    def __init__(self):
        self.chat = _Chat()


_MockOpenAIClient.__module__ = 'openai'
_MockOpenAIClient.__qualname__ = 'OpenAI'


# ------------------------------------------------------------------------------
class TestWrapAnthropic:
    def test_returns_same_object(self):
        buf = io.StringIO()
        client = _MockAnthropicClient()
        result = shunt(client, SinkStream(buf))
        assert result is client

    def test_records_call(self):
        buf = io.StringIO()
        client = shunt(_MockAnthropicClient(), SinkStream(buf))
        resp = client.messages.create(model='claude-3', max_tokens=100)
        assert resp['id'] == 'msg_fake'

        data = json.loads(buf.getvalue().strip())
        assert data['client'] == 'anthropic.Anthropic'
        assert data['method'] == 'messages.create'
        assert data['request']['model'] == 'claude-3'
        assert data['response']['id'] == 'msg_fake'
        assert data['error'] is None
        assert data['duration_ms'] >= 0

    def test_records_error(self):
        buf = io.StringIO()
        client = _MockAnthropicClient()

        def failing_create(**kwargs):
            raise RuntimeError('API down')

        client.messages.create = failing_create
        shunt(client, SinkStream(buf))

        with pytest.raises(RuntimeError, match='API down'):
            client.messages.create(model='x')

        data = json.loads(buf.getvalue().strip())
        assert data['error'] == 'RuntimeError: API down'
        assert data['response'] is None


class TestWrapOpenAI:
    def test_records_call(self):
        buf = io.StringIO()
        client = shunt(_MockOpenAIClient(), SinkStream(buf))
        resp = client.chat.completions.create(model='gpt-4')
        assert resp['id'] == 'chatcmpl_fake'

        data = json.loads(buf.getvalue().strip())
        assert data['client'] == 'openai.OpenAI'
        assert data['method'] == 'chat.completions.create'


class TestWrapCustomMethods:
    def test_explicit_methods(self):
        buf = io.StringIO()

        class MyClient:
            class inner:
                @staticmethod
                def call(**kwargs):
                    return 'ok'

        client = MyClient()
        shunt(client, SinkStream(buf), methods=['inner.call'])
        result = client.inner.call(prompt='hi')
        assert result == 'ok'

        data = json.loads(buf.getvalue().strip())
        assert data['method'] == 'inner.call'
        assert data['request']['prompt'] == 'hi'


class TestWrapUnknownClient:
    def test_raises_without_methods(self):
        class Unknown:
            pass

        with pytest.raises(ValueError, match='Unknown client'):
            shunt(Unknown(), SinkStream(io.StringIO()))
