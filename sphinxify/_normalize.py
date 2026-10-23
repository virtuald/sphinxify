"""Lower source structures to combinations representable by reStructuredText."""

from typing import List, Optional, Sequence

from ._document import Inline, Link, Literal, OpaqueInline, Role, Style, Text


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
