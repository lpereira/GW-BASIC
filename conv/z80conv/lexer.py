#!/usr/bin/python
# Copyright (c) 2020 Leandro Pereira <leandro@hardinfo.org>
# Licensed under GPLv2.

from collections import deque


class Lexer:
    def __init__(self, fp):
        self.state = self._lexer_asm
        self.start = 0
        self.pos = 0
        self.contents = fp.read()
        self.end = self.pos + len(self.contents)
        self.queue = deque()
        self.line = 1
        self.col = 1
        self.paren_count = 0

    def lex(self):
        def queue():
            last = {'type': None}
            while self.queue:
                token = self.queue.popleft()
                if token['type'] == 'newline' and last['type'] == 'newline':
                    continue
                if token['type'] == 'token' and token['value'] == '':
                    continue
                yield token
                last = token

        while self.state is not None:
            yield from queue()
            self.state = self.state()

        yield from queue()

    def _next(self):
        if self.pos >= self.end:
            return None
        c = self.contents[self.pos]
        self.pos += 1

        if c == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1

        return c

    def _current_token(self):
        return self.contents[self.start : self.pos]

    def _emit(self, typ, extra=None, value=None):
        tok = {
            'type': typ,
            'value': self._current_token() if value is None else value
        }
        if extra is not None:
            tok['extra'] = extra
        if typ == 'token':
            tok['value'] = tok['value'].upper()
        self.queue.append(tok)

    def _emit_token(self, typ, extra=None, value=None):
        self._emit(typ, extra=extra, value=value)
        self.start = self.pos

    def _error(self, typ):
        self._emit_token('error', extra={
            'type': typ,
            'position': (self.line, self.col)
        })
        return None

    def _ignore(self):
        self.start = self.pos

    def _backup(self):
        self.pos -= 1

    def _lexer_single_line_comment(self):
        self._ignore() # Ignore ;

        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if c in '\r\n':
                self._backup()
                self._emit_token('comment')
                return self._lexer_asm

    def _lexer_directive(self):
        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if c.isspace():
                self._backup()
                self._emit_token('directive')
                return self._lexer_asm

            if not c.isalpha():
                return self._error('Expecting alphabetic character')

    def _lexer_number(self):
        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if not c.isdigit():
                self._backup()
                self._emit_token('number')
                return self._lexer_asm

    def _lexer_multiline_comment(self):
        self._ignore() # Ignore COMMENT

        comment_char = None

        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if c.isspace():
                continue

            comment_char = c
            self._ignore()
            break

        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if c == comment_char:
                self._backup()
                self._emit_token('comment')

                self.pos += 1
                self._ignore()

                return self._lexer_asm

    def _lexer_token_until_end_of_line(self, typ, lex_comma=False):
        self._ignore()

        while True:
            c = self._next()
            if c is None or c in ';\r\n':
                self._backup()
                self._emit_token(typ, value=self._current_token().strip())
                return self._lexer_token
            if c == ',':
                self._backup()
                self._emit_token(typ, value=self._current_token().strip())
                self.pos += 1
                self._ignore()

    def _lexer_title(self):
        return self._lexer_token_until_end_of_line('title')

    def _lexer_subtitle(self):
        return self._lexer_token_until_end_of_line('subtitle')

    def _lexer_extern(self):
        return self._lexer_token_until_end_of_line('extern', lex_comma=True)

    def _lexer_db(self):
        return self._lexer_token_until_end_of_line('db', lex_comma=True)

    def _lexer_dw(self):
        return self._lexer_token_until_end_of_line('dw', lex_comma=True)

    def _lexer_assign(self):
        self._backup()
        tok = self._current_token()
        self.pos += 1
        self._ignore()

        while True:
            c = self._next()
            if c is None or c in ';\r\n':
                self._backup()
                self._emit_token('assign', value={
                    'token': tok,
                    'value': self._current_token().strip()
                })
                return None if c is None else self._lexer_asm

    def _lexer_token(self):
        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if c == '=':
                return self._lexer_assign

            if not c.isalnum() and not c in ':.[]?$_&':
                self._backup()

                curtoken = self._current_token().upper()
                if curtoken == 'COMMENT':
                    return self._lexer_multiline_comment
                elif curtoken == 'TITLE':
                    return self._lexer_title
                elif curtoken == 'SUBTTL':
                    return self._lexer_subtitle
                elif curtoken == 'EXTRN':
                    return self._lexer_extern
                elif curtoken == 'DB':
                    return self._lexer_db
                elif curtoken == 'DW':
                    return self._lexer_dw

                self._emit_token('token')
                return self._lexer_asm

    def _lexer_string(self, end_char, token_type='string'):
        while True:
            c = self._next()
            if c is None:
                return self._error('EOF')

            if c == end_char:
                self._emit_token(token_type)
                return self._lexer_asm

    def _lexer_string_double(self):
        return self._lexer_string('"')

    def _lexer_string_single(self):
        return self._lexer_string('\'')

    def _lexer_angle(self):
        return self._lexer_string('>', token_type='token')

    def _lexer_asm(self):
        while True:
            c = self._next()
            if c is None:
                return None

            if c == '\n':
                self._emit_token('newline')
                continue

            if c.isspace():
                self._ignore()
                continue

            if c == ';':
                return self._lexer_single_line_comment

            if c == '.':
                return self._lexer_directive

            if c == ',':
                self._emit_token('comma')
                continue

            if c == '(':
                self._emit_token('open_paren')
                self.paren_count += 1
                continue

            if c == ')':
                if self.paren_count == 0:
                    return self._error('Closing parenthesis without an opening parenthesis')
                self._emit_token('close_paren')
                self.paren_count -= 1
                if self.paren_count == 0:
                    self._ignore()
                    return self._lexer_asm

            if c.isdigit():
                return self._lexer_number

            if c.isalpha() or c == '?':
                return self._lexer_token

            if c == '\'':
                return self._lexer_string_single

            if c == '"':
                return self._lexer_string_double

            if c == '<':
                return self._lexer_angle
