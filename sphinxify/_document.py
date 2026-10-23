"""Internal document nodes. Values are content, never generated reST."""

from dataclasses import dataclass
from typing import List, Union


@dataclass
class Text:
    value: str


@dataclass
class Literal:
    value: str


@dataclass
class Link:
    label: str
    target: str


@dataclass
class Role:
    name: str
    target: str


@dataclass
class OpaqueInline:
    source: str


@dataclass
class SoftBreak:
    pass


@dataclass
class HardBreak:
    pass


@dataclass
class Style:
    kind: str
    children: List["Inline"]


Inline = Union[Text, Literal, Link, Role, OpaqueInline, SoftBreak, HardBreak, Style]
