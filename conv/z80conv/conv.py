#!/usr/bin/python
# Copyright (c) 2020 Leandro Pereira <leandro@hardinfo.org>
# Licensed under GPLv2.

import sys
import traceback
from .lexer import Lexer
from .parser import Parser
from .transformer import Transformer
from .writer import PasmoWriter


def main():
    lexer = Lexer(sys.stdin)
    parser = Parser(lexer)
    transformer = Transformer(parser)
    writer = PasmoWriter(transformer)

    try:
        for line in writer.lines():
            print(line)
    except SyntaxError as e:
        print("Exception: %s" % e)
        traceback.print_exc(file=sys.stdout)


if __name__ == '__main__':
    main()
