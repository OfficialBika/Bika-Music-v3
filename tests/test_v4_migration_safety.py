import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from anony.core.mongo import MongoDB


class MigrationSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_writes_plan_and_never_drops_live_collections(self):
        db = object.__new__(MongoDB)
        db.db = MagicMock()
        db.usersdb = MagicMock()
        db.chatsdb = MagicMock()
        db.db.tgusersdb = MagicMock()
        db.usersdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([{"_id": 1}, {"user_id": 1}]))
        db.db.tgusersdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([{"_id": 2}]))
        db.chatsdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([{"_id": -1001}]))
        db.usersdb.count_documents = AsyncMock(return_value=0)
        db.db.tgusersdb.count_documents = AsyncMock(return_value=0)
        db.chatsdb.count_documents = AsyncMock(return_value=0)
        db.db.__getitem__ = MagicMock()
        cfg = MagicMock()
        cfg.MIGRATION_DRY_RUN = True
        cfg.MIGRATION_BACKUP_DIR = "/tmp/v4-migration-test"
        with patch("anony.core.mongo.config", cfg), patch("anony.core.mongo.logger"):
            await db.migrate_coll()
        db.usersdb.drop.assert_not_called()
        db.db.tgusersdb.drop.assert_not_called()
        db.chatsdb.drop.assert_not_called()
        db.usersdb.insert_many.assert_not_called()
        db.chatsdb.insert_many.assert_not_called()

    async def test_invalid_ids_abort_migration(self):
        db = object.__new__(MongoDB)
        db.db = MagicMock()
        db.usersdb = MagicMock()
        db.chatsdb = MagicMock()
        db.db.tgusersdb = MagicMock()
        db.usersdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([{"_id": "invalid"}]))
        db.db.tgusersdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([]))
        db.chatsdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([]))
        cfg = MagicMock()
        cfg.MIGRATION_DRY_RUN = True
        cfg.MIGRATION_BACKUP_DIR = "/tmp/v4-migration-test"
        with patch("anony.core.mongo.config", cfg), patch("anony.core.mongo.logger"):
            with self.assertRaises(ValueError):
                await db.migrate_coll()
        db.usersdb.drop.assert_not_called()
        db.chatsdb.drop.assert_not_called()

    async def test_staging_requires_verified_backup_confirmation(self):
        db = object.__new__(MongoDB)
        db.db = MagicMock()
        db.usersdb = MagicMock()
        db.chatsdb = MagicMock()
        db.db.tgusersdb = MagicMock()
        db.usersdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([]))
        db.db.tgusersdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([]))
        db.chatsdb.find = MagicMock(side_effect=lambda *a, **k: self._cursor([]))
        cfg = MagicMock()
        cfg.MIGRATION_DRY_RUN = False
        cfg.MIGRATION_BACKUP_DIR = "/tmp/v4-migration-test"
        cfg.MIGRATION_CONFIRM_APPLY = ""
        with patch("anony.core.mongo.config", cfg), patch("anony.core.mongo.logger"):
            with self.assertRaises(RuntimeError):
                await db.migrate_coll()
        db.usersdb.drop.assert_not_called()
        db.chatsdb.drop.assert_not_called()

    @staticmethod
    def _cursor(rows):
        async def iterator():
            for row in rows:
                yield row
        return iterator()


if __name__ == "__main__":
    unittest.main()
