import re
from dataclasses import field, dataclass
from enum import Flag, auto, StrEnum
from pathlib import Path
from typing import Optional


@dataclass
class SourceReference:
    file: Path
    lineno: int

    def __repr__(self):
        return f'Reference(.../{self.file.name}:{self.lineno})'

    def __str__(self):
        return f'.../{self.file.name}:{self.lineno}'


class Modifier(Flag):
    NONE = 0
    WITH_SPACES = auto()
    ALIGN = auto()
    BOLD = auto()
    ITALIC = auto()
    MONOSPACE = auto()
    STRIKETHROUGH = auto()
    SELECT = auto()
    QUOTES = auto()
    BLOCK = auto()


@dataclass
class Word:
    value: str
    modifier: Modifier

    def __repr__(self):
        if self.modifier == Modifier.NONE:
            return f'Word(value={self.value!r})'
        else:
            return f'Word(value={self.value!r}, {self.modifier.name!s})'


@dataclass
class SourceLine:
    reference: SourceReference
    content: list[Word] = field(default_factory=lambda: [])


@dataclass
class Line:
    content: list[SourceLine] = field(default_factory=lambda: [])

    @property
    def line(self) -> Optional['Line']:
        return self

    def empty(self) -> bool:
        return len(self.content) == 0

    def append(self, src: SourceLine):
        self.content.append(src)


@dataclass
class Aside:
    class Kind(StrEnum):
        PLAIN = ''
        EMPHASIS = '#'
        FOOT = '_'

    kind: Kind
    document: 'Document'

    @property
    def line(self) -> Optional[Line]:
        return self.document.paragraph.line


@dataclass
class List:
    marker: str
    document: 'Document'

    @property
    def line(self) -> Optional[Line]:
        return self.document.paragraph.line


@dataclass
class Block:
    language: Optional[str]
    content: list[SourceLine] = field(default_factory=lambda: [])

    @property
    def line(self) -> Optional[Line]:
        return None


@dataclass
class Paragraph:
    content: list[Line | Aside | List | Block] = field(default_factory=lambda: [])

    @property
    def paragraph(self) -> 'Paragraph':
        return self

    @property
    def line(self) -> Optional[Line]:
        return self.content[-1].line if len(self.content) > 0 else None

    def empty(self) -> bool:
        return len(self.content) == 0

    def append(self, line: Line | Aside | List | Block):
        self.content.append(line)


@dataclass
class Section:
    level: int
    title: SourceLine
    document: 'Document'

    @property
    def paragraph(self) -> Paragraph:
        return self.document.paragraph


@dataclass
class Document:
    indent: int
    title: Optional[Paragraph] = field(default=None)
    content: list[Paragraph | Section] = field(default_factory=lambda: [Paragraph()])

    @property
    def paragraph(self) -> Paragraph:
        return self.content[-1].paragraph

    def empty(self) -> bool:
        return all(c.empty() for c in self.content)

    def append(self, block: Paragraph | Section):
        self.content.append(block)

    def pop(self) -> Paragraph | Section:
        return self.content.pop()


def parse(file: Path) -> Document:
    stack = [Document(0)]

    def indent() -> int:
        nonlocal stack
        return sum(d.indent for d in stack)

    def document() -> Document:
        nonlocal stack
        return stack[-1]

    lines = file.read_text().splitlines()
    lines_iterator = enumerate(lines)

    for lineno, text in lines_iterator:
        reference = SourceReference(file, lineno + 1)

        try:
            # Pop document if indent is no longer matched
            #  (empty lines should not pop as spaces get stripped by editors).
            while len(stack) > 1 and len(text) > 0 and not re.match(r'^\s*$', text[:indent()]):
                previous = stack.pop()

                # Remove empty paragraph if it exists and it was not the default one.
                if not previous.empty() and previous.paragraph.empty():
                    # Re-add the paragraph in the correct document instead
                    # if re.match(r'^\s*$', lines[lineno - 1]):
                    document().append(previous.pop())

            # Remove the indent
            text = text[indent():]

            # Claim space if still empty
            if document().empty():
                if match := re.match(r'^(\s*)', text):
                    remaining, = match.groups()
                    remaining = len(remaining)
                    if remaining > 0 and len(stack) == 1:
                        raise ValueError(f'Invalid space on root document @ {reference}')

                    document().indent += remaining
                    text = text[remaining:]

            # Mark as title with triple
            if re.match(r'^---', text):
                document().title = document().pop()
                document().append(Paragraph())
                continue

            # New section if it starts with hashtags
            #   Title is optional handled afterward
            if match := re.match(r'^(#+)(\s*)(?:\s(.+)\s*)?$', text):
                # Remove empty paragraph if it exists
                if document().paragraph.empty():
                    document().pop()

                level, pad, title = match.groups()
                level, pad = len(level), len(pad)
                virtual_document = Document(level + pad + 1)
                document().append(Section(level, title, virtual_document))
                stack.append(virtual_document)
                continue

            # Block
            if match := re.match(r'^```(.+)?\s*$', text):
                language, = match.groups()

                block = Block(language)

                # Skip the current line
                lineno, text = next(lines_iterator)

                # Match all until next delimiter
                while not re.match(r'^```\s*$', text[indent():]):
                    block.content.append(
                        SourceLine(reference=SourceReference(file, lineno),
                                   content=[Word(text[indent():], Modifier.BLOCK)])
                    )
                    lineno, text = next(lines_iterator)

                # Push the block
                document().paragraph.append(block)
                continue

            # Aside if it starts with `.?>`
            if match := re.match(r'^(([_#]?)>\s*)', text):
                match, kind = match.groups()

                virtual_document = Document(len(match))
                document().paragraph.append(Aside(Aside.Kind(kind), virtual_document))
                stack.append(virtual_document)

                # Clean up text and continue parsing this source line
                text = text[len(match):]

            # List (known only implemented)
            if match := re.match(r'^((?:[A-Z]+\.|\d+\.|[IVXCM]+\.|\s*-)+(?:\s+|$))', text):
                marker, = match.groups()

                virtual_document = Document(len(marker))
                document().paragraph.append(List(marker, virtual_document))
                stack.append(virtual_document)

                # Clean up text and continue parsing this source line
                text = text[len(marker):]

            # New paragraph if whitespace only or empty
            if re.match(r'^\s*$', text):

                # Skip if paragraph is empty
                if document().paragraph.empty():
                    continue

                document().append(Paragraph())
                continue

            # New line if it does not start with a space
            if re.match(r'^\S', text):
                document().paragraph.append(Line())

            # Continued line otherwise
            else:
                if document().paragraph.empty():
                    raise ValueError(f"Invalid indentation @ {reference}")

                text = f'{text.lstrip()}'

            ## Text/Word level parsing
            source_line = SourceLine(reference)
            words = re.split(r'([_*~`]{1,2}|["\[\]]|\s+)', text.rstrip())

            modifier = Modifier.NONE
            for i in range(len(words)):
                if len(words[i]) == 0:
                    continue

                # TODO: If it is a space then it coudl be aligning something.

                mapping = {
                    '*': Modifier.BOLD,
                    '_': Modifier.ITALIC,
                    '~': Modifier.STRIKETHROUGH,
                    '`': Modifier.MONOSPACE,
                    '"': Modifier.QUOTES,
                    '[': Modifier.SELECT,
                    ']': Modifier.SELECT,
                }

                if words[i][0] in mapping:
                    applied = mapping[words[i][0]]
                    if len(words[i]) == 2 or applied == Modifier.QUOTES:
                        applied |= modifier.WITH_SPACES
                    modifier ^= applied
                    continue

                if modifier != Modifier.NONE and not (modifier & Modifier.WITH_SPACES) and re.match(r'\s', words[i]):
                    raise ValueError(f'Spaces are not allowed here! @ {reference}')

                source_line.content.append(Word(words[i], modifier))

                # Remove ALIGN after one word and check line before.
                if modifier & Modifier.ALIGN:
                    modifier ^= Modifier.ALIGN

            document().paragraph.line.append(source_line)

        except Exception as e:
            e.add_note(f"@ {reference!s}, {indent():2} = {lines[lineno][indent()]!r}")
            raise e

    return stack[0]


def command_parse(file: Path):
    """ Dump the parsed AST """
    from rich import print
    print(parse(file.resolve(strict=True)))


def test():
    command_parse(Path(__file__).parent.parent.parent / 'input.mmd')


if __name__ == '__main__':
    test()
