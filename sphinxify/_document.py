"""Internal document nodes. Values are content, never generated reST."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union


@dataclass
class Text:
    value: str


@dataclass
class Literal:
    value: str
    source: Optional[str] = None


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


@dataclass
class Paragraph:
    inlines: List[Inline]
    explicit: bool = False
    source_break_after: bool = False


@dataclass
class Note:
    blocks: List["Block"]


@dataclass
class CodeBlockNode:
    text: str
    language: Optional[str] = None


@dataclass
class ListItem:
    blocks: List["Block"]


@dataclass
class ListBlock:
    ordered: bool
    items: List[ListItem]


@dataclass
class DefinitionEntry:
    term: List[Inline]
    blocks: List["Block"]


@dataclass
class DefinitionList:
    entries: List[DefinitionEntry]


@dataclass
class Table:
    rows: List[List[List["Block"]]]
    header_rows: int = 0
    caption: List[Inline] = field(default_factory=list)


@dataclass
class Rubric:
    inlines: List[Inline]


@dataclass
class PreservedBlock:
    parts: List[Union[str, Literal, Role, OpaqueInline, CodeBlockNode]]


Block = Union[Paragraph, Note, CodeBlockNode, ListBlock, DefinitionList, Table, Rubric, PreservedBlock]


@dataclass
class SourceText:
    text: str


@dataclass
class EnterNote:
    pass


@dataclass
class ExitNote:
    pass


SourcePart = Union[SourceText, EnterNote, ExitNote, Literal, Role, OpaqueInline, CodeBlockNode]


@dataclass
class SectionSource:
    parts: List[SourcePart] = field(default_factory=list)


@dataclass
class SourceSections:
    desc: SectionSource = field(default_factory=SectionSource)
    params: List[Tuple[str, SectionSource]] = field(default_factory=list)
    returns: Optional[SectionSource] = None
    deprecated: Optional[SectionSource] = None


@dataclass
class HtmlText:
    source: str


@dataclass
class HtmlElement:
    tag: str
    attrs: Dict[str, str]
    children: List["ParsedNode"] = field(default_factory=list)
    opening: str = ""
    closing: str = ""
    preserve: bool = False


@dataclass
class HtmlNote:
    children: List["ParsedNode"] = field(default_factory=list)


ParsedNode = Union[HtmlText, HtmlElement, HtmlNote, Literal, Role, OpaqueInline, CodeBlockNode]


@dataclass
class ParsedSection:
    children: List[ParsedNode] = field(default_factory=list)
