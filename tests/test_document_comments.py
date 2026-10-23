from pathlib import Path

import pytest

from sphinxify import CodeBlockReplacement, Doc, Param
from sphinxify._comment import parse_comment
from sphinxify._html import parse_html
from sphinxify._normalize import normalize_html
from sphinxify._rst import render_blocks


def convert(source, fix=lambda name: name, callback=None):
    sections = parse_comment(source, fix, callback)
    def render(section):
        return render_blocks(normalize_html(parse_html(section)))
    return str(Doc(
        render(sections.desc),
        [Param(name, render(section).split("\n")) for name, section in sections.params],
        render(sections.returns).split("\n") if sections.returns is not None else [],
        render(sections.deprecated).split("\n") if sections.deprecated is not None else None,
    ))


@pytest.mark.parametrize("literal", ["<code>foo</code>", "{@code foo}", "``foo``"])
def test_literal_spellings_have_identical_semantics(literal):
    assert convert("<b>" + literal + "</b>") == "``foo``"


@pytest.mark.parametrize("source, expected", [
    ("@note Intro<br> next\nmore", ".. note:: Intro\n   next\n   more"),
    ("@note Example\n\n@code\nf();\n@endcode   \nContinued.\n\nOutside.",
     ".. note:: Example\n\n   ::\n\n      f();\n\n   Continued.\n\nOutside."),
    ("@note @code f(); @endcode", ".. note::\n\n   ::\n\n      f();"),
    ("@deprecated @code f(); @endcode", "\n\n:deprecated: ::\n             \n                f();"),
    ("<p>@param x Description</p>", "\n\n:param x: Description"),
    ("<p>@return Description</p>", "\n\n:returns: Description"),
])
def test_comment_routing(source, expected):
    assert convert(source) == expected


def test_method_name_callback_produces_a_role():
    assert convert("{@link #Run()}", str.lower) == ":meth:`.run`"


def test_callback_order_and_none_preservation():
    seen = []
    source = "Before\n@code{.cpp} a(); @endcode\n@param x Value\n@code b(); @endcode\n@return Value\n@code c(); @endcode\n@deprecated Old\n@code d(); @endcode"
    def callback(block):
        seen.append((block.index, block.text, block.language))
        return None
    result = convert(source, callback=callback)
    assert seen == [(0, "a();", "cpp"), (1, "b();", None), (2, "c();", None), (3, "d();", None)]
    assert result == (
        "Before\n\n.. code-block:: cpp\n\n   a();\n\n"
        ":deprecated: Old\n             \n             ::\n             \n                d();\n\n"
        ":param x: Value\n          \n          ::\n          \n             b();\n\n"
        ":returns: Value\n          \n          ::\n          \n             c();"
    )


def test_generated_math_roles_have_real_boundaries():
    # The historical simple_maths fixture explicitly documents this defect.
    assert convert("x<sub>1</sub>\nx<sup>2</sup>") == (
        "x\\ :sub:`1`\nx\\ :sup:`2`"
    )


@pytest.mark.parametrize("name", [p.name for p in sorted((Path(__file__).parent / "input").glob("*.txt")) if p.name != "simple_maths.txt"])
def test_new_pipeline_corpus_parity(name):
    root = Path(__file__).parent
    assert convert((root / "input" / name).read_text()) + "\n" == (root / "expected" / name).read_text()
