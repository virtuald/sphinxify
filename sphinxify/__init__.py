"""Convert Javadoc/Doxygen to Sphinx reStructuredText docstrings."""

import functools
import warnings
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from ._codeblocks import CodeBlock, CodeBlockReplacement, CodeBlockTransform
from ._comment import parse_comment
from ._document import SectionSource
from ._html import parse_html
from ._normalize import normalize_html
from ._rst import render_blocks

__version__ = "0.14"


def trim_lines(lines: List[str]) -> List[str]:
    # Indented blank code lines are payload, not removable field layout.
    lines = "\n".join(lines).split("\n")
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return lines or [""]


@dataclass
class Param:
    #: The parameter name.
    name: str
    #: Lines describing the parameter.
    lines: List[str]


@dataclass
class Doc:
    #: The description prose before any parameters are listed.
    desc: str
    #: List of parameters.
    params: List[Param]
    #: The return value description (as a list of lines).
    returns: List[str]
    #: The deprecation message, if any.
    deprecated: Optional[List[str]] = None

    @functools.cached_property
    def _params_dict(self) -> Dict[str, Param]:
        """Ordered mapping of parameter names and their descriptions."""
        return {p.name: p for p in self.params}

    @classmethod
    def from_comment(
        cls,
        txt: str,
        fix_method_name: Callable[[str], str] = lambda x: x,
        *,
        code_block_transform: Optional[CodeBlockTransform] = None,
    ) -> "Doc":
        """Create a Doc from a doc comment.

        Arguments:
            txt: The doc comment to convert.
            fix_method_name: A callback to convert method names in links.
            code_block_transform: Called once per source block, in source order.
                Return a CodeBlockReplacement, or None to preserve the block.

        Raises:
            ValueError: A recognized code block has no closing delimiter.
        """
        sections = parse_comment(txt, fix_method_name, code_block_transform)

        def render(section: SectionSource) -> str:
            return render_blocks(normalize_html(parse_html(section)))

        return cls(
            render(sections.desc),
            [Param(name, render(section).split("\n")) for name, section in sections.params],
            render(sections.returns).split("\n") if sections.returns is not None else [],
            render(sections.deprecated).split("\n") if sections.deprecated is not None else None,
        )

    def get_param(self, name: str) -> Optional[Param]:
        return self._params_dict.get(name)

    def remove_param(self, name: str) -> None:
        to_delete = self._params_dict[name]
        for i, param in enumerate(self.params):
            if param is to_delete:
                del self.params[i]
        del self._params_dict[name]

    def __str__(self) -> str:
        """Convert a Doc to Sphinx reST."""
        to_append = ["\n"]
        if self.deprecated is not None:
            to_append.append(":deprecated: " + self.deprecated[0])
            to_append += [" " * 13 + line for line in self.deprecated[1:]]
            to_append.append("")
        if self.params:
            pindent = max(len(p.name) for p in self.params) + len(":param : ")
            pindent_str = " " * pindent
            for param in self.params:
                pname = f":param {param.name}: "
                pp = trim_lines(param.lines)
                to_append.append(f'{pname}{" " * (pindent - len(pname))}{pp[0]}')
                to_append += [pindent_str + line for line in pp[1:]]
            to_append.append("")
        if self.returns:
            returns = trim_lines(self.returns)
            to_append.append(":returns: " + returns[0])
            to_append += [" " * 10 + line for line in returns[1:]]
        return self.desc + "\n".join(to_append).rstrip("\n")


def process_doc(
    txt: str, *, code_block_transform: Optional[CodeBlockTransform] = None
) -> str:
    """Convert a doc comment to Sphinx reST, optionally transforming code blocks."""
    return str(Doc.from_comment(txt, code_block_transform=code_block_transform))


def process_raw(
    txt: str, *, code_block_transform: Optional[CodeBlockTransform] = None
) -> str:
    """
    Convert the first doc comment in txt into Sphinx reST.

    .. deprecated:: 0.13
       Use :func:`sphinxify.from_java.process_raw` instead.
    """
    from sphinxify.from_java import process_raw

    warnings.warn(
        "Use sphinxify.from_java.process_raw instead", DeprecationWarning, stacklevel=2
    )
    return process_raw(txt, code_block_transform=code_block_transform)
