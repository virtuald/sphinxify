"""Source-preserving HTML parsing; no reST syntax or output layout lives here."""

import re
from html import unescape
from html.entities import html5
from html.parser import HTMLParser

from ._document import (
    EnterNote, ExitNote, HtmlElement, HtmlNote, HtmlText, OpaqueInline,
    ParsedSection, SectionSource, SourceText,
)

_INLINE = {
    "b": "strong", "strong": "strong",
    "i": "emphasis", "em": "emphasis",
}
_BLOCKS = {"table", "p", "ul", "ol", "dl", "h1", "h2", "h3", "h4", "h5", "h6"}
_TAGS = _BLOCKS | set(_INLINE) | {
    "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "li", "dt", "dd",
    "a", "code", "tt", "sub", "sup", "br",
}


def _unescape(text: str) -> str:
    # C++ &references are not optional-semicolon HTML entities.
    def replace(match):
        name = match[1]
        if name.startswith("#"):
            return unescape(match[0])
        return html5.get(name + ";", match[0])
    return re.sub(r"&(#(?:[xX][0-9a-fA-F]+|[0-9]+)|[A-Za-z][A-Za-z0-9]*);", replace, text)


class _SourceParser(HTMLParser):
    def __init__(self, source: SectionSource):
        super().__init__(convert_charrefs=False)
        prefix = "\x00sphinxify-node-"
        values = [value for part in source.parts for value in vars(part).values()
                  if isinstance(value, str)]
        while any(prefix in value for value in values):
            prefix += "-"
        self.atoms = {}
        text = []
        for part in source.parts:
            if isinstance(part, SourceText):
                text.append(part.text)
            else:
                key = prefix + str(len(self.atoms)) + "\x00"
                self.atoms[key] = part
                text.append(key)
        self.source = "".join(text)
        self.pattern = re.compile("(" + "|".join(map(re.escape, self.atoms)) + ")") if self.atoms else None
        self.root = ParsedSection()
        self.stack = [self.root]
        self.offsets = [0]
        for line in self.source.split("\n"):
            self.offsets.append(self.offsets[-1] + len(line) + 1)
        self.consumed = 0
        self.feed(self.source)
        self.close()
        if self.consumed < len(self.source):
            self._data(self.source[self.consumed:])

    def _offset(self):
        line, col = self.getpos()
        return self.offsets[line - 1] + col

    def _record(self, raw):
        offset = self._offset()
        if offset > self.consumed:
            self._data(self.source[self.consumed:offset])
        self.consumed = offset + len(raw)

    def _close_optional(self, tags, boundaries):
        for index in range(len(self.stack) - 1, 0, -1):
            element = self.stack[index]
            if not isinstance(element, HtmlElement):
                break
            if element.tag in tags:
                del self.stack[index:]
                break
            if element.tag in boundaries:
                break

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        if tag not in _TAGS:
            self.handle_data(raw)
            return
        self._record(raw)
        if tag in _BLOCKS:
            self._close_optional({"p"}, {"td", "th", "li"})
        if tag == "li":
            self._close_optional({"li"}, {"ul", "ol"})
        elif tag in {"dt", "dd"}:
            self._close_optional({"dt", "dd"}, {"dl"})
        elif tag in {"td", "th"}:
            self._close_optional({"td", "th"}, {"tr", "table"})
        elif tag == "tr":
            self._close_optional({"tr"}, {"table", "thead", "tbody", "tfoot"})
        element = HtmlElement(tag, dict(attrs), opening=raw)
        self.stack[-1].children.append(element)
        if tag != "br":
            self.stack.append(element)

    def handle_endtag(self, tag):
        offset = self._offset()
        raw = self.source[offset:self.source.find(">", offset) + 1]
        self._record(raw)
        for index in range(len(self.stack) - 1, 0, -1):
            element = self.stack[index]
            if not isinstance(element, HtmlElement):
                break
            if element.tag == tag:
                element.closing = raw
                del self.stack[index:]
                return
        self.stack[-1].children.append(HtmlText(raw))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in _TAGS and tag != "br":
            self.stack.pop()

    def _data(self, data):
        for part in self.pattern.split(data) if self.pattern else [data]:
            if not part:
                continue
            atom = self.atoms.get(part)
            if isinstance(atom, EnterNote):
                note = HtmlNote()
                self.stack[-1].children.append(note)
                self.stack.append(note)
            elif isinstance(atom, ExitNote):
                for index in range(len(self.stack) - 1, 0, -1):
                    if isinstance(self.stack[index], HtmlNote):
                        for open_element in self.stack[index + 1:]:
                            if isinstance(open_element, HtmlElement) and open_element.tag != "p":
                                open_element.preserve = True
                        del self.stack[index:]
                        break
            elif atom is not None:
                self.stack[-1].children.append(atom)
            else:
                self.stack[-1].children.append(HtmlText(part))

    def handle_data(self, data):
        self._record(data)
        self._data(data)

    def _reference(self, prefix, name):
        raw = prefix + name
        if self.source[self._offset() + len(raw):].startswith(";"):
            raw += ";"
        self.handle_data(raw)

    def handle_entityref(self, name):
        self._reference("&", name)

    def handle_charref(self, name):
        self._reference("&#", name)

    def handle_comment(self, data):
        offset = self._offset()
        end = self.source.find(">", offset + 4 + len(data)) + 1
        raw = self.source[offset:end]
        self._record(raw)
        self.stack[-1].children.append(OpaqueInline(raw))


def parse_html(source: SectionSource) -> ParsedSection:
    """Parse one section, keeping atoms and explicit note boundaries structural."""
    return _SourceParser(source).root
