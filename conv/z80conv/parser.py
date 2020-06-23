#!/usr/bin/python
# Copyright (c) 2020 Leandro Pereira <leandro@hardinfo.org>
# Licensed under GPLv2.

from collections import deque


class Parser:
    def __init__(self, lexer):
        self.tokens = lexer.lex()
        self.token_queue = deque()
        self.queue = deque()
        self.state = self._parse_asm

        self.in_cseg = False
        self.in_dseg = False
        self.forc_counter = 0
        self.rept_counter = 0
        self.macro_args = deque()
        self.radix = 10
        self.externs = {}

    def parse(self):
        def queue():
            while self.queue:
                yield self.queue.popleft()

        while self.state is not None:
            yield from queue()
            self.state = self.state()

        yield from queue()

    def _emit(self, token):
        self.queue.append(token)

    def _error(self, msg):
        self._emit({'type': 'error', 'value': msg})
        return None

    def _next(self):
        if self.token_queue:
            return self.token_queue.popleft()
        return next(self.tokens, None)

    def _peek(self):
        token = self._next()
        self.token_queue.appendleft(token)
        return token

    def _must_next(self, msg):
        token = self._next()
        if token is None:
            raise SyntaxError(msg)
        return token

    def _must_next_type(self, typ, msg):
        token = self._must_next(msg)
        if token['type'] != typ:
            raise SyntaxError("Expecting type %s, got %s: %s" % (typ, token['type'], msg))
        return token

    def _parse_directive_radix(self):
        token = self._must_next_type('number', "Expecting radix number")
        self._emit({'type': 'directive_radix', 'value': token['value']})
        self.radix = int(token['value'])
        return self._parse_asm

    def _parse_directive_xlist(self):
        self._emit({'type': 'xlist'})
        return self._parse_asm

    def _parse_directive_sall(self):
        self._emit({'type': 'sall'})
        return self._parse_asm

    def _parse_directive_list(self):
        self._emit({'type': 'list'})
        return self._parse_asm

    def _parse_directive(self, token):
        typ = token['value'][1:]
        return getattr(self, '_parse_directive_%s' % typ.lower())

    def _parse_seg(self, is_cseg=True):
        token = self._must_next_type('token', "Expecting token")
        if token['value'] == 'SEGMENT':
            if is_cseg:
                if self.in_cseg:
                    return self._error("Already in code segment")
            elif self.in_dseg:
                return self._error("Already in data segment")

            token = self._must_next("Expecting segment information")
            if token == {'type': 'token', 'value': 'PUBLIC'}:
                public = True
                token = self._must_next_type('string', "Expecting segment name")
            elif token['type'] == 'string':
                public = False
            else:
                return self._error("Expecting string or PUBLIC")
            self._emit({'type': 'cseg', 'public': public, 'name': token['value'][1:-1]})

            if is_cseg:
                self.in_cseg = True
            else:
                self.in_dseg = True
            return self._parse_asm
        elif token['value'] == 'ENDS':
            if is_cseg:
                self.in_cseg = False
            else:
                self.in_dseg = False
            return self._parse_asm
        else:
            return self._error("Expecting SEGMENT or ENDS")

    def _parse_cseg(self):
        return self._parse_seg(is_cseg=True)

    def _parse_dseg(self):
        return self._parse_seg(is_cseg=False)

    def _parse_assume(self):
        token = self._must_next_type('token', "Expecting segment to assume")
        if not ':' in token['value']:
            return self._error("Segment seems invalid")
        self._emit({'type': 'assume', 'seg': token['value']})
        return self._parse_asm

    def _parse_include(self):
        token = self._must_next_type('token', "Expecting file name to include")
        self._emit({'type': 'include', 'filename': token['value']})
        return self._parse_asm

    def _parse_org(self):
        token = self._must_next_type('number', "Expecting ORG argument")
        self._emit({'type': 'org', 'value': token['value']})
        return self._parse_asm

    def _parse_public(self):
        while True:
            token = self._next()
            if token is None:
                return None

            if token['type'] == 'token':
                self._emit({'type': 'public', 'identifier': token['value']})
            elif token['type'] == 'comma':
                continue
            elif token['type'] == 'newline':
                break
            elif token['type'] == 'comment':
                self._emit({'type': 'comment', 'value': token['value']})
                break
        return self._parse_asm

    def _parse_extern(self, token):
        identifier = token['value'].split(":")
        if len(identifier) != 2:
            self._error("Don't know what to do")
        self.externs[identifier[0]] = identifier[1]
        self._emit({'type': 'extern', 'identifier': identifier[0], 'attr': identifier[1]})
        return self._parse_asm

    def _parse_assign(self, token):
        token = token['value']
        self._emit({'type': 'assign', 'symbol': token['token'], 'value': token['value']})
        return self._parse_asm

    def _parse_label(self, token):
        self._emit({'type': 'label', 'identifier': token['value'][:-1]})
        return self._parse_asm

    def _is_x86_instruction(self, token):
        return token['value'] in {
            'MOV', 'ADD', 'INC', 'CMP', 'JNZ', 'JMP', 'JZ', 'RET', 'PUSH', 'POP',
            'CALL', 'OR', 'XCHG', 'AND', 'XOR', 'DEC', 'JAE', 'JB', 'SUB', 'PUSHF',
            'POPF', 'JNAE', 'STC', 'JNB', 'LAHF', 'SAHF', 'CMC', 'SBB', 'STOSB',
            'REP', 'JNS', 'JS', 'ROR', 'ROL', 'ADC', 'CLD', 'SHL', 'SHR', 'XLAT',
            'LOOP', 'TEST', 'CBW', 'NEG', 'JLE', 'JO', 'JGE', 'JL', 'MOVS', 'JPO',
            'JNE', 'RCL', 'RCR', 'CLC', 'MOVSW', 'LODS', 'STOSW', 'NOT', 'STD',
            'CMPSW', 'JPE', 'IMUL', 'IDIV', 'MUL', 'SAL', 'JE', 'LODSW', 'LODSB',
            'MOVSB', 'JA', 'DIV', 'JCXZ', 'CLI', 'STI', 'LEA', 'JP', 'IN', 'OUT',
            'INT', 'JG', 'REPE', 'REPZ', 'REPNE', 'REPNZ',
        }

    def _is_macro(self, token):
        return token['value'] in {
            'INS86', 'ACRLF', 'DO_EXT', 'HLFHL', 'HLFDE', 'NEGDE', 'POPR', 'UN_DEF',
            'MOVRI', 'T', 'Q', 'QF', 'DERMAK', '?Z0', 'ADD_EXT', 'DEF_MAC', 'M', 'R',
            'R2', '?&S', 'EXPAND_MAC', 'CALLOS', 'DUMY', 'ADR', 'DC', 'NEGHL',
            'CPMXIO', 'DOSIO', 'NDEV', 'DEV', 'NAMES',

            # FIXME: add_ext macro in BINTRP.H references this, but it's parsed incorrectly
            '?I'
        }

    def _valid_number_for_radix(self, num, radix):
        if radix == 8:
            return all('0' <= c <= '7' for c in num)
        if radix == 10:
            return all('0' <= c <= '9' for c in num)
        if radix == 16:
            hex_digits = "0123456789abcdefABCDEF"
            return all(c in hex_digits for c in num)
        raise SyntaxError("Unknown radix: %d" % radix)

    def _radix_to_num(self, radix):
        return {'O': 8, 'H': 16, 'D': 10}[radix]

    def _parse_x86_operand(self, operand):
        out = []
        skip = False
        for i, op in enumerate(operand):
            if skip:
                skip = False
                continue
            if isinstance(op, str):
                if i < len(operand)-1 and operand[i+1] in ('O', 'H', 'D'):
                    skip = True
                    radix = self._radix_to_num(operand[i+1])
                else:
                    radix = self.radix
                if self._valid_number_for_radix(op, radix):
                    out.append(int(op, radix))
                else:
                    out.append(op)
            elif isinstance(op, list) or isinstance(op, tuple):
                out.append(self._parse_x86_operand(op))
            else:
                out.append(op)
        return out[0] if len(out) == 1 else tuple(out)

    def _get_x86_operand(self, n_paren=0):
        operand = []
        while True:
            peek = self._peek()
            if peek is None:
                break
            elif peek['type'] in ('token', 'number', 'string'):
                self._next()
                operand.append(peek['value'])
            elif peek['type'] == 'open_paren':
                self._next()
                operand.append(self._get_x86_operand(n_paren + 1))
            elif peek['type'] == 'close_paren':
                self._next()
                if n_paren == 0:
                    return self._error("Close parenthesis without open parenthesis")
                break
            elif peek['type'] in ('newline', 'comment', 'comma'):
                break
            else:
                return self._error("Unexpected token: %s" % token)
        return self._parse_x86_operand(operand)

    def _parse_x86_instruction(self, token):
        instruction = token['value']
        operands = []
        comment = None
        while True:
            peek = self._peek()
            if peek is None:
                break
            if peek['type'] in ('token', 'number', 'string', 'open_paren'):
                operands.append(self._get_x86_operand())
            elif peek['type'] == 'close_paren':
                return self._error("Close parenthesis without open parenthesis")
            elif peek['type'] == 'comma':
                self._next()
                continue
            elif peek['type'] == 'comment':
                self._next()
                comment = peek['value']
                break
            elif peek['type'] == 'newline':
                break
            else:
                return self._error("Unexpected token while parsing 8086 instruction operand: %s" % token)
        self._emit({'type': 'instruction', 'op': instruction, 'operands': tuple(operands), 'comment': comment})
        return self._parse_asm

    def _parse_byte_from_db(self, db):
        try:
            return int(db, self.radix)
        except ValueError:
            pass

        try:
            if db[-1] == 'D':
                return int(db[:-1], 10)
            if db[-1] == 'H':
                return int(db[:-1], 16)
            if db[-1] == 'O':
                return int(db[:-1], 8)
        except ValueError:
            pass

        return db

    def _parse_macro_movri(self, arguments, comment):
        if len(arguments) != 4:
            raise NotImplementedError("Don't know how to generate MOVRI with %d arguments" % len(arguments))

        as_number = []
        for arg in arguments:
            if len(arg) == 2:
                assert arg[0]['type'] == 'number'
                assert arg[1]['type'] == 'token' and arg[1]['value'] in 'OHD'

                arg = int(arg[0]['value'], self._radix_to_num(arg[1]['value']))
            elif len(arg) == 1:
                arg = int(arg[0]['value'], self.radix)
            else:
                raise NotImplementedError("Can't parse argument for MOVRI macro: %s" % str(arguments))

            as_number.append(arg)

        cx_val = as_number[1] | as_number[0] << 8
        dx_val = as_number[3] | as_number[2] << 8

        self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('CX', cx_val), 'comment': comment})
        self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('DX', dx_val), 'comment': None})
        return self._parse_asm

    def _parse_macro_ins86(self, arguments, comment):
        operands = []
        for ops in arguments:
            for op in ops:
                if op['type'] == 'number':
                    if op['value'].isdigit(): # Arguments to this macro are always in octal
                        operands.append(int(op['value'], 8))
                    elif op['value'] == '+2':
                        operands[-1] += op['value']
                    else:
                        raise SyntaxError("Unknown radix for INS86 numeric argument")
                elif op['type'] in ('token', 'string'):
                    operands.append(op['value'])
                else:
                    raise SyntaxError("Invalid argument to INS86 macro")

        operands = tuple(operands)

        if operands == (6,):
            self._emit({'type': 'instruction', 'op': 'push', 'operands': ('ES',), 'comment': comment})
            return self._parse_asm

        if operands == (7,):
            self._emit({'type': 'instruction', 'op': 'pop', 'operands': ('ES',), 'comment': comment})
            return self._parse_asm

        if operands == (14,):
            self._emit({'type': 'instruction', 'op': 'push', 'operands': ('CS',), 'comment': comment})
            return self._parse_asm

        if operands == (203,):
            self._emit({'type': 'instruction', 'op': 'retf', 'operands': (), 'comment': comment})
            return self._parse_asm

        if operands == (236,):
            self._emit({'type': 'instruction', 'op': 'in', 'operands': ('AL', 'DX'), 'comment': comment})
            return self._parse_asm

        if operands == (238,):
            self._emit({'type': 'instruction', 'op': 'out', 'operands': ('DX', 'AL'), 'comment': comment})
            return self._parse_asm

        if operands in ((46,), (38,)): # CS:/ES: prefixes, useless for Z80
            if comment:
                self._emit({'type': 'comment', 'value': comment})
            return self._parse_asm

        if operands == (139, 242, 46, 172):
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('SI', 'DX'), 'comment': comment})
            self._emit({'type': 'instruction', 'op': 'lodsb', 'operands': ('AL', '[SI]'), 'comment': None})
            return self._parse_asm

        if operands == (50, 228):
            self._emit({'type': 'instruction', 'op': 'xor', 'operands': ('AH', 'AH'), 'comment': comment})
            return self._parse_asm

        if operands == (140, 218):
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('DX', 'DS'), 'comment': comment})
            return self._parse_asm

        if operands == (57, 23):
            self._emit({'type': 'instruction', 'op': 'cmp', 'operands': ('[BX]', 'DX'), 'comment': comment})
            return self._parse_asm

        if operands == (209, 235):
            self._emit({'type': 'instruction', 'op': 'shr', 'operands': ('BX', 1), 'comment': comment})
            return self._parse_asm

        if operands == (139, 240):
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('SI', 'AX'), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (142, 6) and len(operands) == 3:
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('ES', operands[-1]), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (255, 180) and len(operands) == 3:
            self._emit({'type': 'instruction', 'op': 'push', 'operands': (operands[-1],), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (137, 22) and len(operands) == 3:
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': (operands[-1], 'DX'), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (137, 38) and len(operands) == 3:
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': (operands[-1], 'SP'), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (246, 6) and len(operands) == 3:
            if comment:
                self._emit({'type': 'comment', 'value': comment})
                comment = None
            while True:
                peek = self._peek()
                if peek['type'] == 'newline':
                    self._next()
                    continue
                if peek['type'] == 'comment':
                    self._next()
                    comment = peek['value']
                    continue
                if peek['type'] == 'db':
                    self._next()
                    op = peek['value']
                    self._emit({'type': 'instruction', 'op': 'test', 'operands': (operands[-1], op), 'comment': comment})
                    return self._parse_asm
                break

        if operands in ((185,), (186,)):
            if comment:
                self._emit({'type': 'comment', 'value': comment})
                comment = None
            dbs = []
            while len(dbs) != 2:
                peek = self._peek()
                if peek['type'] == 'newline':
                    self._next()
                    continue
                if peek['type'] == 'comment':
                    self._next()
                    comment = peek['value']
                    continue
                if peek['type'] == 'db':
                    self._next()
                    dbs.append(peek['value'])
                    continue
                raise SyntaxError("Unexpected token found while parsing INS86 macro: %s" % peek)
            op1 = 'CX' if operands[0] == 185 else 'DX'
            op2 = dbs[0], dbs[1]
            self._emit({'type': 'instruction', 'op': 'movi', 'operands': (op1, op2), 'comment': comment})
            return self._parse_asm

        if operands == (209, 234):
            self._emit({'type': 'instruction', 'op': 'shr', 'operands': ('DX', 1), 'comment': comment})
            return self._parse_asm

        if operands == (209, 233):
            self._emit({'type': 'instruction', 'op': 'shr', 'operands': ('BX', 1), 'comment': comment})
            return self._parse_asm

        if operands == (247, 218):
            self._emit({'type': 'instruction', 'op': 'neg', 'operands': ('DX',), 'comment': comment})
            return self._parse_asm

        if operands == (247, 219):
            self._emit({'type': 'instruction', 'op': 'neg', 'operands': ('BX',), 'comment': comment})
            return self._parse_asm

        if operands == (247, 226):
            self._emit({'type': 'instruction', 'op': 'mul', 'operands': ('DX',), 'comment': comment})
            return self._parse_asm

        if operands == (138, 242):
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('DH', 'DL'), 'comment': comment})
            return self._parse_asm

        if operands == (5,):
            if comment:
                self._emit({'type': 'comment', 'value': comment})
                comment = None
            dbs = []
            while len(dbs) != 2:
                peek = self._peek()
                if peek['type'] == 'newline':
                    self._next()
                    continue
                if peek['type'] == 'comment':
                    self._next()
                    comment = peek['value']
                    continue
                if peek['type'] == 'db':
                    self._next()
                    dbs.append(peek['value'])
                    continue
                raise SyntaxError("Unexpected token found while parsing INS86 macro: %s" % peek)
            op = self._parse_byte_from_db(dbs[1]) << 8 | self._parse_byte_from_db(dbs[0])
            self._emit({'type': 'instruction', 'op': 'add', 'operands': ('AX', op), 'comment': comment})
            return self._parse_asm

        if operands == (131, 250):
            if comment:
                self._emit({'type': 'comment', 'value': comment})
                comment = None
            op = None
            while op is None:
                peek = self._peek()
                if peek['type'] == 'newline':
                    self._next()
                elif peek['type'] == 'comment':
                    self._next()
                    comment = peek['value']
                elif peek['type'] == 'db':
                    self._next()
                    op = self._parse_byte_from_db(peek['value'])
                else:
                    raise SyntaxError("Unexpected token while parsing INS86 macro: %s" % peek)
            self._emit({'type': 'instruction', 'op': 'cmp', 'operands': ('DX', op), 'comment': comment})
            return self._parse_asm

        if operands[0] == 115 and len(operands) == 2:
            self._emit({'type': 'instruction', 'op': 'jae', 'operands': (operands[1],), 'comment': comment})
            return self._parse_asm

        if operands == (254, 198):
            self._emit({'type': 'instruction', 'op': 'inc', 'operands': ('DH',), 'comment': comment})
            return self._parse_asm

        if operands == (138, 212):
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('DL', 'AH'), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (57, 30) and len(operands) == 3:
            self._emit({'type': 'instruction', 'op': 'cmp', 'operands': (operands[2], 'BX'), 'comment': comment})
            return self._parse_asm

        if operands[:2] == (255, 54) and len(operands) == 3:
            self._emit({'type': 'instruction', 'op': 'push', 'operands': (operands[2],), 'comment': comment})
            return self._parse_asm

        if operands == (255, 39):
            self._emit({'type': 'instruction', 'op': 'jmp', 'operands': ('[BX]',), 'comment': comment})
            return self._parse_asm

        if operands == (247, 211):
            self._emit({'type': 'instruction', 'op': 'not', 'operands': ('BX',), 'comment': comment})
            return self._parse_asm

        if operands == (11, 218):
            self._emit({'type': 'instruction', 'op': 'or', 'operands': ('BX', 'DX'), 'comment': comment})
            return self._parse_asm

        if operands == (35, 218):
            self._emit({'type': 'instruction', 'op': 'and', 'operands': ('BX', 'DX'), 'comment': comment})
            return self._parse_asm

        if operands == (51, 218):
            self._emit({'type': 'instruction', 'op': 'xor', 'operands': ('BX', 'DX'), 'comment': comment})
            return self._parse_asm

        if len(operands) == 2 and operands[0] == 186:
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('DX', operands[1]), 'comment': comment})
            return self._parse_asm

        if len(operands) == 2 and operands[0] == 177:
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('CL', operands[1]), 'comment': comment})
            return self._parse_asm

        if operands == (211, 234):
            self._emit({'type': 'instruction', 'op': 'shr', 'operands': ('DX', 'CL'), 'comment': comment})
            return self._parse_asm

        if operands == (139, 243):
            self._emit({'type': 'instruction', 'op': 'mov', 'operands': ('SI', 'BX'), 'comment': comment})
            return self._parse_asm

        debug = []
        for op in operands:
            if isinstance(op, int): debug.append('%02x' % op)
            else: debug.append(' %s ' % op)
        raise SyntaxError("Unknown arguments to INS86 macro: %s    %s" % (''.join(debug), operands))

    def _parse_macro_popr(self, comment):
        self._emit({'type': 'instruction', 'op': 'pop', 'operands': ['CX'], 'comment': comment})
        self._emit({'type': 'instruction', 'op': 'pop', 'operands': ['DX'], 'comment': None})
        return self._parse_asm

    def _parse_macro_call(self, token):
        macro = token['value']
        peek = self._peek()
        if peek['type'] == 'token' and peek['value'] == 'MACRO':
                return self._parse_macro(token)

        operands = []
        comment = None
        cur_operand = []
        while True:
            token = self._must_next("Expecting operands for %s" % macro)
            if token['type'] in ('token', 'number', 'string'):
                cur_operand.append(token)
            elif token['type'] == 'comment':
                comment = token['value']
                break
            elif token['type'] == 'newline':
                break
            elif token['type'] == 'comma':
                operands.append(cur_operand)
                cur_operand = []
                continue
            else:
                return self._error("Unexpected token: %s" % token)
        if cur_operand:
            operands.append(cur_operand)

        if macro == 'INS86':
            return self._parse_macro_ins86(operands, comment)
        if macro == 'MOVRI':
            return self._parse_macro_movri(operands, comment)
        if macro == 'POPR':
            return self._parse_macro_popr(comment)

        self._emit({'type': 'macro_call', 'identifier': macro, 'args': operands, 'comment': comment})
        return self._parse_asm

    def _parse_data(self, typ, token):
        if token['value'].startswith('OFFSET'):
            value = ('offset', self._parse_byte_from_db(token['value'][len("OFFSET"):].strip()))
        else:
            value = self._parse_byte_from_db(token['value'])

        self._emit({'type': typ, 'bytes': (value,)})
        return self._parse_asm

    def _parse_db(self, token):
        return self._parse_data('db', token)

    def _parse_dw(self, token):
        return self._parse_data('dw', token)

    def _parse_label_def(self, token):
        self._next() # Eat LABEL
        identifier = token['value']
        attrs = []
        comment = None
        while True:
            token = self._next()
            if token['type'] == 'token':
                attrs.append(token['value'])
            elif token['type'] == 'comment':
                comment = token['value']
            elif token['type'] == 'newline':
                break
            else:
                return self._error("Unexpected token type %s" % token['type'])
        self._emit({'type': 'label_def', 'identifier': identifier, 'attrs': attrs, 'comment': comment})
        return self._parse_asm

    def _parse_equ(self, token):
        self._next() # Eat EQU
        identifier = token['value']
        attrs = []
        comment = None
        while True:
            token = self._next()
            if token['type'] == 'token':
                attrs.append(token['value'])
            elif token['type'] == 'comment':
                comment = token['value']
                break
            elif token['type'] == 'newline':
                break
            else:
                return self._error("Unexpected token type %s" % token['type'])
        self._emit({'type': 'equ', 'identifier': identifier, 'attrs': attrs, 'comment': comment})
        return self._parse_asm

    def _parse_macro(self, token):
        self._next() # Eat MACRO
        identifier = token['value']
        args = []
        comment = None
        while True:
            token = self._next()
            if token is None:
                break
            if token['type'] == 'newline':
                break
            if token['type'] == 'comment':
                comment = token['value']
                break
            if token['type'] == 'comma':
                continue
            if token['type'] == 'token':
                args.append(token['value'])
            else:
                return self._error("Unexpected token type: %s" % token['type'])
        self.macro_args.append(args)
        self._emit({'type': 'macro', 'identifier': identifier, 'args': args, 'comment': comment})
        return self._parse_asm

    def _parse_if(self, typ):
        cond = []
        comment = None
        while True:
            token = self._next()
            if token['type'] in ('number', 'token'):
                cond.append(token['value'])
            elif token['type'] == 'comment':
                comment = token['value']
                break
            elif token['type'] == 'newline':
                break
            else:
                return self._error("Unexpected token type %s" % token['type'])
        if not cond:
            return self._error("If without condition")
        self._emit({'type': typ.lower(), 'cond': cond, 'comment': comment})
        return self._parse_asm

    def _parse_ifdif(self):
        ops = []
        comment = None
        while True:
            token = self._next()
            if token['type'] in ('number', 'token', 'string'):
                ops.append(token['value'])
            elif token['type'] == 'comment':
                comment = token['value']
                break
            elif token['type'] == 'comma':
                continue
            elif token['type'] == 'newline':
                break
            else:
                return self._error("Unexpected token type %s" % token['type'])
        if len(ops) != 2:
            return self._error("IFDIF requires 2 arguments")
        self._emit({'type': 'ifdif', 'ops': ops, 'comment': comment})
        return self._parse_asm

    def _parse_echo(self):
        msg = []
        while True:
            token = self._next()
            if token['type'] == 'newline':
                break
            msg.append(token)
        self._emit({'type': 'echo', 'msg': msg})
        return self._parse_asm

    def _parse_endm(self, escaping=False):
        if escaping:
            self._emit({'type': 'end_macro_escaped'})
        else:
            if self.rept_counter:
                self.rept_counter -= 1
                self._emit({'type': 'end_rept'})
            elif self.forc_counter:
                self.forc_counter -= 1
                self._emit({'type': 'end_forc'})
            elif self.macro_args:
                self.macro_args.popleft()
                self._emit({'type': 'end_macro'})
            else:
                return self._error("Not in macro, rept, or forc")
        return self._parse_asm

    def _parse_forc(self):
        self.forc_counter += 1
        comment = None
        args = []
        while True:
            token = self._next()
            if token['type'] == 'newline':
                break
            if token['type'] == 'comma':
                continue
            if token['type'] == 'comment':
                comment = token['value']
                break
            if token['type'] != 'token':
                return self._error("Expecting token, got %s" % token['type'])
            args.append(token)
        self._emit({'type': 'forc', 'args': args, 'comment': comment})
        return self._parse_asm

    def _parse_purge(self):
        token = self._must_next_type('token', "Macro identifier")
        self._emit({'type': 'purge', 'identifier': token['value']})
        return self._parse_asm

    def _parse_strip_macro(self):
        macro_token_count = 0
        while True:
            token = self._next()
            if token is None:
                return self._error("Expecting ENDM")
            if token['type'] == 'token' and token['value'] == 'MACRO':
                macro_token_count += 1
                if macro_token_count > 1:
                    return self._error("Nested macros not supported for stripping")
            if token['type'] == 'token' and token['value'] == 'ENDM':
                return self._parse_asm

    def _is_useless_macro(self, name):
        useless_macros = {
            'LDIR', 'LDDR', 'DJNZ', 'FSIGN', 'PUSHM', 'SYNCHK', 'OUTCHR', 'CHRGET',
            'COMPAR', 'PUSHR', 'INST', 'GETYPE', 'INS86', 'POPR', 'MOVRI',
        }
        if name in useless_macros:
            peek = self._peek()
            if peek['type'] == 'token' and peek['value'] == 'MACRO':
                return True
        return False

    def _parse_rept(self):
        count = self._must_next("Expecting argument to rept")
        if count['type'] not in ('token', 'number'):
            return self._error("Don't know how to parse REPT argument")
        self._emit({'type': 'rept', 'count': count})
        self.rept_counter += 1
        return self._parse_asm

    def _parse_asm(self):
        while True:
            token = self._next()
            if token is None:
                return None

            typ = token['type']

            if typ == 'newline':
                continue

            if typ == 'comment':
                self._emit(token)
                return self._parse_asm

            if typ == 'directive':
                return self._parse_directive(token)

            if typ == 'token':
                typ = token['value']
                if typ == 'CSEG':
                    return self._parse_cseg
                if typ == 'DSEG':
                    return self._parse_dseg
                if typ == 'ASSUME':
                    return self._parse_assume
                if typ == 'INCLUDE':
                    return self._parse_include
                if typ == 'PUBLIC':
                    return self._parse_public
                if typ == 'ORG':
                    return self._parse_org
                if typ == 'PAGE':
                    continue
                if typ in ('%OUT', 'ECHO'):
                    return self._parse_echo
                if typ == 'END':
                    break
                if typ == 'ENDM':
                    return self._parse_endm(escaping=False)
                if typ == '&ENDM':
                    return self._parse_endm(escaping=True)
                if typ == 'ENDIF':
                    self._emit({'type': 'end_if'})
                    return self._parse_asm
                if typ in ('IF', 'IFE', 'IFDEF', 'IFNDEF'):
                    return self._parse_if(typ)
                if typ == 'IFDIF':
                    return self._parse_ifdif
                if typ == 'IF1': # Hack!
                    self.token_queue.appendleft({'type': 'number', 'value': '1'})
                    return self._parse_if('IF')
                if typ == 'ELSE':
                    self._emit({'type': 'else'})
                    return self._parse_asm
                if typ == 'PURGE':
                    return self._parse_purge
                if typ in ('FORC', 'IRPC'):
                    return self._parse_forc
                if typ == 'REPT':
                    return self._parse_rept
                if token['value'].endswith(':'):
                    return self._parse_label(token)
                if self._is_x86_instruction(token):
                    return self._parse_x86_instruction(token)
                if self._is_useless_macro(typ):
                    self._emit({'type': 'comment', 'value': 'Stripped useless macro: %s' % typ})
                    return self._parse_strip_macro
                if self._is_macro(token):
                    return self._parse_macro_call(token)
                else:
                    peek = self._peek()
                    if peek['type'] == 'token' and peek['value'] == 'LABEL':
                        return self._parse_label_def(token)
                    if peek['type'] == 'token' and peek['value'] == 'EQU':
                        return self._parse_equ(token)

            if typ in ('title', 'subtitle'):
                self._emit(token)
                return self._parse_asm

            if typ == 'assign':
                return self._parse_assign(token)

            if typ == 'extern':
                return self._parse_extern(token)

            if typ == 'db':
                return self._parse_db(token)

            if typ == 'dw':
                return self._parse_dw(token)

            for args in self.macro_args:
                for arg in args:
                    if arg == token['value']:
                        self._emit({'type': 'macro_arg', 'identifier': arg})
                        return self._parse_asm

            return self._error("Don't know how to parse token %s" % token)
