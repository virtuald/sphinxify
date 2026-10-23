import pytest

from sphinxify._document import (
    CodeBlockNode,
    DefinitionEntry,
    DefinitionList,
    HardBreak,
    ListBlock,
    ListItem,
    Note,
    Paragraph,
    PreservedBlock,
    Rubric,
    SoftBreak,
    Table,
    Text,
)
from sphinxify._rst import render_blocks


def para(text):
    return Paragraph([Text(text)])


@pytest.mark.parametrize(
    "blocks, expected",
    [
        (
            [
                Note(
                    [
                        Paragraph(
                            [
                                Text("Intro"),
                                HardBreak(),
                                Text(" next"),
                                SoftBreak(),
                                Text("more"),
                            ]
                        )
                    ]
                )
            ],
            ".. note:: Intro\n   next\n   more",
        ),
        ([Note([para("Inside")]), para("Outside")], ".. note:: Inside\n\nOutside"),
        (
            [Note([Paragraph([Text("Inside")], explicit=True)])],
            ".. note::\n\n   Inside",
        ),
        (
            [ListBlock(False, [ListItem([para("one")]), ListItem([para("two")])])],
            "- one\n\n- two",
        ),
        (
            [
                ListBlock(
                    True,
                    [
                        ListItem(
                            [para("before"), CodeBlockNode("code"), para("after")]
                        ),
                        ListItem([para("next")]),
                    ],
                )
            ],
            "#. before\n\n   ::\n\n      code\n\n   after\n#. next",
        ),
        (
            [DefinitionList([DefinitionEntry([Text("Term")], [para("Definition")])])],
            "Term\n   Definition",
        ),
        (
            [Table([[[para("one")], [para("two")]]])],
            ".. list-table::\n\n   * - one\n     - two",
        ),
        ([Rubric([Text("Heading")])], ".. rubric:: Heading"),
        (
            [PreservedBlock(["<table>", CodeBlockNode("sample"), "</table>"])],
            "<table>\n\n::\n\n   sample\n\n</table>",
        ),
        (
            [
                Note(
                    [
                        ListBlock(
                            False, [ListItem([para("before"), CodeBlockNode("sample")])]
                        )
                    ]
                )
            ],
            ".. note::\n\n   - before\n\n     ::\n\n        sample",
        ),
        ([CodeBlockNode("")], ""),
    ],
)
def test_structural_block_layout(blocks, expected):
    assert render_blocks(blocks) == expected


@pytest.mark.parametrize(
    "payload", ["x  \n\t y\n\n\nlast \t", "<b> @param x\n```\nend\n\n"]
)
def test_code_payload_is_not_layout(payload):
    assert render_blocks([CodeBlockNode(payload, "text")]) == (
        ".. code-block:: text\n\n"
        + "\n".join("   " + line for line in payload.split("\n"))
    )


def test_note_inside_table_cell_has_structural_indentation():
    assert render_blocks([Table([[[Note([para("Inside")]), para("After")]]])]) == (
        ".. list-table::\n\n   * - .. note:: Inside\n\n       After"
    )
