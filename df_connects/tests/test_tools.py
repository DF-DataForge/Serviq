# -*- coding: utf-8 -*-
from odoo.tests import BaseCase, tagged

from ..models.tools import get_path, normalize_ean, to_float, to_text


@tagged('post_install', '-at_install')
class TestTools(BaseCase):

    def test_normalize_ean(self):
        self.assertEqual(normalize_ean('5410013108009'), '5410013108009')
        self.assertEqual(normalize_ean(' 5410013-108009 '), '5410013108009')
        self.assertEqual(normalize_ean(5410013108009), '5410013108009')
        self.assertEqual(normalize_ean(5410013108009.0), '5410013108009')
        # UPC-A and GTIN-14 with leading 0 become EAN-13.
        self.assertEqual(normalize_ean('036000291452'), '0036000291452')
        self.assertEqual(normalize_ean('05410013108009'), '5410013108009')
        self.assertEqual(normalize_ean('96385074'), '96385074')
        # Wrong check digit, wrong length, empty, letters, all zeros.
        self.assertFalse(normalize_ean('5410013108008'))
        self.assertFalse(normalize_ean('54100131'))
        self.assertFalse(normalize_ean('12345'))
        self.assertFalse(normalize_ean(''))
        self.assertFalse(normalize_ean(None))
        self.assertFalse(normalize_ean('ABC4100131080'))
        self.assertFalse(normalize_ean('0000000000000'))

    def test_get_path(self):
        data = {'data': {'items': [{'price': {'amount': 5}}, {'x': 1}]}}
        self.assertEqual(get_path(data, 'data.items[0].price.amount'), 5)
        self.assertEqual(get_path(data, 'data.items.1.x'), 1)
        self.assertEqual(get_path(data, 'data.items[-1].x'), 1)
        self.assertIsNone(get_path(data, 'data.items[5].x'))
        self.assertIsNone(get_path(data, 'data.missing'))
        self.assertIs(get_path(data, ''), data)
        self.assertEqual(get_path(data, 'nope', 'default'), 'default')
        # Alternatives: the first one found.
        self.assertEqual(get_path(data, 'gtin|data.items.1.x'), 1)
        self.assertEqual(get_path(data, 'a|b', 'none'), 'none')

    def test_to_float(self):
        self.assertEqual(to_float('1.234,56'), 1234.56)
        self.assertEqual(to_float('1,234.56'), 1234.56)
        self.assertEqual(to_float('12,5'), 12.5)
        self.assertEqual(to_float('€ 7.50'), 7.5)
        self.assertEqual(to_float(3), 3.0)
        self.assertEqual(to_float(None), 0.0)
        self.assertEqual(to_float('n/a'), 0.0)

    def test_to_text(self):
        self.assertEqual(to_text(' A1 '), 'A1')
        self.assertEqual(to_text(123.0), '123')
        self.assertFalse(to_text(''))
        self.assertFalse(to_text(None))
