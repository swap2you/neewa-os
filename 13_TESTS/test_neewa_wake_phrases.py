import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "12_SCRIPTS" / "neewa_wake_phrases.py"
SPEC = importlib.util.spec_from_file_location("neewa_wake_phrases", MODULE_PATH)
phrases = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(phrases)

CANONICAL_PHRASE = phrases.CANONICAL_PHRASE
NEGATIVE_EXAMPLES = phrases.NEGATIVE_EXAMPLES
PRONUNCIATION_ALIASES = phrases.PRONUNCIATION_ALIASES
enrolled_phrases = phrases.enrolled_phrases
fires_once = phrases.fires_once
is_negative_example = phrases.is_negative_example
normalize_phrase = phrases.normalize_phrase
phrase_profile_map = phrases.phrase_profile_map
sherpa_keyword_lines = phrases.sherpa_keyword_lines


class WakePhrasePolicyTests(unittest.TestCase):
    def test_canonical_is_hey_neewa(self):
        self.assertEqual(CANONICAL_PHRASE, "hey neewa")
        self.assertEqual(enrolled_phrases()[0], "hey neewa")

    def test_aliases_are_enrolled_once(self):
        phrases = enrolled_phrases()
        self.assertEqual(
            phrases,
            ["hey neewa", "hey niva", "hey neeva", "hey neva"],
        )
        self.assertEqual(len(phrases), len(set(phrases)))
        for alias in PRONUNCIATION_ALIASES:
            self.assertIn(normalize_phrase(alias), phrases)

    def test_duplicate_aliases_do_not_enroll_twice(self):
        phrases = enrolled_phrases("hey neewa", ["hey niva", "HEY NIVA", " hey neewa "])
        self.assertEqual(phrases.count("hey niva"), 1)
        self.assertEqual(phrases.count("hey neewa"), 1)

    def test_negatives_are_not_enrolled(self):
        enrolled = set(enrolled_phrases())
        for phrase in NEGATIVE_EXAMPLES:
            self.assertTrue(is_negative_example(phrase))
            self.assertNotIn(normalize_phrase(phrase), enrolled)
        self.assertNotIn("hey nina", enrolled)
        self.assertNotIn("hey nio", enrolled)

    def test_aliases_map_to_the_same_profile(self):
        mapping = phrase_profile_map(profile="default")
        self.assertTrue(mapping)
        self.assertEqual(set(mapping.values()), {"default"})
        self.assertEqual(mapping["hey neewa"], mapping["hey niva"])

    def test_sherpa_keyword_display_names(self):
        lines = sherpa_keyword_lines()
        self.assertEqual(lines, ["@HEY_NEEWA", "@HEY_NIVA", "@HEY_NEEVA", "@HEY_NEVA"])
        self.assertTrue(all(" " not in line for line in lines))

    def test_no_duplicate_trigger_inside_cooldown(self):
        self.assertTrue(fires_once([(0.0, "hey neewa"), (2.1, "hey neewa")]))
        self.assertFalse(fires_once([(0.0, "hey niva"), (0.4, "hey niva")]))
        self.assertTrue(fires_once([(0.0, "hey neewa"), (0.4, "hey niva")]))

    def test_hermes_alias_patch_is_idempotent(self):
        import importlib.util
        import tempfile

        apply_path = ROOT / "12_SCRIPTS" / "apply_neewa_wake_aliases.py"
        spec = importlib.util.spec_from_file_location("apply_neewa_wake_aliases", apply_path)
        apply = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(apply)
        fixture = (
            "        phrase = str(ww._get(cfg, \"phrase\") or \"hey hermes\").strip()\n"
            "        phrase_map: Dict[str, str] = {phrase: ww._active_profile_name()}\n"
            "        if bool(cfg.get(\"profile_routing\", True)):\n"
            "            pass\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wake_word_engines.py"
            path.write_text(fixture, encoding="utf-8")
            first = apply.patch_engine(path)
            second = apply.patch_engine(path)
            text = path.read_text(encoding="utf-8")
        self.assertTrue(first.startswith("patched"))
        self.assertEqual(second, "already_patched")
        self.assertIn("NEEWA_WAKE_ALIASES", text)
        self.assertIn('cfg.get("aliases")', text)
        self.assertIn("phrase_map.setdefault(_name, active_profile)", text)

    def test_config_alias_block_insert(self):
        import importlib.util
        import tempfile

        apply_path = ROOT / "12_SCRIPTS" / "apply_neewa_wake_aliases.py"
        spec = importlib.util.spec_from_file_location("apply_neewa_wake_aliases", apply_path)
        apply = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(apply)
        src = "wake_word:\n  enabled: true\n  phrase: hey neewa\n  capture: client\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(src, encoding="utf-8")
            first = apply.ensure_aliases_config(path)
            second = apply.ensure_aliases_config(path)
            text = path.read_text(encoding="utf-8")
        self.assertTrue(first.startswith("config_updated"))
        self.assertEqual(second, "aliases_present")
        self.assertIn("hey niva", text)
        self.assertIn("hey neeva", text)
        self.assertIn("hey neva", text)
        self.assertIn("phrase: hey neewa", text)


if __name__ == "__main__":
    unittest.main()
