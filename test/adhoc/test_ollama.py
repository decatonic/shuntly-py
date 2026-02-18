import io
import json

import pytest

try:
    import ollama
except ImportError:
    pytest.skip("ollama not available", allow_module_level=True)

from shuntly import SinkStream, shunt

_MODEL = 'qwen2.5:0.5b'  # Small model for testing

# Skip tests if Ollama isn't running or model isn't available
def _check_ollama_available():
    try:
        available_models = ollama.list()
        model_names = [model['name'] for model in available_models.get('models', [])]
        return any(_MODEL in name for name in model_names)
    except:
        return False

pytestmark = pytest.mark.skipif(
    not _check_ollama_available(), 
    reason=f'Ollama not running or model {_MODEL} not available'
)


def test_wrap_captures_chat_record():
    buf = io.StringIO()
    client = shunt(ollama, SinkStream(buf))

    response = client.chat(
        model=_MODEL,
        messages=[{'role': 'user', 'content': 'Reply with just the word: pong'}],
    )

    # Verify the response has the expected structure
    assert 'message' in response
    assert 'content' in response['message']
    
    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'ollama'
    assert record['method'] == 'chat'
    assert record['request']['model'] == _MODEL
    assert record['request']['messages'][0]['content'] == 'Reply with just the word: pong'
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert 'message' in record['response']


def test_wrap_captures_generate_record():
    buf = io.StringIO()
    client = shunt(ollama, SinkStream(buf))

    response = client.generate(
        model=_MODEL,
        prompt='Reply with just the word: ping',
    )

    # Verify the response has the expected structure
    assert 'response' in response
    
    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'ollama'
    assert record['method'] == 'generate'
    assert record['request']['model'] == _MODEL
    assert record['request']['prompt'] == 'Reply with just the word: ping'
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert 'response' in record['response']


def test_wrap_captures_streaming_chat():
    """Test streaming chat responses are captured correctly."""
    buf = io.StringIO()
    client = shunt(ollama, SinkStream(buf))

    chunks = []
    stream = client.chat(
        model=_MODEL,
        messages=[{'role': 'user', 'content': 'Count to 3'}],
        stream=True,
    )

    for chunk in stream:
        chunks.append(chunk)

    # Verify we got streaming chunks
    assert len(chunks) > 0
    assert all('message' in chunk for chunk in chunks)

    record = json.loads(buf.getvalue().strip())

    assert record['client'] == 'ollama'
    assert record['method'] == 'chat'
    assert record['request']['model'] == _MODEL
    assert record['request']['stream'] is True
    assert record['error'] is None
    assert record['duration_ms'] > 0
    # Response should be the accumulated chunks
    assert record['response'] == chunks