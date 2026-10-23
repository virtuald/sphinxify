import pytest
from docutils import nodes
from docutils.core import publish_doctree

from sphinxify._document import (
    HardBreak,
    Link,
    Literal,
    OpaqueInline,
    Role,
    Style,
    Text,
)
from sphinxify._normalize import normalize_inlines
from sphinxify._rst import render_inlines


@pytest.mark.parametrize(
    "source, expected",
    [
        ([Style("strong", [Literal("foo")])], "``foo``"),
        ([Style("emphasis", [Style("strong", [Text("word")])])], "**word**"),
        ([Style("strong", [Style("strong", [Text("word")])])], "**word**"),
        ([Style("sub", [Style("sup", [Text("x")])])], ":sup:`x`"),
        ([Style("sup", [Literal("foo")])], "``foo``"),
        ([Style("strong", [Role("meth", ".run")])], ":meth:`.run`"),
        ([Style("strong", [OpaqueInline("<T>")])], "<T>"),
        (
            [Text("pre"), Link("`foo`", "https://example.org"), Text("post")],
            r"pre\ `\`foo\` <https://example.org>`__\ post",
        ),
        ([Literal("foo"), Literal("bar")], r"``foo``\ ``bar``"),
        (
            [Text("("), Literal("foo"), Text("), "), Literal("bar"), Text(".")],
            "(``foo``), ``bar``.",
        ),
        ([Text("first"), HardBreak(), Text(" next")], "first\nnext"),
        ([Style("strong", [Text("a"), Style("emphasis", [Text("b")])])], "**ab**"),
        ([Text("trailing_ &")], r"trailing\_ &"),
    ],
)
def test_normalized_inline_output(source, expected):
    assert render_inlines(normalize_inlines(source)) == expected


def test_atomic_semantics_survive_formatting():
    result = render_inlines(
        normalize_inlines(
            [
                Style("emphasis", [Link("`foo`", "https://example.org")]),
                Text(" and "),
                Style("strong", [Literal("bar")]),
            ]
        )
    )
    assert result == r"`\`foo\` <https://example.org>`__ and ``bar``"
    tree = publish_doctree(result, settings_overrides={"halt_level": 2})
    assert [n.astext() for n in tree.findall(nodes.reference)] == ["`foo`"]
    assert [n.astext() for n in tree.findall(nodes.literal)] == ["bar"]
