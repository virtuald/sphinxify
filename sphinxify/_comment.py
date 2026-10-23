"""Route comment sections and recognize semantic atoms without emitting reST."""

import re
from typing import Callable, List, Optional, Union

from ._codeblocks import CodeBlock, CodeBlockTransform, split_comment
from ._document import (
    CodeBlockNode, EnterNote, ExitNote, Literal, Role, SectionSource,
    SourcePart, SourceSections, SourceText,
)

# HTML tags are consumed whole so quoted attributes do not become inline atoms.
_INLINE_TOKEN = re.compile(
    r"(?P<html><!--.*?--\s*>|<[A-Za-z/!](?:\"[^\"]*\"|'[^']*'|[^'\">])*>)"
    r"|(?P<code>\{@code ([^}]+)\})"
    r"|(?P<link>\{@link ([^}]+)\})"
    r"|(?P<literal>``.*?``)"
    r"|(?P<role>:(?:[\w-]+:)?[\w-]+:`(?:\\.|[^`])*`)",
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
            result.append(SourceText(text[position:match.start()]))
        raw = match[0]
        if match.group("code"):
            result.append(Literal(raw[len("{@code "):-1]))
        elif match.group("literal"):
            result.append(Literal(raw[2:-2], source=raw))
        elif match.group("link"):
            result.append(_link(raw[len("{@link "):-1], fix) or SourceText(raw))
        elif match.group("role"):
            name, target = raw[1:].split(":`", 1)
            result.append(Role(name, re.sub(r"\\(.)", r"\1", target[:-1])))
        else:
            result.append(SourceText(raw))
        position = match.end()
    if position < len(text):
        result.append(SourceText(text[position:]))
    return result


def _inline_atoms(section: SectionSource, fix: Callable[[str], str]):
    result: List[SourcePart] = []
    text: List[str] = []

    def flush():
        result.extend(_tokenize("".join(text), fix))
        text.clear()

    for part in section.parts:
        if isinstance(part, SourceText):
            text.append(part.text)
        else:
            flush()
            result.append(part)
    flush()
    section.parts = result


def parse_comment(
    txt: str,
    fix_method_name: Callable[[str], str],
    code_block_transform: Optional[CodeBlockTransform],
) -> SourceSections:
    sections = SourceSections()
    current = sections.desc
    note_owner: Optional[SectionSource] = None
    lines: List[Union[str, CodeBlock]] = []
    after_block = False
    for chunk in split_comment(txt):
        if isinstance(chunk, CodeBlock):
            lines.append(chunk)
            after_block = True
        else:
            if after_block:
                chunk = re.sub(r"^[ \t]*\n", "", chunk, count=1)
            lines.extend(chunk.splitlines())
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
            block = CodeBlockNode(
                token.text if replacement is None else replacement.text,
                token.language if replacement is None else replacement.language,
            )
            append_line([block])
            continue
        line = token.strip()
        if line.startswith("<p>") and line[3:].lstrip().startswith(("@", "\\")):
            line = line[3:].lstrip()
            if line.endswith("</p>"):
                line = line[:-4].rstrip()
        if not line:
            following = next((item for item in lines[index + 1:]
                              if isinstance(item, CodeBlock) or item.strip()), None)
            if not isinstance(following, CodeBlock):
                if note_owner is not None:
                    close_note()
                elif current is not sections.returns:
                    current = sections.desc
        if line.startswith((r"\fn ", r"\class ")):
            continue
        if line.startswith(("@brief ", r"\brief ")):
            line = line[len("@brief "):]
        elif line.startswith(r"\enum "):
            line = " ".join(line.split()[2:])
        elif line == "@deprecated" or line.startswith("@deprecated "):
            close_note()
            sections.deprecated = current = SectionSource()
            line = line[len("@deprecated "):]
        elif line == "@note" or line.startswith("@note "):
            close_note()
            current.parts.append(EnterNote())
            note_owner = current
            line = line[len("@note "):]
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
        append_line([SourceText(line.strip())])
    close_note()
    for section in [sections.desc] + [p[1] for p in sections.params] + [sections.returns, sections.deprecated]:
        if section is not None:
            _inline_atoms(section, fix_method_name)
    return sections
