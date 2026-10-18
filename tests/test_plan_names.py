"""Offline checks that plan labels change without changing policy meaning."""

import unittest

from retail_copilot.documents import load_settings
from retail_copilot.plan_names import canonical_plan_names, display_plan_names, plan_aliases


class PlanNameTests(unittest.TestCase):
    def setUp(self):
        self.aliases = plan_aliases(load_settings())

    def test_config_maps_the_two_names_in_both_directions(self):
        self.assertEqual(self.aliases, {"Practice Basic": "Connect Essential", "Practice Plus": "Connect Plus"})
        text = "Compare Connect Essential and Connect Plus."
        canonical = canonical_plan_names(text, self.aliases)
        self.assertEqual(canonical, "Compare Practice Basic and Practice Plus.")
        self.assertEqual(display_plan_names(canonical, self.aliases), text)

    def test_case_and_punctuation_are_accepted_without_partial_replacements(self):
        self.assertEqual(canonical_plan_names("CONNECT ESSENTIAL, connect plus?", self.aliases),
                         "Practice Basic, Practice Plus?")
        self.assertEqual(display_plan_names("practice basic; PRACTICE PLUS's allowance", self.aliases),
                         "Connect Essential; Connect Plus's allowance")
        for text in ("Connect Essentialish", "MyConnect Essential", "Connect Essential-Pro", "x_Connect Essential"):
            self.assertEqual(canonical_plan_names(text, self.aliases), text)
        for text in ("Practice Basically", "MyPractice Basic", "Practice Plus-Pro", "x_Practice Plus"):
            self.assertEqual(display_plan_names(text, self.aliases), text)

    def test_only_adjacent_fictional_prefix_is_removed_from_visible_names(self):
        text = "The fictional Practice Basic plan has 10 GB; FICTIONAL Practice Plus has 30 GB."
        self.assertEqual(display_plan_names(text, self.aliases),
                         "The Connect Essential plan has 10 GB; Connect Plus has 30 GB.")
        separate = "Fictional policies remain illustrative. No monthly prices are defined. Practice Plus has 30 GB."
        self.assertEqual(display_plan_names(separate, self.aliases),
                         "Fictional policies remain illustrative. No monthly prices are defined. Connect Plus has 30 GB.")
        self.assertEqual(canonical_plan_names("fictional Connect Essential", self.aliases), "fictional Practice Basic")

    def test_collisions_and_overlapping_whole_names_are_rejected(self):
        for mapping in (
            {"Practice Basic": "Connect", "Practice Plus": "connect"},
            {"Practice Basic": "practice basic"},
            {"Practice Basic": "Connect", "practice basic": "Other"},
            {"Practice Basic": "Practice Plus", "Practice Plus": "Other"},
            {"Practice Basic": "Connect", "Practice Plus": "Connect Plus"},
        ):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                plan_aliases({"plan_aliases": mapping})

    def test_invalid_configuration_is_rejected_before_conversion(self):
        for mapping in (None, [], {"": "Connect"}, {"Practice Basic": 1},
                        {"Practice Basic": " Connect"}, {"Practice Basic": "Connect  Essential"},
                        {"Practice Basic": "<b>Connect</b>"}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                plan_aliases({"plan_aliases": mapping})

    def test_unknown_names_and_disabled_aliases_remain_unchanged(self):
        text = "Does Connect Premium include more data?"
        self.assertEqual(canonical_plan_names(text, self.aliases), text)
        self.assertEqual(display_plan_names(text, self.aliases), text)
        self.assertEqual(plan_aliases({}), {})
        self.assertEqual(canonical_plan_names("Connect Plus", {}), "Connect Plus")
        self.assertEqual(display_plan_names("Practice Plus", {}), "Practice Plus")


if __name__ == "__main__":
    unittest.main()
