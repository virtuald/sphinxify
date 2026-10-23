"""Route comment sections and recognize semantic atoms without emitting reST."""

import re
from typing import Callable, List, Optional, Union

from ._codeblocks import (
    _HTML_INLINE,
    _HTML_TAG,
    _RST_LITERAL,
    _RST_ROLE,
    CodeBlock,
    CodeBlockTransform,
    split_comment,
)
from ._document import (
    CodeBlockNode,
    EnterNote,
    ExitNote,
    Literal,
    Role,
    SectionSource,
    SourcePart,
    SourceSections,
    SourceText,
)

# Lexical opacity precedes line routing: neither code payload nor quoted HTML
# attributes can accidentally become a Doxygen command or another inline token.
_INLINE_TOKEN = re.compile(
    r"(?P<html_code>" + _HTML_INLINE + r")"
    r"|(?P<html>" + _HTML_TAG + r")"
    r"|(?P<code>\{@code ([^}]+)\})"
    r"|(?P<link>\{@link ([^}]+)\})"
    r"|(?P<literal>" + _RST_LITERAL + r")"
    r"|(?P<role>" + _RST_ROLE + r")",
    re.S,
)


def _link(value: str, fix: Callable[[str], str]) -> Optional[Role]:
    match = re.fullmatch(r"#(\w+?)\(.*?\)\W*", value)
    if match:
        return Role("meth", "." + fix(match[1]))
    match = re.fullmatch(r"(\w+)#(\w+)\(.*?\)\W*", value)
    if match:
        return Role("meth", "." + match[1] + "." + fix(match[2]))
    match = re.fullmatch(r"#(\w+)\.(\w+)\W*", value)
    if match:
        return Role("meth", "." + match[1] + "." + fix(match[2]))
    match = re.fullmatch(r"(?:[a-z]\w*\.)*([A-Z]\w+?)\W*", value)
    if match:
        return Role("class", "." + match[1])
    return None


def _tokenize(text: str, fix: Callable[[str], str]) -> List[SourcePart]:
    result: List[SourcePart] = []
    position = 0
    for match in _INLINE_TOKEN.finditer(text):
        if match.start() > position:
            result.append(SourceText(text[position : match.start()]))
        raw = match[0]
        if match.group("code"):
            result.append(Literal(raw[len("{@code ") : -1]))
        elif match.group("literal"):
            result.append(Literal(raw[2:-2], source=raw))
        elif match.group("link"):
            result.append(_link(raw[len("{@link ") : -1], fix) or SourceText(raw))
        elif match.group("role"):
            name, target = raw[1:].split(":`", 1)
            result.append(Role(name, re.sub(r"\\(.)", r"\1", target[:-1])))
        else:
            result.append(SourceText(raw, protected=True))
        position = match.end()
    if position < len(text):
        result.append(SourceText(text[position:]))
    return result


def _source_lines(text: str, fix: Callable[[str], str]) -> List[List[SourcePart]]:
    lines: List[List[SourcePart]] = []
    line: List[SourcePart] = []
    for part in _tokenize(text, fix):
        if isinstance(part, SourceText) and not part.protected:
            for index, chunk in enumerate(part.text.split("\n")):
                if index:
                    lines.append(line)
                    line = []
                if chunk:
                    line.append(SourceText(chunk))
        else:
            line.append(part)
    if line:
        lines.append(line)
    return lines


def _strip_line(parts: List[SourcePart]) -> List[SourcePart]:
    parts = parts[:]
    while parts and isinstance(parts[0], SourceText) and not parts[0].protected:
        parts[0] = SourceText(parts[0].text.lstrip())
        if parts[0].text:
            break
        parts.pop(0)
    while parts and isinstance(parts[-1], SourceText) and not parts[-1].protected:
        parts[-1] = SourceText(parts[-1].text.rstrip())
        if parts[-1].text:
            break
        parts.pop()
    return parts


def parse_comment(
    txt: str,
    fix_method_name: Callable[[str], str],
    code_block_transform: Optional[CodeBlockTransform],
) -> SourceSections:
    sections = SourceSections()
    current = sections.desc
    note_owner: Optional[SectionSource] = None
    lines: List[Union[List[SourcePart], CodeBlock]] = []
    after_block = False
    for chunk in split_comment(txt):
        if isinstance(chunk, CodeBlock):
            lines.append(chunk)
            after_block = True
        else:
            if after_block:
                chunk = re.sub(r"^[ \t]*\n", "", chunk, count=1)
            lines.extend(_source_lines(chunk, fix_method_name))
            after_block = False

    def close_note():
        nonlocal note_owner
        if note_owner is not None:
            note_owner.parts.append(ExitNote())
            note_owner = None

    def append_line(parts: List[SourcePart]):
        if current.parts and not isinstance(current.parts[-1], EnterNote):
            current.parts.append(SourceText("\n"))
        current.parts.extend(parts)

    for index, token in enumerate(lines):
        if isinstance(token, CodeBlock):
            replacement = code_block_transform(token) if code_block_transform else None
            append_line(
                [
                    CodeBlockNode(
                        token.text if replacement is None else replacement.text,
                        token.language if replacement is None else replacement.language,
                    )
                ]
            )
            continue
        parts = _strip_line(token)
        if (
            len(parts) >= 2
            and isinstance(parts[0], SourceText)
            and parts[0].text == "<p>"
            and isinstance(parts[1], SourceText)
            and parts[1].text.lstrip().startswith(("@", "\\"))
        ):
            parts.pop(0)
            if isinstance(parts[-1], SourceText) and parts[-1].text == "</p>":
                parts.pop()
            parts = _strip_line(parts)
        if not parts:
            following = next(
                (
                    item
                    for item in lines[index + 1 :]
                    if isinstance(item, CodeBlock) or _strip_line(item)
                ),
                None,
            )
            if not isinstance(following, CodeBlock):
                if note_owner is not None:
                    close_note()
                elif current is not sections.returns:
                    current = sections.desc
            append_line([])
            continue
        if not isinstance(parts[0], SourceText) or parts[0].protected:
            append_line(parts)
            continue
        line = parts[0].text
        tail = parts[1:]
        if line.startswith((r"\fn ", r"\class ")):
            continue
        if line.startswith(("@brief ", r"\brief ")):
            line = line[len("@brief ") :]
        elif line.startswith(r"\enum "):
            line = " ".join(line.split()[2:])
        elif (line == "@deprecated" and not tail) or line.startswith("@deprecated "):
            close_note()
            sections.deprecated = current = SectionSource()
            line = line[len("@deprecated ") :]
        elif (line == "@note" and not tail) or line.startswith("@note "):
            close_note()
            current.parts.append(EnterNote())
            note_owner = current
            line = line[len("@note ") :]
        else:
            param = re.search(r"^[\\@]param\W+(\w+)", line)
            if param:
                close_note()
                line = re.sub(r"^[\\@]param\W+\w+(\W+)?", "", line)
                current = SectionSource()
                sections.params.append((param[1], current))
            else:
                returns = re.search(r"^[\\@]returns?\W*", line)
                if returns:
                    close_note()
                    line = re.sub(r"^[\\@]returns?\W*", "", line)
                    if sections.returns is None:
                        sections.returns = SectionSource()
                    current = sections.returns
        if line.startswith(r"\li "):
            line = "-" + line[3:]
        append_line(_strip_line([SourceText(line)] + tail))
    close_note()
    return sections
