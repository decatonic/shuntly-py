from shuntly.core import shunt
from shuntly.record import ShuntlyRecord
from shuntly.sinks import Sink, SinkFile, SinkMany, SinkPipe, SinkS3, SinkStream

__all__ = [
    'shunt',
    'ShuntlyRecord',
    'Sink',
    'SinkFile',
    'SinkMany',
    'SinkPipe',
    'SinkS3',
    'SinkStream',
]
