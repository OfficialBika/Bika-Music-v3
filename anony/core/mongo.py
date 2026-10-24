# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# V4 hardening: preserve Bika schema while making legacy migration non-destructive.

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from random import randint
from time import time

from pymongo import AsyncMongoClient

from anony import config, logger, userbot


class MongoDB:
    def __init__(self):
        self.mongo = AsyncMongoClient(config.MONGO_URL, serverSelectionTimeoutMS=12500)
        self.db = self.mongo.Anon

        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.cmd_delete = []
        self.auto_delete_play = []
        self.loop = {}
        self.notified = []
        self.cache = self.db.cache
        self.logger = False

        self.assistant = {}
        self.assistantdb = self.db.assistant
        self.auth = {}
        self.authdb = self.db.auth
        self.chats = []
        self.chatsdb = self.db.chats
        self.lang = {}
        self.langdb = self.db.lang
        self.users = []
        self.usersdb = self.db.users
        self._state_lock = asyncio.Lock()

    async def connect(self) -> None:
        try:
            start = time()
            await self.mongo.admin.command("ping")
            logger.info("Database connection successful. (%.2fs)", time() - start)
            await self.load_cache()
        except Exception as exc:
            raise SystemExit(f"Database connection failed: {type(exc).__name__}") from exc

    async def close(self) -> None:
        await self.mongo.close()
        logger.info("Database connection closed.")

    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.active_calls

    async def add_call(self, chat_id: int) -> None:
        self.active_calls[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls.get(chat_id, 0))

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        from anony.helpers._admins import reload_admins
        if chat_id not in self.admin_list or reload:
            self.admin_list[chat_id] = await reload_admins(chat_id)
        return self.admin_list[chat_id]

    async def get_loop(self, chat_id: int) -> int:
        return self.loop.get(chat_id, 0)

    async def set_loop(self, chat_id: int, count: int) -> None:
        self.loop[chat_id] = max(0, int(count))

    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        async with self._state_lock:
            await self.authdb.update_one(
                {"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True
            )
            users.add(user_id)

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        async with self._state_lock:
            await self.authdb.update_one(
                {"_id": chat_id}, {"$pull": {"user_ids": user_id}}, upsert=True
            )
            users.discard(user_id)

    async def set_assistant(self, chat_id: int) -> int:
        if not userbot.clients:
            raise RuntimeError("No userbot sessions are connected")
        num = randint(1, len(userbot.clients))
        await self.assistantdb.update_one(
            {"_id": chat_id}, {"$set": {"num": num}}, upsert=True
        )
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id: int):
        from anony import anon
        if not anon.clients:
            raise RuntimeError("No PyTgCalls assistant clients are connected")
        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            num = doc.get("num") if doc else None
            if not isinstance(num, int) or num < 1 or num > len(anon.clients):
                num = await self.set_assistant(chat_id)
            self.assistant[chat_id] = num
        return anon.clients[self.assistant[chat_id] - 1]

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)
        num = self.assistant[chat_id]
        if num < 1 or num > len(userbot.clients):
            num = await self.set_assistant(chat_id)
        return {1: userbot.one, 2: userbot.two, 3: userbot.three}.get(num)

    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            async with self._state_lock:
                await self.cache.update_one(
                    {"_id": "bl_chats"}, {"$addToSet": {"chat_ids": chat_id}}, upsert=True
                )
                if chat_id not in self.blacklisted:
                    self.blacklisted.append(chat_id)
        else:
            await self.cache.update_one(
                {"_id": "bl_users"}, {"$addToSet": {"user_ids": chat_id}}, upsert=True
            )

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            async with self._state_lock:
                await self.cache.update_one(
                    {"_id": "bl_chats"}, {"$pull": {"chat_ids": chat_id}}, upsert=True
                )
                self.blacklisted = [item for item in self.blacklisted if item != chat_id]
        else:
            await self.cache.update_one(
                {"_id": "bl_users"}, {"$pull": {"user_ids": chat_id}}, upsert=True
            )

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return list(self.blacklisted)
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def add_chat(self, chat_id: int) -> None:
        async with self._state_lock:
            await self.chatsdb.update_one(
                {"_id": chat_id}, {"$setOnInsert": {"_id": chat_id}}, upsert=True
            )
            if chat_id not in self.chats:
                self.chats.append(chat_id)

    async def rm_chat(self, chat_id: int) -> None:
        async with self._state_lock:
            await self.chatsdb.delete_one({"_id": chat_id})
            self.chats = [item for item in self.chats if item != chat_id]
            self.cmd_delete = [item for item in self.cmd_delete if item != chat_id]
            self.admin_play = [item for item in self.admin_play if item != chat_id]
            self.auto_delete_play = [item for item in self.auto_delete_play if item != chat_id]
            self.lang.pop(chat_id, None)
            self.auth.pop(chat_id, None)

    async def get_chats(self) -> list:
        if not self.chats:
            self.chats.extend([item["_id"] async for item in self.chatsdb.find({}, {"_id": 1})])
        return list(self.chats)

    async def get_cmd_delete(self, chat_id: int) -> bool:
        if chat_id not in self.cmd_delete:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete.append(chat_id)
        return chat_id in self.cmd_delete

    async def set_cmd_delete(self, chat_id: int, delete: bool = False) -> None:
        async with self._state_lock:
            if delete and chat_id not in self.cmd_delete:
                self.cmd_delete.append(chat_id)
            elif not delete:
                self.cmd_delete = [item for item in self.cmd_delete if item != chat_id]
            await self.chatsdb.update_one(
                {"_id": chat_id}, {"$set": {"cmd_delete": bool(delete)}, "$setOnInsert": {"_id": chat_id}},
                upsert=True,
            )

    async def get_auto_delete_play(self, chat_id: int) -> bool:
        if chat_id not in self.auto_delete_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc is None:
                return True
            if doc.get("auto_delete_play", True):
                self.auto_delete_play.append(chat_id)
        return chat_id in self.auto_delete_play

    async def set_auto_delete_play(self, chat_id: int, status: bool = False) -> None:
        async with self._state_lock:
            if status and chat_id not in self.auto_delete_play:
                self.auto_delete_play.append(chat_id)
            elif not status:
                self.auto_delete_play = [item for item in self.auto_delete_play if item != chat_id]
            await self.chatsdb.update_one(
                {"_id": chat_id}, {"$set": {"auto_delete_play": bool(status)}, "$setOnInsert": {"_id": chat_id}},
                upsert=True,
            )

    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one(
            {"_id": chat_id}, {"$set": {"lang": lang_code}}, upsert=True
        )
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else config.LANG_CODE
        return self.lang[chat_id]

    async def is_logger(self) -> bool:
        return self.logger

    async def get_logger(self) -> bool:
        doc = await self.cache.find_one({"_id": "logger"})
        if doc:
            self.logger = doc["status"]
        return self.logger

    async def set_logger(self, status: bool) -> None:
        await self.cache.update_one(
            {"_id": "logger"}, {"$set": {"status": bool(status)}}, upsert=True
        )
        self.logger = bool(status)

    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        async with self._state_lock:
            if remove:
                self.admin_play = [item for item in self.admin_play if item != chat_id]
            elif chat_id not in self.admin_play:
                self.admin_play.append(chat_id)
            await self.chatsdb.update_one(
                {"_id": chat_id}, {"$set": {"admin_play": not remove}, "$setOnInsert": {"_id": chat_id}},
                upsert=True,
            )

    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True
        )

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$pull": {"user_ids": user_id}}, upsert=True
        )

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    async def is_user(self, user_id: int) -> bool:
        return user_id in self.users

    async def add_user(self, user_id: int) -> None:
        async with self._state_lock:
            await self.usersdb.update_one(
                {"_id": user_id}, {"$setOnInsert": {"_id": user_id}}, upsert=True
            )
            if user_id not in self.users:
                self.users.append(user_id)

    async def rm_user(self, user_id: int) -> None:
        async with self._state_lock:
            await self.usersdb.delete_one({"_id": user_id})
            self.users = [item for item in self.users if item != user_id]

    async def get_users(self) -> list:
        if not self.users:
            self.users.extend([item["_id"] async for item in self.usersdb.find({}, {"_id": 1})])
        return list(self.users)

    async def migrate_coll(self) -> None:
        """Create a migration plan and optionally stage normalized users/chats.

        This method intentionally never drops or replaces live collections. Take and
        verify an external mongodump before enabling the staging operation.
        """
        dry_run = bool(config.MIGRATION_DRY_RUN)
        backup_dir = Path(config.MIGRATION_BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        plan = {"timestamp": stamp, "dry_run": dry_run, "collections": {}}
        source_docs = {}
        normalized = {}

        user_sources = [self.usersdb, self.db.tgusersdb]
        chat_sources = [self.chatsdb]
        for name, collections in (("users", user_sources), ("chats", chat_sources)):
            unique_ids = set()
            docs_seen = 0
            for collection in collections:
                async for doc in collection.find({}):
                    docs_seen += 1
                    value = doc.get("_id")
                    if not isinstance(value, int):
                        value = doc.get("user_id" if name == "users" else "chat_id")
                    if not isinstance(value, int) or isinstance(value, bool):
                        raise ValueError(f"Invalid {name} document; migration aborted")
                    unique_ids.add(value)
            normalized[name] = [{"_id": item} for item in sorted(unique_ids)]
            source_docs[name] = docs_seen
            plan["collections"][name] = {
                "source_documents": docs_seen,
                "normalized_documents": len(unique_ids),
                "duplicates_removed_in_staging_only": docs_seen - len(unique_ids),
            }

        plan_path = backup_dir / f"migration-plan-{stamp}.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        logger.warning("Migration plan written to %s (dry_run=%s)", plan_path, dry_run)
        if dry_run:
            return

        confirmation = getattr(config, "MIGRATION_CONFIRM_APPLY", "")
        if confirmation != "I_HAVE_VERIFIED_BACKUP":
            raise RuntimeError(
                "Migration staging blocked: verify a MongoDB backup, then set "
                "MIGRATION_CONFIRM_APPLY=I_HAVE_VERIFIED_BACKUP and MIGRATION_DRY_RUN=False."
            )

        for name, docs in normalized.items():
            target = self.db[f"{name}_migration_new"]
            # Refuse to overwrite a previous staging run; this protects evidence and gives
            # the operator a chance to inspect old stage data before retrying.
            if await target.count_documents({}):
                raise RuntimeError(f"Staging collection {target.name} is not empty; refusing to overwrite")
            if docs:
                await target.insert_many(docs, ordered=True)
            count = await target.count_documents({})
            if count != len(docs):
                raise RuntimeError(f"Staging validation failed for {name}: {count} != {len(docs)}")
        plan["validated_staged_collections"] = True
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        logger.warning("Migration staging validated; live collections were not changed.")

    async def load_cache(self) -> None:
        # Legacy collections remain untouched by default. Staging is only explicit.
        doc = await self.cache.find_one({"_id": "migrated"})
        if not doc:
            await self.migrate_coll()
        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()
        logger.info("Database cache loaded.")
