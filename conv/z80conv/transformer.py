#!/usr/bin/python
# Copyright (c) 2020 Leandro Pereira <leandro@hardinfo.org>
# Licensed under GPLv2.

from collections import deque
from itertools import tee, chain, repeat
import re


def windowed(seq, n, fillvalue=None, step=1):
    """Return a sliding window of width *n* over the given iterable.
        >>> all_windows = windowed([1, 2, 3, 4, 5], 3)
        >>> list(all_windows)
        [(1, 2, 3), (2, 3, 4), (3, 4, 5)]
    When the window is larger than the iterable, *fillvalue* is used in place
    of missing values:
        >>> list(windowed([1, 2, 3], 4))
        [(1, 2, 3, None)]
    Each window will advance in increments of *step*:
        >>> list(windowed([1, 2, 3, 4, 5, 6], 3, fillvalue='!', step=2))
        [(1, 2, 3), (3, 4, 5), (5, 6, '!')]
    To slide into the iterable's items, use :func:`chain` to add filler items
    to the left:
        >>> iterable = [1, 2, 3, 4]
        >>> n = 3
        >>> padding = [None] * (n - 1)
        >>> list(windowed(chain(padding, iterable), 3))
        [(None, None, 1), (None, 1, 2), (1, 2, 3), (2, 3, 4)]

    Shamelessly stolen from more-itertools.
    """
    if n < 0:
        raise ValueError('n must be >= 0')
    if n == 0:
        yield tuple()
        return
    if step < 1:
        raise ValueError('step must be >= 1')

    window = deque(maxlen=n)
    i = n
    for _ in map(window.append, seq):
        i -= 1
        if not i:
            i = step
            yield tuple(window)

    size = len(window)
    if size < n:
        yield tuple(chain(window, repeat(fillvalue, n - size)))
    elif 0 < i < min(step, n):
        window += (fillvalue,) * i
        yield tuple(window)


class Transformer:
    def __init__(self, parser):
        self.parser = parser
        self.inverted_jumps = {
            'JZ': 'JNZ',
            'JAE': 'JNAE',
            'JB': 'JNB',
            'JS': 'JNS',
            'JNZ': 'JZ',
            'JNAE': 'JAE',
            'JNB': 'JB',
            'JNS': 'JS',
        }
        self.autogenlabel_re = re.compile('^\\?\\?L\\d+$')

    def extern(self, identifier):
        return self.parser.externs.get(identifier)

    def _match(self, window, *match):
        def _match_op_tuple(code_oper, pattern_oper):
            for pattern, code in zip(pattern_oper, code_oper):
                if pattern is None:
                    continue
                if isinstance(pattern, set):
                    if not code in pattern:
                        return False
                elif isinstance(pattern, str):
                    if code != pattern:
                        return False
                elif isinstance(pattern, tuple):
                    if type(code) != type(pattern):
                        return False
                    if not _match_op_tuple(code, pattern):
                        return False
                else:
                    raise NotImplementedError("Pattern of type %s not supported" % type(pattern))
            return True

        def _match_op(code, pattern):
            if code is None:
                return False

            if code['type'] == 'label':
                return pattern == ('??L:', None) and self.autogenlabel_re.fullmatch(code['identifier'])

            code_op, code_oper = code['op'], code['operands']
            pattern_op, pattern_oper = pattern

            code_op = code_op.upper()

            if isinstance(pattern_op, str):
                op_match = code_op == pattern_op
            elif isinstance(pattern_op, set):
                op_match = code_op in pattern_op
            elif pattern_op is None:
                op_match = True
            else:
                raise NotImplementedError("Operation of type %s not supported" % type(pattern_op))

            if isinstance(pattern_oper, tuple):
                oper_match = _match_op_tuple(code_oper, pattern_oper)
            elif pattern_oper is None:
                oper_match = True
            else:
                raise NotImplementedError("Operand of type %s not supported" % type(pattern_oper))

            return op_match and oper_match

        return window if all(_match_op(wop, mop) for wop, mop in zip(window, match)) else ()

    def _calculate_transform_dict(self, tokens):
        trans_dict = {}

        def fill_dict(window, *new_tokens):
            if len(new_tokens) > len(window):
                raise NotImplementedError("Can't insert more instructions than the window size")
            if not any(token['id'] in trans_dict for token in window):
                for token in window:
                    trans_dict[token['id']] = None
                for window_token, new_token in zip(window, new_tokens):
                    trans_dict[window_token['id']] = new_token

        tokens = list(token for token in tokens if token['type'] in {'label', 'instruction'})

        for window in windowed(tokens, 5):
            if window[0] is None:
                break
            matched = self._match(window, ('LAHF', ()), ('ADD', None), ('RCR', ('SI', None)), ('SAHF', ()), ('RCL', ('SI', None)))
            if matched and matched[2]['operands'] == matched[4]['operands']:
                fill_dict(matched,
                    {'op': 'savepsw', 'operands': ('reg',)},
                    {'op': matched[1]['op'], 'operands': matched[1]['operands']},
                    {'op': 'restorepsw', 'operands': ('reg',)})
                continue

        for window in windowed(tokens, 3):
            matched = self._match(window, ({'JZ', 'JAE', 'JB', 'JS', 'JNZ', 'JNAE', 'JNB', 'JNS'}, (('SHORT', None),)), ({'JMP', 'CALL'}, None), ('??L:', None))
            if matched and self.autogenlabel_re.fullmatch(matched[0]['operands'][0][1]):
                fill_dict(matched, {'op': matched[1]['op'] + '_' + self.inverted_jumps[matched[0]['op']][1:], 'operands': matched[1]['operands']})
                continue

            matched = self._match(window, ('POP', ('AX',)), ('XCHG', ('AL', 'AH')), ('SAHF', ()))
            if matched:
                fill_dict(matched, {'op': 'restorepsw', 'operands': ('stack',)})
                continue

            matched = self._match(window, ('POP', ('SI',)), ('XCHG', ('SI', 'BX')), ('PUSH', ('SI',)))
            if matched:
                fill_dict(matched, {'op': 'xthl', 'operands': ()})
                continue

            matched = self._match(window, ('XOR', ('AH', 'AH')), ('CMP', ('AL', None)), ('JZ', None))
            if matched:
                fill_dict(matched, {'op': 'cmp', 'operands': matched[1]['operands']}, {'op': 'jz', 'operands': matched[2]['operands']})
                continue

            matched = self._match(window, ('POP', ('AX',)), ('OR', ('AH', 'AH')), ('JZ', None))
            if matched:
                fill_dict(matched, {'op': 'jz', 'operands': matched[2]['operands']})
                continue

            matched = self._match(window, ('LAHF', ()), ({'INC', 'DEC'}, ({'BX', 'CX', 'DX', 'SP'},)), ('SAHF', ()))
            if matched:
                fill_dict(matched, {'op': matched[1]['op'], 'operands': matched[1]['operands']})
                continue

            matched = self._match(window, ('XOR', ('AH', 'AH')), ('MUL', ('DX',)), ('MOV', ('DH', 'DL')))
            if matched:
                fill_dict(matched, {'op': 'mul16by8', 'operands': ('AL', 'DX', 'DL')})
                continue

        for window in windowed(tokens, 4):
            matched = self._match(window, ('LAHF', ()), ('XCHG', ('AL', 'AH')), ('PUSH', ('AX',)), ('XCHG', ('AL', 'AH')))
            if matched:
                fill_dict(matched, {'op': 'savepsw', 'operands': ('stack',)})
                continue

        for window in windowed(tokens, 2):
            matched = self._match(window, ({'DEC', 'DECB'}, ('CH',)), ('JNZ', (('SHORT', None),)))
            if matched:
                fill_dict(matched, {'op': 'djnz', 'operands': matched[1]['operands']})
                continue

            matched = self._match(window, ({'JZ', 'JAE', 'JB', 'JS', 'JNZ', 'JNAE', 'JNB', 'JNS'}, (('SHORT', '$+3'),)), ('RET', ()))
            if matched:
                fill_dict(matched, {'op': 'ret_' + self.inverted_jumps[matched[0]['op']], 'operands': ()})
                continue

            matched = self._match(window, ('POP', ('AX',)), ('SAHF', ()))
            if matched:
                fill_dict(matched, {'op': 'POP', 'operands': ('AX',)})
                continue

            matched = self._match(window, ('LAHF', ()), ('PUSH', ('AX',)))
            if matched:
                fill_dict(matched, {'op': 'PUSH', 'operands': ('AX',)})
                continue

        for window in windowed(tokens, 1):
            matched = self._match(window, ({'REP', 'REPE', 'REPZ', 'REPNZ', 'REPNE'}, ({'LODSB', 'LODSW', 'STOSB', 'STOSW', 'MOVSB', 'MOVSW', 'SCASB', 'SCASW', 'CMPSB'},)))
            if matched:
                fill_dict(matched, {'op': matched[0]['op'] + '_' + matched[0]['operands'][0], 'operands': ()})
                continue

        return trans_dict

    def transform(self):
        def annotate_with_id():
            for id, token in enumerate(self.parser.parse()):
                token['id'] = id
                yield token

        left, right = tee(annotate_with_id())
        trans_dict = self._calculate_transform_dict(left)
        for token in right:
            if token['id'] in trans_dict:
                trans = trans_dict[token['id']]
                if trans is None:
                    comment = token.get('comment', None)
                    if comment is not None:
                        yield {'type': 'comment', 'value': comment}
                    continue

                token.update(trans)

            yield token
