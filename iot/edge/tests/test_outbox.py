import tempfile
import unittest
from pathlib import Path

from basilcare_edge.outbox import Outbox


class OutboxTest(unittest.TestCase):
    def test_a_row_leaves_only_when_acknowledged(self):
        box = Outbox(":memory:")
        box.add("t/1", {"n": 1})
        box.add("t/2", {"n": 2})
        rows = box.take()
        self.assertEqual([1, 2], [payload["n"] for _, _, payload in rows])
        self.assertEqual([], box.take(), "in-flight rows are not taken twice")
        box.done(rows[0][0])
        self.assertEqual(1, box.pending())

    def test_connection_loss_sends_in_flight_rows_again_in_order(self):
        box = Outbox(":memory:")
        for n in range(3):
            box.add("t", {"n": n})
        box.take()
        box.release_inflight()
        self.assertEqual([0, 1, 2], [p["n"] for _, _, p in box.take()])

    def test_bounded_queue_drops_the_oldest(self):
        box = Outbox(":memory:", max_rows=3)
        for n in range(5):
            box.add("t", {"n": n})
        self.assertEqual([2, 3, 4], [p["n"] for _, _, p in box.take()])
        self.assertEqual(2, box.dropped)

    def test_survives_a_restart_of_the_program(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "sub" / "outbox.sqlite3")
            box = Outbox(path)
            box.add("t", {"n": 1})
            box.take()                       # in flight when the power is cut
            box.close()
            again = Outbox(path)
            self.assertEqual([1], [p["n"] for _, _, p in again.take()])
            again.close()


if __name__ == "__main__":
    unittest.main()
