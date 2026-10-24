import os
import unittest
from unittest.mock import patch


class ConfigTests(unittest.TestCase):
    def test_safe_defaults(self):
        from config import Config

        with patch.dict(os.environ, {}, clear=True):
            cfg = Config()
        self.assertFalse(cfg.ENABLE_EVAL)
        self.assertTrue(cfg.EVAL_AUDIT)
        self.assertTrue(cfg.MIGRATION_DRY_RUN)
        self.assertGreaterEqual(cfg.PLAYBACK_SKIP_LIMIT, 1)
        self.assertGreaterEqual(cfg.PLAYBACK_RETRY_LIMIT, 1)

    def test_invalid_integers_fall_back_and_limits_are_clamped(self):
        from config import Config

        with patch.dict(os.environ, {
            "PLAYBACK_SKIP_LIMIT": "-2",
            "PLAYBACK_RETRY_LIMIT": "n/a",
            "BROADCAST_RETRY_LIMIT": "-99",
            "OLD_POST_CLEAN_DELAY": "0",
        }, clear=False):
            cfg = Config()
        self.assertEqual(cfg.PLAYBACK_SKIP_LIMIT, 1)
        self.assertEqual(cfg.PLAYBACK_RETRY_LIMIT, 3)
        self.assertEqual(cfg.BROADCAST_RETRY_LIMIT, 0)
        self.assertEqual(cfg.OLD_POST_CLEAN_DELAY, 1)


if __name__ == "__main__":
    unittest.main()
