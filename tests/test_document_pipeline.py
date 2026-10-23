import pytest
from docutils import nodes
from docutils.core import publish_doctree

from sphinxify import CodeBlockReplacement, Doc, Param, process_doc


@pytest.mark.parametrize(
    "source, expected",
    [
        ("@note Intro<br> next\nmore", ".. note:: Intro\n   next\n   more"),
        ("<b>{@code foo}</b>", "``foo``"),
        ("<em><strong>word</strong></em>", "**word**"),
        ("<sup><code>foo</code></sup>", "``foo``"),
    ],
)
def test_structural_regressions(source, expected):
    result = process_doc(source)
    assert result == expected
    tree = publish_doctree(result, settings_overrides={"halt_level": 2})
    assert not list(tree.findall(nodes.system_message))


@pytest.mark.parametrize(
    "prefix, expected",
    [
        (
            "@param x Value.",
            "\n\n:param x: Value.\n          \n          ::\n          \n             line  \n             last \t\n             \n             ",
        ),
        (
            "@return Value.",
            "\n\n:returns: Value.\n          \n          ::\n          \n             line  \n             last \t\n             \n             ",
        ),
        (
            "@deprecated Value.",
            "\n\n:deprecated: Value.\n             \n             ::\n             \n                line  \n                last \t\n                \n                ",
        ),
    ],
)
def test_final_field_code_payload_is_unchanged(prefix, expected):
    assert (
        process_doc(
            prefix + "\n<pre>original</pre>",
            code_block_transform=lambda block: CodeBlockReplacement(
                "line  \nlast \t\n\n"
            ),
        )
        == expected
    )


def test_manual_document_and_mutable_fields_remain_supported():
    doc = Doc("Description.", [Param("x", ["Value."])], ["Result."])
    doc.params[0].lines.append("Continued.")
    doc.desc = "Changed."
    assert (
        str(doc)
        == "Changed.\n\n:param x: Value.\n          Continued.\n\n:returns: Result."
    )
    doc.remove_param("x")
    assert str(doc) == "Changed.\n\n:returns: Result."
