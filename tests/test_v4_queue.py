import unittest

from anony.helpers._dataclass import Track
from anony.helpers._queue import Queue


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = Queue()
        self.track1 = Track(id="abcdefghijk", title="one")
        self.track2 = Track(id="12345678901", title="two")

    def test_empty_queue_is_safe(self):
        self.assertIsNone(self.queue.get_current(10))
        self.assertIsNone(self.queue.get_next(10))
        self.queue.clear(10)
        self.assertEqual(self.queue.get_queue(10), [])

    def test_add_and_get_next(self):
        self.assertEqual(self.queue.add(10, self.track1), 0)
        self.assertEqual(self.queue.add(10, self.track2), 1)
        self.assertIs(self.queue.get_current(10), self.track1)
        self.assertIs(self.queue.get_next(10), self.track2)
        self.assertIs(self.queue.get_current(10), self.track2)

    def test_clear_removes_chat_queue(self):
        self.queue.add(10, self.track1)
        self.queue.clear(10)
        self.assertEqual(self.queue.get_queue(10), [])
        self.assertNotIn(10, self.queue.queues)

    def test_invalid_force_position_is_bounded(self):
        self.queue.add(10, self.track1)
        self.queue.add(10, self.track2)
        self.queue.force_add(10, self.track2, remove=99)
        self.assertLessEqual(len(self.queue.get_queue(10)), 3)

    def test_check_item_handles_missing_id(self):
        self.queue.add(10, self.track1)
        pos, item = self.queue.check_item(10, "")
        self.assertEqual(pos, -1)
        self.assertIsNone(item)


if __name__ == "__main__":
    unittest.main()
