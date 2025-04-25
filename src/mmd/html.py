import re
import textwrap
from pathlib import Path

from more_itertools import peekable

from mmd.parse import Document, Line, Modifier, Aside, Block, List, Paragraph, Section, parse


def as_html(root: Document) -> str:
    def l_as_html(l: Line):
        output = ''

        def as_tag(s, modifier, start, end):
            nonlocal output
            if s & modifier:
                output += start
            else:
                output += end

        def all_tags(diff):
            if diff & Modifier.QUOTES:
                as_tag(w.modifier, Modifier.QUOTES, '<q>', '</q>')
            if diff & Modifier.BOLD:
                as_tag(w.modifier, Modifier.BOLD, '<strong>', '</strong>')
            if diff & Modifier.ITALIC:
                as_tag(w.modifier, Modifier.ITALIC, '<i>', '</i>')
            if diff & Modifier.MONOSPACE:
                as_tag(w.modifier, Modifier.MONOSPACE, '<code>', '</code>')
            if diff & Modifier.SELECT:
                as_tag(w.modifier, Modifier.SELECT, '<mark>', '</mark>')
            if diff & Modifier.STRIKETHROUGH:
                as_tag(w.modifier, Modifier.STRIKETHROUGH, '<s>', '</s>')

        for src in l.content:
            prev = Modifier.NONE
            for w in src.content:
                all_tags(prev ^ w.modifier)
                prev = w.modifier
                output += w.value
            all_tags(prev)
            output += ' '

        return output.rstrip() + '<br>'

    def aside_as_html(a: Aside, nesting: int):
        # TODO: use kind
        yield "<p>"
        yield "<article>"
        inner = d_as_html(a.document, nesting + 1)

        # If there is a title output, wrap in header and skip hr.
        tmp = next(inner)
        if tmp == '<hgroup>':
            yield '<header>'
            yield tmp
            while (tmp := next(inner)) != '<hr>':
                yield tmp
            yield '</header>'

        # If the first thing is a paragraph skip the tag as it messes with pico.css
        tmp = next(inner)
        if tmp != '<p>':
            yield tmp

        yield from inner
        yield "</article>"

    def block_as_html(b: Block, _nesting: int):
        def inner():
            yield "<pre><code>"
            yield textwrap.dedent(''.join(x.content[0].value + '\n' for x in b.content)).replace('\n', '<br>')
            yield "</code></pre>"

        yield ''.join(inner())

    def list_as_html(ls: list[List], nesting: int):
        start, end = None, None
        if re.search(r'[A-Z]+\.\s*$', ls[0].marker):
            start, end = '<ol type="A">', '</ol>'

        if re.search(r'\d+\.\s*$', ls[0].marker):
            start, end = '<ol type="1">', '</ol>'

        if re.search(r'[IVXCM]+\.\s*$', ls[0].marker):
            start, end = '<ol type="I">', '</ol>'

        if re.search(r'\s*-\s*$', ls[0].marker):
            start, end = '<ul>', '</ul>'

        assert start is not None, repr(ls[0].marker)
        assert end is not None, repr(ls[0].marker)

        yield start
        for l in ls:
            yield '<li>'
            yield from d_as_html(l.document, nesting + 1)
            yield '</li>'
        yield end

    def p_as_html(p: Paragraph, nesting: int):
        yield '<p>'
        content = peekable(enumerate(p.content))
        for i, x in content:
            if isinstance(x, Line):
                l = l_as_html(x)
                if i + 1 == len(p.content):
                    l = l.removesuffix('<br>')
                yield l
            if isinstance(x, Aside):
                yield from aside_as_html(x, nesting)
            if isinstance(x, Block):
                yield from block_as_html(x, nesting)
            if isinstance(x, List):
                items = [x]
                try:
                    while isinstance(content.peek()[1], List):
                        items.append(next(content)[1])
                except StopIteration:
                    pass

                yield from list_as_html(items, nesting)
        yield '</p>'

    def s_as_html(s: Section, nesting: int):
        yield '<section>'
        yield {
            1: f'<h5>{s.title}</h5>',
            2: f'<h4>{s.title}</h4>',
            3: f'<h3>{s.title}</h3>',
            4: f'<h2>{s.title}</h2>',
        }[min(max(1, s.level), 4)]
        yield from d_as_html(s.document, nesting + 1)
        yield '</section>'

    def d_as_html(d: Document, nesting: int):
        def inner():
            if d.title is not None:
                yield '<hgroup>'
                if isinstance(d.title, Paragraph):
                    if len(d.title.content) > 0:
                        start, end = {
                            0: ('<h2>', '</h2>'),
                            1: ('<h4>', '</h4>'),
                            2: ('<h5>', '</h5>'),
                        }[min(nesting, 2)]
                        yield f'{start}{l_as_html(d.title.content[0]).removesuffix('<br>')}{end}'
                    yield '<p>'
                    for x in d.title.content[1:]:
                        if isinstance(x, Line):
                            yield l_as_html(x)
                        else:
                            print('Non-lines as title are not supported. And should not be allowed anyway.')
                else:
                    print('Section as title is not supported. And should not be allowed anyway.')
                yield '</hgroup>'
                yield '<hr>'

            for x in d.content:
                if isinstance(x, Section):
                    yield from s_as_html(x, nesting)
                if isinstance(x, Paragraph):
                    yield from p_as_html(x, nesting)

        yield from inner()

    return textwrap.dedent(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>mmd</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
            <style>
                section {{ margin-left: 1rem }}
                section > :where(h1, h2, h3, h4, h5, h6) {{ margin-left: -1rem }}
            </style>
        </head>
        <body>
        <main class="container">
{''.join(f'        {x}\n' for x in d_as_html(root, 0))}
        </main>
        </body>
        </html>
        """
    )


def command_html(file: Path, open: bool = False):
    """ Renders a mmd file to HTML """
    root = parse(file.resolve(strict=True))
    (file := file.with_suffix('.html')).write_text(as_html(root))

    if open:
        from subprocess import run
        run(['open', str(file)])


def test():
    command_html(Path(__file__).parent.parent.parent / 'input.mmd')


if __name__ == '__main__':
    test()
