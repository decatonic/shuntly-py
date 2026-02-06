# Shuntly

A lightweight wiretap for LLM SDKs: capture all requests and responses with a single line of code.

Shuntly wraps LLM SDKs to record every request and response as JSON. Calling `shunt()` wraps and returns a client with its original interface and types preserved, permitting consistent IDE autocomplete and type checking. Shuntly provides a collection of configurable "sinks" to write records to stderr, files, named pipes, or any combination.

While debugging LLM tooling, maybe you want to see exactly what is being sent and returned. When launching an agent, maybe you want to record every call to the LLM. Shuntly can capture it all without TLS interception, a web-based platform, or complicated logging infrastructure.


## Install

```
pip install shuntly
```

## Integrate

Given an LLM SDK (e.g. [`anthropic`](https://pypi.org/project/anthropic), [`openai`](https://pypi.org/project/openai]), [`google-genai`](https://pypi.org/project/google-genai)), simply call `shunt()` with the instantiated SDK class. The returned object has the same type and interface.

```python
from anthropic import Anthropic
from shuntly import shunt

# Without providing a sink Shuntly output goes to stderr
client = shunt(Anthropic(api_key=API_KEY))

# Now use the client as before
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
```

Each call to `messages.create()` writes a complete JSON record:

```json
{
  "timestamp": "2025-01-15T12:00:00+00:00",
  "hostname": "dev1",
  "user": "alice",
  "pid": 42,
  "client": "anthropic.Anthropic",
  "method": "messages.create",
  "request": {"model": "claude-sonnet-4-20250514", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hello"}]},
  "response": {"id": "msg_...", "content": [{"type": "text", "text": "Hi!"}]},
  "duration_ms": 823.4,
  "error": null
}
```

## View

Shuntly JSON output can be streamed or read with a JSON viewer like [`fx`](https://fx.wtf). These tools provide JSON syntax highlighting and collapsible sections.


### View Realtime Shuntly from `stderr`

Shuntly output, by default, goes to `stderr`; this is equivalent to providing a `SinkStream` to `shunt()`:

```python
from shuntly import shunt, SinkStream
client = shunt(Anthropic(api_key=API_KEY), SinkStream())
```

Given a `command`, you can view Shuntly `stderr` output in `fx` with the following:

```bash
$ command 2>&1 >/dev/null | fx
```


### View Realtime Shuntly via a Pipe

To view Shuntly output via a named pipe in another terminal, the `SinkPipe` sink can be used. First, name the pipe when providing `SinkPipe` to `shunt()`:

```python
from shuntly import shunt, SinkPipe
client = shunt(Anthropic(api_key=API_KEY), SinkPipe('/tmp/shuntly.fifo'))
```

Then, in a terminal to view Shuntly output, create the named pipe and provide it to `fx`

```bash
$ mkfifo /tmp/shuntly.fifo; fx < /tmp/shuntly.fifo
```

Then, in another terminal, launch your command.


### View Shuntly from a File

To store Shuntly output in a file, the `SinkFile` sink can be used. Name the file when providing `SinkFile` to `shunt()`:

```python
from shuntly import shunt, SinkFile
client = shunt(Anthropic(api_key=API_KEY), SinkFile('/tmp/shuntly.jsonl'))
```

Then, after your command is complete, view the file:

```bash
$ fx /tmp/shuntly.jsonl
```

### Send Shuntly Output to Multiple Sinks

Using `SinkMany`, multiple sinks can be written to simultaneously.

```python
from shuntly import shunt, SinkStream, SinkFile, SinkMany

client = shunt(Anthropic(), SinkMany([
    SinkStream(),
    SinkFile('/tmp/shuntly.jsonl'),
]))
```

### Custom Sinks

Custom sinks can be implemented by subclassing `Sink` and implementing `write()`:

```python
from shuntly import Sink, ShuntlyRecord

class SinkPrint(Sink):
    def write(self, record: ShuntlyRecord) -> None:
        print(record.client, record.method, record.duration_ms)
```


## Supported SDKs

Shuntly presently handles these clients:

| Client | Package | Methods |
|--------|---------|---------|
| `anthropic.Anthropic` | [`PyPI`](https://pypi.org/project/anthropic) | `messages.create`, `messages.stream` |
| `openai.OpenAI` | [`PyPI`](https://pypi.org/project/openapi) | `chat.completions.create` |
| `google.genai.Client` | [`PyPI`](https://pypi.org/project/google-genai) | `models.generate_content` |

For anything else, method paths can be explicitly provided:

```python
client = shunt(my_client, methods=["chat.send", "embeddings.create"])
```

## What is New in Shuntly


### 0.4.0

Renamed `Record` to `ShuntlyRecord`.

Export `shunt()` without `Shuntly` class.


### 0.2.0

Fully tested and integrated support for OpenAI and Google SDKs.

`SinkPipe` is now interruptible.


### 0.1.0

Initial release.


