import unittest

from scrape_honda_bigwing import allowed_detail_url, detail_name, normalized_model_name, parse_catalog, parse_detail


class HondaBigWingParserTests(unittest.TestCase):
    def test_catalog_only_accepts_same_site_model_cards(self):
        html = b'''<a href="https://www.thaihonda.co.th/hondabigbike/motorcycle/sport/cbr-2026">
          <span class="product-name">CBR</span><span class="price">100,000</span></a>
          <a href="https://example.com/hondabigbike/motorcycle/sport/other">
          <span class="product-name">Other</span></a>'''
        models = parse_catalog(html)
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["name"], "CBR")
        self.assertEqual(models[0]["url_year_hint"], 2026)
        self.assertFalse(allowed_detail_url("https://www.thaihonda.co.th/hondabigbike/motorcycle/sport/cbr?x=1"))

    def test_detail_reads_specs_but_skips_unknown_values(self):
        html = '''<div class="spec"><li><div class="accordion-title">Engine</div>
          <table><tr><td>Capacity</td><td>471.03</td></tr>
          <tr><td>Torque</td><td>-</td></tr></table></li></div>'''.encode()
        self.assertEqual(parse_detail(html), [{"group": "Engine", "label": "Capacity", "value": "471.03"}])
        self.assertEqual(parse_detail(b"<div>no specs</div>"), [])
        self.assertEqual(detail_name(b"<script>let _bikeModel = 'CBR500R E-Clutch';</script>"),
                         "CBR500R E-Clutch")
        self.assertEqual(detail_name(b"<title>Honda - CB1300 BolD&#039;OR</title>"), "CB1300 BolD'OR")
        self.assertEqual(normalized_model_name("NEW CB1300 Super BolD'OR"),
                         normalized_model_name("CB1300 SUPER BOLDOR"))


if __name__ == "__main__":
    unittest.main()
