# shuntly

A lightweight wiretap for LLM SDKs: capture all requests and responses with a single line of code.

Shuntly wraps LLM SDKs to record every request and response as JSON. Calling `Shuntly.shunt()` patches and returns a client with its original interface and types preserved, permitting consistent IDE autocomplete and type checking.

Bring your own LLM SDK (Anthropic, OpenAPI), and Shuntly provides "sinks" to write records to stderr, files, named pipes, or any combination.

## Install

```
pip install shuntly
```

## Usage

```python
from anthropic import Anthropic
from shuntly import Shuntly

# By default, all calls and responses are output to stderr
client = Shuntly.shunt(Anthropic())

# Use the client normally
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
```

Each call writes JSON like:

```json
{"timestamp": "2025-01-15T12:00:00+00:00", "hostname": "dev1", "user": "alice", "pid": 42, "client": "anthropic.Anthropic", "method": "messages.create", "request": {"model": "claude-sonnet-4-20250514", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hello"}]}, "response": {"id": "msg_...", "content": [{"type": "text", "text": "Hi!"}]}, "duration_ms": 823.4, "error": null}
```

## Sinks

```python
from shuntly import Shuntly, SinkStream, SinkFile, SinkPipe, SinkMany

# stderr (default when no sink is passed)
client = Shuntly.shunt(Anthropic(), SinkStream())

# Append JSON lines to a file
client = Shuntly.shunt(Anthropic(), SinkFile("llm.jsonl"))

# Write to a named pipe (creates it if it doesn't exist)
client = Shuntly.shunt(Anthropic(), SinkPipe("/tmp/llm.pipe"))

# Fan out to multiple destinations
client = Shuntly.shunt(Anthropic(), SinkMany([
    SinkStream(),
    SinkFile("llm.jsonl"),
]))
```

## Supported clients

Shuntly handles these clients out of the box:

| Client | Methods |
|--------|---------|
| `anthropic.Anthropic` | `messages.create`, `messages.stream` |
| `openai.OpenAI` | `chat.completions.create` |

For anything else, pass the method paths explicitly:

```python
client = Shuntly.shunt(my_client, methods=["chat.send", "embeddings.create"])
```

## Custom sinks

Subclass `Sink` and implement `write`:

```python
from shuntly import Sink, Record

class SinkPrint(Sink):
    def write(self, record: Record) -> None:
        print(record.client, record.method, record.duration_ms)
```
