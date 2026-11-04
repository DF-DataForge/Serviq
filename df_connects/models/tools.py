# -*- coding: utf-8 -*-
"""Helpers without database access: EAN / GTIN validation and reading values
out of the JSON a supplier returns."""
import re

# Valid GTIN lengths: EAN-8, UPC-A (GTIN-12), EAN-13, GTIN-14.
GTIN_LENGTHS = (8, 12, 13, 14)


def gtin_check_digit_ok(code):
    """True when the last digit of ``code`` (digits only) is the GS1 check
    digit of the others."""
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    # From the right, weights 3, 1, 3, 1, ... on the body.
    total = sum(d * (3 if i % 2 == 0 else 1)
                for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize_ean(value):
    """Return the EAN / GTIN in ``value`` as a 13 digit string (14 for a
    GTIN-14 that does not start with 0), or False when ``value`` is empty or
    not a valid EAN.

    UPC-A (12) is padded to EAN-13, so the same article gets the same UUID
    whether a supplier sends it as UPC or as EAN. EAN-8 is kept as is: it is
    a different number space and padding it would not match a barcode.
    """
    if value is None or value is False:
        return False
    if isinstance(value, float):
        # Some APIs send the EAN as a JSON number.
        if not value.is_integer():
            return False
        value = int(value)
    code = re.sub(r'[\s-]', '', str(value))
    if not code.isdigit() or len(code) not in GTIN_LENGTHS:
        return False
    if not gtin_check_digit_ok(code) or not int(code):
        return False
    if len(code) == 12:
        code = '0' + code
    elif len(code) == 14 and code.startswith('0'):
        code = code[1:]
    return code


_PATH_TOKEN = re.compile(r'[^.\[\]]+|\[\d+\]')


def get_path(data, path, default=None):
    """Value at ``path`` in ``data``: keys separated by dots, list indexes in
    brackets or as a number (``data.items``, ``prices[0].amount``,
    ``prices.0.amount``). An empty path returns ``data`` itself.

    Several paths can be given separated by "|": the first one found (not
    None) is returned, e.g. ``ean|gtin|barcode``."""
    if not path:
        return data
    if '|' in path:
        for alternative in path.split('|'):
            value = get_path(data, alternative.strip(), None)
            if value is not None:
                return value
        return default
    current = data
    for token in _PATH_TOKEN.findall(path.strip()):
        if token.startswith('['):
            token = token[1:-1]
        if isinstance(current, dict):
            if token not in current:
                return default
            current = current[token]
        elif isinstance(current, (list, tuple)) and token.lstrip('-').isdigit():
            index = int(token)
            if not -len(current) <= index < len(current):
                return default
            current = current[index]
        else:
            return default
    return current


def to_float(value, default=0.0):
    """Number in ``value``: accepts JSON numbers and strings with a decimal
    comma or point and thousands separators ("1.234,56", "1,234.56")."""
    if value is None or value is False or value == '':
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r'[^\d,.\-]', '', str(value))
    if not text:
        return default
    if ',' in text and '.' in text:
        # The separator that comes last is the decimal one.
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except ValueError:
        return default


def to_text(value):
    """Value as stripped text, False when empty."""
    if value is None or value is False:
        return False
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or False
