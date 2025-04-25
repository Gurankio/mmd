from typer import Typer

from mmd.html import command_html
from mmd.inline import command_inline
from mmd.parse import command_parse

main = Typer()
main.command('parse')(command_parse)
main.command('html')(command_html)
main.command('inline')(command_inline)

if __name__ == '__main__':
    main()
