"""The sole owner of generated reST syntax, escaping, and layout."""

import re
from dataclasses import dataclass
from string import punctuation
from typing import List, Sequence

from ._document import (
    Block, CodeBlockNode, DefinitionList, HardBreak, Inline, Link, ListBlock,
    Literal, Note, OpaqueInline, Paragraph, PreservedBlock, Role, Rubric,
    SoftBreak, Style, Table, Text,
)


@dataclass
class _Token:
    text: str
    markup: bool = False


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", r"\`")


def _prose(value: str) -> str:
    return re.sub(r"\B_\b", r"\\_", value)


def render_inlines(nodes: Sequence[Inline]) -> str:
    tokens: List[_Token] = []
    after_break = False
    for node in nodes:
        if isinstance(node, Text):
            text = _prose(node.value)
            if after_break:
                text = text.lstrip(" \t")
            token = _Token(text)
        elif isinstance(node, Literal):
            if not node.value:
                continue
            text = (
                ":literal:`" + _label(node.value) + "`"
                if "``" in node.value else "``" + node.value + "``"
            )
            token = _Token(text, True)
        elif isinstance(node, Link):
            token = _Token(f"`{_label(node.label)} <{node.target}>`__", True)
        elif isinstance(node, Role):
            token = _Token(f":{node.name}:`{_label(node.target)}`", True)
        elif isinstance(node, Style):
            value = "".join(child.value for child in node.children if isinstance(child, Text))
            if node.kind in {"sup", "sub"}:
                text = f":{node.kind}:`{_label(value)}`"
            elif "\n" in value:
                text = f":{node.kind}:`{_label(value)}`"
            else:
                marker = "**" if node.kind == "strong" else "*"
                text = marker + _prose(value) + marker
            token = _Token(text, True)
        elif isinstance(node, OpaqueInline):
            token = _Token(node.source)
        else:
            token = _Token("\n")
        after_break = isinstance(node, (HardBreak, SoftBreak))
        if token.text:
            tokens.append(token)

    result: List[str] = []
    for index, token in enumerate(tokens):
        if result:
            before = result[-1][-1]
            after = token.text[0]
            previous = tokens[index - 1]
            needs_start = token.markup and not before.isspace() and before not in "\"'(<[{-/:"
            needs_end = previous.markup and not after.isspace() and after not in "\"')>]}-/:.,;!?\\"
            if needs_start or needs_end:
                result.append("\\ ")
        result.append(token.text)
    return "".join(result)


@dataclass
class _Line:
    text: str
    payload: bool = False


def _indent(lines: Sequence[_Line], width: int) -> List[_Line]:
    return [_Line(" " * width + line.text if line.text or line.payload else "", line.payload)
            for line in lines]


def _blocks(blocks: Sequence[Block]) -> List[_Line]:
    result: List[_Line] = []
    for block in blocks:
        lines = _block(block)
        if not lines:
            continue
        if result:
            result.append(_Line(""))
        result.extend(lines)
    return result


def _block(block: Block) -> List[_Line]:
    if isinstance(block, Paragraph):
        text = render_inlines(block.inlines)
        lines = [_Line(line.rstrip()) for line in text.split("\n")]
        while lines and not lines[0].text:
            lines.pop(0)
        while lines and not lines[-1].text:
            lines.pop()
        return lines
    if isinstance(block, CodeBlockNode):
        if not block.text:
            return []
        directive = ".. code-block:: " + block.language if block.language else "::"
        return [_Line(directive), _Line("")] + [
            _Line("   " + line, True) for line in block.text.split("\n")
        ]
    if isinstance(block, Note):
        body = _blocks(block.blocks)
        if not body:
            return [_Line(".. note::")]
        first = block.blocks[0]
        inline_header = isinstance(first, Paragraph) and not first.explicit
        raw_header = isinstance(first, PreservedBlock) and not any(
            isinstance(part, CodeBlockNode) for part in first.parts
        )
        if inline_header or raw_header:
            return [_Line(".. note:: " + body[0].text, body[0].payload)] + _indent(body[1:], 3)
        return [_Line(".. note::"), _Line("")] + _indent(body, 3)
    if isinstance(block, ListBlock):
        marker = "#. " if block.ordered else "- "
        result = []
        previous_size = 0
        for item in block.items:
            lines = _blocks(item.blocks) or [_Line("")]
            if result and previous_size == 1:
                result.append(_Line(""))
            result.append(_Line(marker + lines[0].text, lines[0].payload))
            result.extend(_indent(lines[1:], len(marker)))
            previous_size = len(lines)
        return result
    if isinstance(block, DefinitionList):
        result = []
        for entry in block.entries:
            result.extend(_Line(line) for line in render_inlines(entry.term).split("\n"))
            result.extend(_indent(_blocks(entry.blocks), 3))
        return result
    if isinstance(block, Table):
        caption = render_inlines(block.caption)
        result = [_Line(".. list-table::" + (" " + caption if caption else ""))]
        if block.header_rows:
            result.append(_Line(f"   :header-rows: {block.header_rows}"))
        result.append(_Line(""))
        for row in block.rows:
            for index, cell in enumerate(row):
                lines = _blocks(cell) or [_Line("")]
                marker = "   * -" if index == 0 else "     -"
                first_text = lines[0].text
                if len(lines) == 1 and first_text and len(set(first_text)) == 1 and first_text[0] in punctuation:
                    first_text = "\\" + first_text
                result.append(_Line(marker + (" " + first_text if first_text else ""), lines[0].payload))
                result.extend(_indent(lines[1:], 7))
        return result
    if isinstance(block, Rubric):
        return [_Line(".. rubric:: " + " ".join(render_inlines(block.inlines).split()))]
    if isinstance(block, PreservedBlock):
        # Raw source and semantic atoms remain distinct until this final write.
        result = ""
        for part in block.parts:
            if isinstance(part, str):
                result += part
            elif isinstance(part, CodeBlockNode):
                code = "\n".join(line.text for line in _block(part))
                if code:
                    result += "\n\n" + code + "\n\n"
            else:
                result += render_inlines([part])
        return [_Line(line, True) for line in result.split("\n")]
    raise TypeError(f"Unknown document block: {block!r}")


def render_blocks(blocks: Sequence[Block]) -> str:
    """Serialize layout without trimming or reparsing literal payload lines."""
    return "\n".join(line.text for line in _blocks(blocks))
