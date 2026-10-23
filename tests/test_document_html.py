from pathlib import Path

import pytest

from sphinxify._document import CodeBlockNode, EnterNote, ExitNote, Literal, SectionSource, SourceText
from sphinxify._html import parse_html
from sphinxify._normalize import normalize_html
from sphinxify._rst import render_blocks


def convert(*parts):
    return render_blocks(normalize_html(parse_html(SectionSource([
        SourceText(p) if isinstance(p, str) else p for p in parts
    ]))))


@pytest.mark.parametrize(
    "parts, expected",
    [
        (("<ul><li>before</li>", CodeBlockNode("sample"), "<li>after</li></ul>"),
         "- before\n\n::\n\n   sample\n\n- after"),
        (("<dl><dt>Term</dt><dd>Definition</dd>", CodeBlockNode("sample"), "</dl>"),
         "Term\n   Definition\n\n::\n\n   sample"),
        (("<ul>Intro &amp; <em>context</em>.<li>One<li>Two</ul>",),
         "Intro & *context*.\n\n- One\n\n- Two"),
        (("<dl><dt>Term</dt><dd>Definition</dd>Tail &amp; text</dl>",),
         "Term\n   Definition\n\nTail & text"),
        (("<a\nhref='https://example.org'>API <code>foo</code></a>",),
         "`API foo <https://example.org>`__"),
        (("Use ", Literal("<b>foo</b>"), " with std::vector<T>."),
         "Use ``<b>foo</b>`` with std::vector<T>."),
        (("<!-- <b>literal</b> --> &amp; &reference",),
         "<!-- <b>literal</b> --> & &reference"),
        (("<li>one</li><li>two</li>",), "- one\n\n- two"),
        (("<table><tr><td colspan='2'>before", CodeBlockNode("replacement"), "after</td></tr></table>"),
         "<table><tr><td colspan='2'>before\n\n::\n\n   replacement\n\nafter</td></tr></table>"),
        ((EnterNote(), "<p>Inside</p><br> next", ExitNote(), "Outside"),
         ".. note::\n\n   Inside\n\n   next\n\nOutside"),
        ((EnterNote(), "<ul><li>inside", ExitNote(), "outside</li></ul>"),
         ".. note:: <ul><li>inside\n\noutside</li></ul>"),
        (("<table><tr><td>one</td><td>two</td></tr></table>",),
         ".. list-table::\n\n   * - one\n     - two"),
    ],
)
def test_html_lowering(parts, expected):
    assert convert(*parts) == expected


@pytest.mark.parametrize("name", [
    "html_inline_code_paragraphs.txt", "html_table_attributes.txt",
    "html_trigger_table.txt", "html_entities.txt", "html_unknown_cpp.txt",
    "html_multiline_link.txt", "html_standalone_list_items.txt",
    "html_formatted_link_labels.txt", "html_link_label_backticks.txt",
])
def test_html_only_corpus_parity(name):
    root = Path(__file__).parent
    assert convert((root / "input" / name).read_text()) + "\n" == (
        root / "expected" / name
    ).read_text()
