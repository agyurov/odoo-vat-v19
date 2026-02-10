import unittest

import pandas as pd

from src.vat_exporter.journal import get_accounting_period


class GetAccountingPeriodTests(unittest.TestCase):
    def test_iso_dates(self):
        df = pd.DataFrame({"date": ["2026-01-10", "2026-01-31", "2025-12-01"]})

        period = get_accounting_period(df)

        self.assertEqual(period, "202601")
        self.assertEqual(str(df.loc[1, "date_dt"].date()), "2026-01-31")

    def test_eu_dates(self):
        df = pd.DataFrame({"date": ["10/01/2026", "31/01/2026", "01/12/2025"]})

        period = get_accounting_period(df)

        self.assertEqual(period, "202601")
        self.assertEqual(str(df.loc[1, "date_dt"].date()), "2026-01-31")

    def test_invalid_dates_include_sample_values_and_assumed_format(self):
        df = pd.DataFrame(
            {
                "date": [
                    "2026-01-10",
                    "31/01/2026",
                    "2026/02/20",
                    "31-01-2026",
                    "not-a-date",
                ]
            }
        )

        with self.assertRaises(ValueError) as ctx:
            get_accounting_period(df)

        message = str(ctx.exception)
        self.assertIn("Assumed format: mixed (YYYY-MM-DD and/or DD/MM/YYYY)", message)
        self.assertIn("2026/02/20", message)
        self.assertIn("31-01-2026", message)
        self.assertIn("not-a-date", message)


if __name__ == "__main__":
    unittest.main()
