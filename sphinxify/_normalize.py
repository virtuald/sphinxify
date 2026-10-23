"""Lower source structures to combinations representable by reStructuredText."""

import re
from typing import List, Optional, Sequence

from ._html import _INLINE, _unescape

from ._document import (
    Block, CodeBlockNode, DefinitionEntry, DefinitionList, HardBreak, HtmlElement,
    HtmlNote, HtmlText, Inline, Link, ListBlock, ListItem, Literal, Note,
    OpaqueInline, Paragraph, ParsedNode, ParsedSection, PreservedBlock, Role,
    Rubric, Style, Table, Text,
)


def _atomic(node: Inline) -> bool:
    if isinstance(node, Style):
        return any(_atomic(child) for child in node.children)
    return isinstance(node, (Literal, Link, Role, OpaqueInline))


def normalize_inlines(nodes: Sequence[Inline]) -> List[Inline]:
    """Flatten styles into runs; never wrap atomic markup in other markup."""
    result: List[Inline] = []

    def append(node: Inline, style: Optional[str]):
        if isinstance(node, Text) and not node.value:
            return
        if style and isinstance(node, Text):
            if result and isinstance(result[-1], Style) and result[-1].kind == style:
                previous = result[-1].children[-1]
                if isinstance(previous, Text):
                    previous.value += node.value
                    return
            result.append(Style(style, [Text(node.value)]))
        elif isinstance(node, Text) and result and isinstance(result[-1], Text):
            result[-1].value += node.value
        else:
            result.append(Text(node.value) if isinstance(node, Text) else node)

    def visit(children: Sequence[Inline], style: Optional[str] = None):
        for child in children:
            if isinstance(child, Style):
                if _atomic(child):
                    visit(child.children)
                else:
                    active = child.kind
                    if style in {"sub", "sup"} and active not in {"sub", "sup"}:
                        active = style
                    elif style == "strong" and active == "emphasis":
                        active = style
                    visit(child.children, active)
            else:
                append(child, style)

    visit(nodes)
    return result


def _raw_parts(node: ParsedNode):
    if isinstance(node, HtmlText):
        return [node.source]
    if isinstance(node, HtmlElement):
        parts = [node.opening]
        for child in node.children:
            parts.extend(_raw_parts(child))
        parts.append(node.closing)
        return parts
    if isinstance(node, HtmlNote):
        parts = []
        for child in node.children:
            parts.extend(_raw_parts(child))
        return parts
    return [node]


def _raw_text(node: ParsedNode) -> str:
    result = []
    for part in _raw_parts(node):
        if isinstance(part, str):
            result.append(part)
        elif isinstance(part, Literal):
            result.append(part.source if part.source is not None else part.value)
        elif isinstance(part, OpaqueInline):
            result.append(part.source)
        elif isinstance(part, Role):
            result.append(part.target)
        elif isinstance(part, CodeBlockNode):
            result.append(part.text)
    return "".join(result)


def _plain(node: ParsedNode) -> str:
    if isinstance(node, HtmlText):
        return _unescape(node.source)
    if isinstance(node, HtmlElement):
        if node.tag == "br":
            return " "
        if node.tag in {"code", "tt"}:
            return _unescape("".join(_raw_text(child) for child in node.children))
        return "".join(_plain(child) for child in node.children)
    if isinstance(node, HtmlNote):
        return "".join(_plain(child) for child in node.children)
    return _raw_text(node)


def _inline(node: ParsedNode, in_cell: bool = False) -> List[Inline]:
    if isinstance(node, HtmlText):
        text = _unescape(node.source)
        return [Text(re.sub(r"\s+", " ", text) if in_cell else text)]
    if isinstance(node, (Literal, Role, OpaqueInline)):
        return [node]
    if not isinstance(node, HtmlElement):
        return [OpaqueInline(_raw_text(node))]
    if node.tag == "br":
        return [HardBreak()]
    if not node.closing:
        return [OpaqueInline(_raw_text(node))]
    if node.tag in {"code", "tt"}:
        return [Literal(" ".join(_unescape("".join(_raw_text(c) for c in node.children)).split()))]
    if node.tag == "a" and node.attrs.get("href"):
        return [Link(" ".join(_plain(node).split()), node.attrs["href"])]
    children = [inline for child in node.children for inline in _inline(child, in_cell)]
    if node.tag in _INLINE:
        return [Style(_INLINE[node.tag][1], children)]
    if node.tag in {"sub", "sup"}:
        return [Style(node.tag, children)]
    return children


def _trim_inlines(inlines: List[Inline]) -> List[Inline]:
    inlines = normalize_inlines(inlines)
    while inlines:
        if isinstance(inlines[0], Text):
            inlines[0].value = inlines[0].value.lstrip()
            if inlines[0].value:
                break
        elif not isinstance(inlines[0], HardBreak):
            break
        inlines.pop(0)
    while inlines:
        if isinstance(inlines[-1], Text):
            inlines[-1].value = inlines[-1].value.rstrip()
            if inlines[-1].value:
                break
        elif not isinstance(inlines[-1], HardBreak):
            break
        inlines.pop()
    return inlines


def _lower(children: Sequence[ParsedNode], in_cell: bool = False) -> List[Block]:
    result: List[Block] = []
    pending: List[Inline] = []

    def flush():
        trimmed = _trim_inlines(pending)
        if trimmed:
            result.append(Paragraph(trimmed))
        pending.clear()

    for child in children:
        if isinstance(child, HtmlText):
            # Blank source lines separate prose, never literal payloads.
            chunks = re.split(r"\n[ \t]*\n", child.source)
            for index, chunk in enumerate(chunks):
                if index and not in_cell:
                    flush()
                pending.extend(_inline(HtmlText(chunk), in_cell))
        elif isinstance(child, HtmlNote):
            flush()
            result.append(Note(_lower(child.children, in_cell)))
        elif isinstance(child, CodeBlockNode):
            flush()
            result.append(child)
        elif isinstance(child, HtmlElement) and child.preserve:
            flush()
            result.append(PreservedBlock(_raw_parts(child)))
        elif isinstance(child, HtmlElement) and child.tag in {"p", "ul", "ol", "dl", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"}:
            flush()
            if child.tag == "p":
                blocks = _lower(child.children, in_cell)
                for block in blocks:
                    if isinstance(block, Paragraph):
                        block.explicit = True
                result.extend(blocks)
            elif child.tag in {"ul", "ol"}:
                result.extend(_list(child, in_cell))
            elif child.tag == "dl":
                result.extend(_definitions(child, in_cell))
            elif child.tag == "li":
                result.append(ListBlock(False, [ListItem(_lower(child.children, in_cell))]))
            elif child.tag == "table":
                result.append(_table(child))
            else:
                result.append(Rubric(normalize_inlines([i for c in child.children for i in _inline(c, True)])))
        else:
            pending.extend(_inline(child, in_cell))
    flush()
    return result


def _list(element: HtmlElement, in_cell: bool) -> List[Block]:
    result: List[Block] = []
    items: List[ListItem] = []
    loose: List[ParsedNode] = []

    def flush_items():
        if items:
            result.append(ListBlock(element.tag == "ol", items[:]))
            items.clear()

    def flush_loose():
        blocks = _lower(loose, in_cell)
        if blocks:
            flush_items()
            result.extend(blocks)
        loose.clear()

    for child in element.children:
        if isinstance(child, HtmlElement) and child.tag == "li":
            flush_loose()
            items.append(ListItem(_lower(child.children, in_cell)))
        else:
            loose.append(child)
    flush_loose()
    flush_items()
    return result


def _definitions(element: HtmlElement, in_cell: bool) -> List[Block]:
    result: List[Block] = []
    entries: List[DefinitionEntry] = []
    loose: List[ParsedNode] = []
    term: Optional[List[Inline]] = None

    def flush_entries():
        nonlocal term
        if entries:
            result.append(DefinitionList(entries[:]))
            entries.clear()
        if term is not None:
            result.append(Paragraph(term))
            term = None

    def flush_loose():
        blocks = _lower(loose, in_cell)
        if blocks:
            flush_entries()
            result.extend(blocks)
        loose.clear()

    for child in element.children:
        if isinstance(child, HtmlElement) and child.tag in {"dt", "dd"}:
            flush_loose()
            if child.tag == "dt":
                if term is not None:
                    flush_entries()
                term = _trim_inlines([i for c in child.children for i in _inline(c, in_cell)])
            elif term is not None:
                entries.append(DefinitionEntry(term, _lower(child.children, in_cell)))
                term = None
            elif entries:
                entries[-1].blocks.extend(_lower(child.children, in_cell))
            else:
                result.extend(_lower(child.children, in_cell))
        else:
            loose.append(child)
    flush_loose()
    flush_entries()
    return result


def _table(element: HtmlElement) -> Block:
    rows: List[List[HtmlElement]] = []
    caption: List[Inline] = []

    def collect(parent: HtmlElement) -> bool:
        nonlocal caption
        allowed = {"tr", "thead", "tbody", "tfoot", "caption"} if parent.tag == "table" else {"tr"}
        for child in parent.children:
            if isinstance(child, HtmlText) and not child.source.strip():
                continue
            if not isinstance(child, HtmlElement) or child.tag not in allowed:
                return False
            if child.tag == "tr":
                row = []
                for cell in child.children:
                    if isinstance(cell, HtmlText) and not cell.source.strip():
                        continue
                    if not isinstance(cell, HtmlElement) or cell.tag not in {"td", "th"}:
                        return False
                    row.append(cell)
                rows.append(row)
            elif child.tag == "caption":
                caption = normalize_inlines([i for c in child.children for i in _inline(c, True)])
            elif not collect(child):
                return False
        return True

    def unsupported(parent: HtmlElement) -> bool:
        return any(isinstance(child, HtmlElement) and (
            child.tag == "table" or "colspan" in child.attrs or "rowspan" in child.attrs or unsupported(child)
        ) for child in parent.children)

    if (not element.closing or not collect(element) or unsupported(element) or not rows
            or not rows[0] or any(len(row) != len(rows[0]) for row in rows)):
        return PreservedBlock(_raw_parts(element))
    headers = 0
    for row in rows:
        if not all(cell.tag == "th" for cell in row):
            break
        headers += 1
    if headers == len(rows):
        return PreservedBlock(_raw_parts(element))
    return Table([[_lower(cell.children, True) for cell in row] for row in rows], headers, caption)


def normalize_html(section: ParsedSection) -> List[Block]:
    return _lower(section.children)
