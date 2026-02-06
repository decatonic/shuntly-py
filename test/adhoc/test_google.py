import io
import json
import os

import pytest
from google import genai

from shuntly import SinkStream, shunt

_API_KEY = os.environ.get('GEMINI_API_KEY')
_MODEL = 'gemini-2.5-flash-lite'

pytestmark = pytest.mark.skipif(not _API_KEY, reason='GEMINI_API_KEY not set')


def test_wrap_captures_record():
    buf = io.StringIO()
    client = genai.Client(api_key=_API_KEY)
    shunt(client, SinkStream(buf), methods=['models.generate_content'])

    resp = client.models.generate_content(
        model=_MODEL,
        contents='Reply with the single word: pong',
    )

    valid = 'pong'
    text = resp.text.lower()
    assert text == valid

    record = json.loads(buf.getvalue().strip())
    assert record['client'] == 'google.genai.client.Client'
    assert record['method'] == 'models.generate_content'
    assert record['request']['model'] == _MODEL
    assert record['error'] is None
    assert record['duration_ms'] > 0
    assert record['response']['candidates'][0]['content']['parts'][0]['text'] == valid
