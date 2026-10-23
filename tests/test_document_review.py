"""Independent whole-branch review reproductions."""

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from sphinxify import CodeBlockReplacement, process_doc


def parse(result):
    tree = publish_doctree(result, settings_overrides={"halt_level": 2})
    assert not list(tree.findall(nodes.system_message))
    return tree


@pytest.mark.parametrize(
    "template", ["<code>{value}</code>", "{{@code {value}}}", "``{value}``"]
)
@pytest.mark.parametrize("value", ["a  b", " a b ", "a\nb"])
def test_literal_whitespace_policy_is_shared(template, value):
    result = process_doc("<b>" + template.format(value=value) + "</b>")
    assert result == "``a b``"
    assert [n.astext() for n in parse(result).findall(nodes.literal)] == ["a b"]


@pytest.mark.parametrize(
    "source, expected",
    [
        ("<b> next</b>", "**next**"),
        ("<em> next</em>", "*next*"),
        ("<sup> next</sup>", ":sup:`next`"),
    ],
)
def test_hard_break_suppresses_whitespace_across_nodes(source, expected):
    result = process_doc("@note Intro<br> " + source + "\nmore\n\nOutside")
    assert result == ".. note:: Intro\n   " + expected + "\n   more\n\nOutside"
    tree = parse(result)
    assert next(tree.findall(nodes.note)).astext() == "Intro\nnext\nmore"


def test_note_under_crossing_inline_wrapper_retains_ownership():
    result = process_doc("<b>before\n@note inside\n\noutside</b>")
    assert result == "<b>before\n\n.. note:: inside\n\noutside</b>"
    tree = parse(result)
    assert [n.astext() for n in tree.findall(nodes.note)] == ["inside"]
    assert tree[-1].astext() == "outside</b>"


@pytest.mark.parametrize(
    "prefix, head, indent, tail",
    [
        ("", "<b>before\n\n::\n\n", "   ", "\n\nafter</b>"),
        (
            "@param x Value ",
            "\n\n:param x: Value <b>before\n          \n          ::\n          \n",
            "             ",
            "\n          \n          after</b>",
        ),
    ],
)
def test_callback_block_under_inline_wrapper_retains_identity(
    prefix, head, indent, tail
):
    payload = "PAY  \n\nEND \t\n\n"
    result = process_doc(
        prefix + "<b>before<pre>original</pre>after</b>",
        code_block_transform=lambda block: CodeBlockReplacement(payload),
    )
    assert (
        result == head + "\n".join(indent + line for line in payload.split("\n")) + tail
    )
    assert len(list(parse(result).findall(nodes.literal_block))) == 1


@pytest.mark.parametrize(
    "source, expected, visible, node_type",
    [
        ("&#96;<b><code>x</code></b>&#96;", r"\`\ ``x``\`", "`x`", nodes.literal),
        (
            '&#42;<a href="https://example.org">x</a>&#42;',
            r"\*\ `x <https://example.org>`__\*",
            "*x*",
            nodes.reference,
        ),
    ],
)
def test_entity_delimiters_remain_text_around_markup(
    source, expected, visible, node_type
):
    result = process_doc(source)
    assert result == expected
    tree = parse(result)
    assert tree.astext() == visible
    assert [n.astext() for n in tree.findall(node_type)] == ["x"]


@pytest.mark.parametrize(
    "source, expected",
    [
        ("<code>{@code x}</code>", "``{@code x}``"),
        ("<code>:meth:`.run`</code>", "``:meth:`.run```"),
        ("<code>``x``</code>", r":literal:`\`\`x\`\``"),
        (
            "<code>first\n@note not a note\nlast</code>",
            "``first @note not a note last``",
        ),
        ("{@code first\n@note not a note\nlast}", "``first @note not a note last``"),
        ("<code>@code x @endcode</code>", "``@code x @endcode``"),
        ("<tt><pre>x</pre></tt>", "``<pre>x</pre>``"),
        ("``@code``", "``@code``"),
        (":literal:`@code`", ":literal:`@code`"),
    ],
)
def test_inline_code_is_opaque_before_comment_routing(source, expected):
    seen = []
    result = process_doc(source, code_block_transform=seen.append)
    assert result == expected
    assert seen == []
    tree = parse(result)
    assert len(list(tree.findall(nodes.literal))) == 1
    assert not list(tree.findall(nodes.note))


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            '<a href="https://example.org" title="@code">link</a>',
            "`link <https://example.org>`__",
        ),
        (
            "<!-- @code <pre>not an example</pre> -->",
            "<!-- @code <pre>not an example</pre> -->",
        ),
    ],
)
def test_opaque_html_markup_does_not_contain_block_commands(source, expected):
    seen = []
    assert process_doc(source, code_block_transform=seen.append) == expected
    assert seen == []


@pytest.mark.parametrize(
    "before, after",
    [
        ("<h1>Before", "After</h1>"),
        ("<dl><dt>Before", "After</dt><dd>D</dd></dl>"),
        ("<table><caption>Before", "After</caption><tr><td>X</td></tr></table>"),
    ],
)
def test_block_atoms_in_inline_only_fields_use_lossless_fallback(before, after):
    result = process_doc(
        before + "<pre>original</pre>" + after,
        code_block_transform=lambda block: CodeBlockReplacement("PAY  \nEND \t"),
    )
    assert result == before + "\n\n::\n\n   PAY  \n   END \t\n\n" + after
    assert len(list(parse(result).findall(nodes.literal_block))) == 1


def test_note_inside_fallback_table_retains_ownership():
    result = process_doc(
        '<table><tr><td colspan="2">before\n@note inside\n\noutside</td></tr></table>'
    )
    assert (
        result
        == '<table><tr><td colspan="2">before\n\n.. note:: inside\n\noutside</td></tr></table>'
    )
    assert [n.astext() for n in parse(result).findall(nodes.note)] == ["inside"]


def test_duplicate_table_captions_fall_back_without_content_loss():
    source = (
        "<table><caption>A</caption><caption>B</caption><tr><td>X</td></tr></table>"
    )
    assert process_doc(source) == source
