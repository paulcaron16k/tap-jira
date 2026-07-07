import unittest
from tap_jira.streams import transform_user_date

TEST_SET = {
    "12/okt/2022": "2022-10-12",
    "02/abr/2021": "2021-04-02"
}
class TestUserDateTransform(unittest.TestCase):
    """
    Verify that tap successfully transform date value of different regional languages.
    """
    def test_user_date_for_any_region(self):

        for actual_test_date, expected_test_date in TEST_SET.items():
            self.assertEqual(transform_user_date(actual_test_date), expected_test_date)

    def test_unparseable_or_empty_returns_none(self):
        """Unparseable / empty / None dates return null instead of crashing on
        None.strftime (dateparser.parse returns None for values it can't parse)."""
        for bad in (None, "", "not a date", "13/xyz/2022"):
            self.assertIsNone(transform_user_date(bad))

