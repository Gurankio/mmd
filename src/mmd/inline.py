import urllib
from pathlib import Path


def command_inline(file: Path):
    """ Inline CSS into the HTML for most previews to just work """
    pico, _ = urllib.request.urlretrieve('https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css')
    pico = Path(pico).read_text()

    text = file.resolve(strict=True).read_text()
    replaced = text.replace(
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">',
        '<style>' + pico + '</style>'
    )
    (file := file.with_suffix('.local.html')).write_text(replaced)
    print(file)


def test():
    command_inline(Path(__file__).parent.parent.parent / 'input.html')


if __name__ == '__main__':
    test()
