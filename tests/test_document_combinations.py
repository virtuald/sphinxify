"""Composition contracts at the public boundary, not renderer-derived snapshots."""

import pytest
from docutils import nodes
from docutils.core import publish_doctree

from sphinxify import CodeBlockReplacement, process_doc

MARKER = "SENTINEL"
ATOMS = [
    ("<code>SENTINEL</code>", nodes.literal),
    ("<tt>SENTINEL</tt>", nodes.literal),
    ("{@code SENTINEL}", nodes.literal),
    ("``SENTINEL``", nodes.literal),
    ('<a href="https://example.org">SENTINEL</a>', nodes.reference),
    (":title-reference:`SENTINEL`", nodes.title_reference),
    ("SENTINEL", None),
]
CONTAINERS = [
    "<p>{body}</p>",
    "@note <p>{body}</p>\n\nOUTSIDE",
    "<ul><li>{body}</li></ul>",
    "<dl><dt>Term</dt><dd>{body}</dd></dl>",
    "<table><tr><td>{body}</td></tr></table>",
]


@pytest.mark.parametrize("outer", [None, "strong", "em", "sub", "sup"])
@pytest.mark.parametrize("inner", [None, "strong", "em", "sub", "sup"])
@pytest.mark.parametrize("atom, expected_type", ATOMS)
@pytest.mark.parametrize("container", CONTAINERS)
@pytest.mark.parametrize("prefix, suffix", [("pre", "post"), ("(", ")")])
def test_inline_composition_semantics(
    outer, inner, atom, expected_type, container, prefix, suffix
):
    body = atom
    for tag in (inner, outer):
        if tag:
            body = f"<{tag}>{body}</{tag}>"
    result = process_doc(container.format(body=prefix + body + suffix))
    assert result.count(MARKER) == 1
    tree = publish_doctree(result, settings_overrides={"halt_level": 2})
    assert not list(tree.findall(nodes.system_message))
    assert prefix + MARKER + suffix in tree.astext()
    if expected_type is not None:
        found = list(tree.findall(expected_type))
        assert len(found) == 1
        assert found[0].astext() == MARKER
    if container.startswith("@note"):
        notes = list(tree.findall(nodes.note))
        assert len(notes) == 1 and MARKER in notes[0].astext()
        outside = [p for p in tree.findall(nodes.paragraph) if p.astext() == "OUTSIDE"]
        assert len(outside) == 1 and isinstance(outside[0].parent, nodes.document)


@pytest.mark.parametrize(
    "source, expected",
    [
        ("<em>before <strong>word</strong> after</em>", "*before* **word** *after*"),
        ("<b> word </b>", "**word**"),
        ("<sup>a<sub>b</sub>c</sup>", r":sup:`a`\ :sub:`b`\ :sup:`c`"),
    ],
)
def test_flat_style_runs_have_valid_boundaries(source, expected):
    result = process_doc(source)
    assert result == expected
    publish_doctree(result, settings_overrides={"halt_level": 2})


@pytest.mark.parametrize("left, right", [("b", "strong"), ("i", "em"), ("code", "tt")])
@pytest.mark.parametrize("container", CONTAINERS)
def test_supported_aliases_are_equivalent(left, right, container):
    assert process_doc(container.format(body=f"<{left}>word</{left}>")) == process_doc(
        container.format(body=f"<{right}>word</{right}>")
    )


@pytest.mark.parametrize("space", ["", " ", "\n"])
def test_list_layout_whitespace_is_not_content(space):
    assert (
        process_doc(f"<ul>{space}<li>one</li>{space}<li>two</li>{space}</ul>")
        == "- one\n\n- two"
    )


@pytest.mark.parametrize(
    "before, after, head, indent, tail",
    [
        ("", "", "::\n\n", "   ", ""),
        ("@note ", "", ".. note::\n\n   ::\n\n", "      ", ""),
        (
            "<ul><li>Before",
            "After</li></ul>",
            "- Before\n\n  ::\n\n",
            "     ",
            "\n\n  After",
        ),
        ("<dl><dt>T</dt><dd>D</dd>", "</dl>", "T\n   D\n\n::\n\n", "   ", ""),
        (
            '<table><tr><td colspan="2">Before',
            "After</td></tr></table>",
            '<table><tr><td colspan="2">Before\n\n::\n\n',
            "   ",
            "\n\nAfter</td></tr></table>",
        ),
    ],
)
@pytest.mark.parametrize(
    "payload",
    [
        "<b>&amp; `tick` @param x\n\tindent  \n\n\nlast \t",
        "sentinel \x00sphinxify-node-0\x00\nend\n\n",
    ],
)
def test_callback_payload_survives_all_layout(
    before, after, head, indent, tail, payload
):
    seen = []

    def transform(block):
        seen.append((block.index, block.text))
        return CodeBlockReplacement(payload)

    result = process_doc(
        before + "<pre>original</pre>" + after, code_block_transform=transform
    )
    assert seen == [(0, "original")]
    assert (
        result == head + "\n".join(indent + line for line in payload.split("\n")) + tail
    )


def test_callback_order_through_fallback_and_note():
    seen = []

    def transform(block):
        seen.append((block.index, block.text))
        return CodeBlockReplacement(f"MARK{block.index}")

    result = process_doc(
        '<table rowspan="2"><tr><td><pre>first</pre></td></tr></table>\n@note <pre>second</pre>',
        code_block_transform=transform,
    )
    assert seen == [(0, "first"), (1, "second")]
    assert result.count("MARK0") == result.count("MARK1") == 1
    assert result.index("MARK0") < result.index("MARK1")
