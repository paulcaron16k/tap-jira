import unittest
from unittest import mock

from tap_jira import streams
from tap_jira.http import JiraBadRequestError
from tap_jira.context import Context


def board_list(*boards):
    return {"maxResults": 50, "values": list(boards)}


def values_page(*records):
    return {"maxResults": 50, "values": list(records)}


def issues_page(*records):
    return {"maxResults": 50, "issues": list(records)}


class TestBoardsSync(unittest.TestCase):
    """Exercise Boards.sync orchestration without hitting the network or the
    singer Transformer - write_page is stubbed so we can inspect exactly what
    each stream would emit."""

    def run_sync(self, request_side_effect, selected):
        Context.client = mock.MagicMock()
        Context.client.request.side_effect = request_side_effect

        written = []

        def fake_write_page(self, page):
            # Record a shallow copy so later mutation can't affect assertions
            written.append((self.tap_stream_id, [dict(r) for r in page]))

        with mock.patch.object(streams.Stream, "write_page", new=fake_write_page), \
             mock.patch.object(Context, "is_selected",
                               side_effect=lambda sid: sid in selected):
            streams.BOARDS.sync()

        return written

    def test_children_tagged_with_board_id(self):
        """Every board-scoped child record gets a boardId FK and children are
        fanned out per board."""
        side_effect = [
            board_list({"id": 10}, {"id": 20}),          # board listing
            # board 10
            issues_page({"id": 100, "key": "A-1"}),      # board_issues
            values_page({"id": 200, "key": "PA"}),       # board_projects
            values_page({"id": 300, "name": "Epic A"}),  # epics
            values_page({"id": 400, "name": "Sprint 1"}),  # sprints
            # board 20
            issues_page({"id": 101, "key": "B-1"}),
            values_page({"id": 201, "key": "PB"}),
            values_page({"id": 301, "name": "Epic B"}),
            values_page({"id": 401, "name": "Sprint 2"}),
        ]
        selected = {"boards", "board_issues", "board_projects", "epics", "sprints"}
        written = self.run_sync(side_effect, selected)

        # Boards themselves are written once and never carry a boardId
        boards_pages = [recs for sid, recs in written if sid == "boards"]
        self.assertEqual(1, len(boards_pages))
        self.assertNotIn("boardId", boards_pages[0][0])

        # Each child record is tagged with the id of the board it came under
        for sid in ("board_issues", "board_projects", "epics", "sprints"):
            recs = [r for s, recs in written if s == sid for r in recs]
            self.assertEqual(2, len(recs), "expected one record per board for %s" % sid)
            self.assertEqual({10, 20}, {r["boardId"] for r in recs})

    def test_unsupported_child_is_skipped(self):
        """A 400 from a board-scoped endpoint (e.g. sprints on a kanban board)
        is swallowed so the rest of the sync continues."""
        side_effect = [
            board_list({"id": 10}),
            issues_page({"id": 100, "key": "A-1"}),        # board_issues OK
            JiraBadRequestError("HTTP-error-code: 400"),   # board_projects 400
            values_page({"id": 300, "name": "Epic A"}),    # epics OK
            JiraBadRequestError("HTTP-error-code: 400"),   # sprints 400
        ]
        selected = {"boards", "board_issues", "board_projects", "epics", "sprints"}
        written = self.run_sync(side_effect, selected)

        written_ids = {sid for sid, _ in written}
        self.assertIn("board_issues", written_ids)
        self.assertIn("epics", written_ids)
        # The two streams that returned 400 emit nothing but don't abort the sync
        self.assertNotIn("board_projects", written_ids)
        self.assertNotIn("sprints", written_ids)

    def test_unselected_children_are_not_requested(self):
        """Children that aren't selected trigger no API calls."""
        side_effect = [board_list({"id": 10})]
        written = self.run_sync(side_effect, selected={"boards"})

        self.assertEqual({"boards"}, {sid for sid, _ in written})
        # Only the board listing was requested - no per-board child calls
        self.assertEqual(1, Context.client.request.call_count)


class TestAgileDependencyValidation(unittest.TestCase):
    def validate_with_selected(self, selected):
        catalog = mock.MagicMock()
        catalog.streams = [mock.MagicMock(tap_stream_id=sid) for sid in streams.ALL_STREAM_IDS]
        Context.catalog = catalog
        with mock.patch.object(Context, "is_selected",
                               side_effect=lambda sid: sid in selected):
            streams.validate_dependencies()

    def test_board_child_requires_boards(self):
        with self.assertRaises(streams.DependencyException) as ctx:
            self.validate_with_selected({"sprints", "epics"})
        msg = str(ctx.exception)
        self.assertIn("Sprints", msg)
        self.assertIn("Epics", msg)
        self.assertIn("Boards", msg)

    def test_board_children_ok_when_boards_selected(self):
        # Should not raise
        self.validate_with_selected({"boards", "sprints", "epics",
                                     "board_issues", "board_projects"})


if __name__ == "__main__":
    unittest.main()
