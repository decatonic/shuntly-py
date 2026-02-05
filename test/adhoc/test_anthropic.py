import io
import json
import os

import anthropic
import pytest

from shuntly import Shuntly, SinkStream

_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
_MODEL = "claude-3-haiku-20240307"

pytestmark = pytest.mark.skipif(not _API_KEY, reason="ANTHROPIC_API_KEY not set")


def test_wrap_captures_record():
    buf = io.StringIO()
    # alt_client = anthropic.Anthropic(api_key=_API_KEY)

    client = Shuntly.shunt(anthropic.Anthropic(api_key=_API_KEY), SinkStream(buf))

    resp = client.messages.create(
        model=_MODEL,
        max_tokens=32,
        messages=[{"role": "user", "content": "Reply with the single word: pong"}],
    )

    # response came through unmodified
    assert resp.id.startswith("msg_")
    assert resp.model.startswith("claude")
    assert resp.stop_reason in ("end_turn", "max_tokens")
    text = resp.content[0].text.lower()
    assert "pong" in text

    # record was captured
    record = json.loads(buf.getvalue().strip())
    # import ipdb; ipdb.set_trace()

    assert record["client"] == "anthropic.Anthropic"
    assert record["method"] == "messages.create"
    assert record["request"]["model"] == _MODEL
    assert record["request"]["max_tokens"] == 32
    assert record["error"] is None
    assert record["duration_ms"] > 0
    assert record["response"]["id"].startswith("msg_")


# def test_wrap_captures_error():
#     buf = io.StringIO()
#     client = anthropic.Anthropic(api_key="sk-ant-INVALID")
#     Shuntly.shunt(client, SinkStream(buf))

#     with pytest.raises(anthropic.AuthenticationError):
#         client.messages.create(
#             model=_MODEL,
#             max_tokens=1,
#             messages=[{"role": "user", "content": "hi"}],
#         )

#     record = json.loads(buf.getvalue().strip())
#     assert record["error"] is not None
#     assert "AuthenticationError" in record["error"]
#     assert record["response"] is None
