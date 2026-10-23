"""The sole owner of generated reST syntax, escaping, and layout."""

import re
from dataclasses import dataclass
from typing import List, Sequence

from ._document import (
    HardBreak, Inline, Link, Literal, OpaqueInline, Role, SoftBreak, Style, Text,
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
