import unittest
from unittest import mock

from tap_jira import streams
from tap_jira.http import JiraBadRequestError, JiraNotFoundError
from tap_jira.context import Context


def board_list(*boards):
    return {"maxResults": 50, "values": list(boards)}


def issues_page(*records):
    return {"maxResults": 50, "issues": list(records)}


class TestBacklogAndBoardConfiguration(unittest.TestCase):
    def run_sync(self, request_side_effect, selected):
        Context.client = mock.MagicMock()
        Context.client.request.side_effect = request_side_effect
        written = []

        def fake_write_page(self, page):
            written.append((self.tap_stream_id, [dict(r) for r in page]))

        with mock.patch.object(streams.Stream, "write_page", new=fake_write_page), \
             mock.patch.object(Context, "is_selected",
                               side_effect=lambda sid: sid in selected):
            streams.BOARDS.sync()
        return written

    def test_board_backlog_tagged_with_board_id(self):
        side_effect = [
            board_list({"id": 10}),
            issues_page({"id": 100, "key": "A-1"}, {"id": 101, "key": "A-2"}),  # board_backlog
        ]
        written = self.run_sync(side_effect, {"boards", "board_backlog"})
        board_backlog = [r for sid, recs in written if sid == "board_backlog" for r in recs]
        self.assertEqual(2, len(board_backlog))
        self.assertTrue(all(r["boardId"] == 10 for r in board_backlog))

    def test_board_configurations_single_object_tagged(self):
        config = {"id": 10, "name": "Board 10", "type": "scrum",
                  "columnConfig": {"columns": [{"name": "To Do", "statuses": [{"id": "1"}]}]}}
        side_effect = [board_list({"id": 10}), config]
        written = self.run_sync(side_effect, {"boards", "board_configurations"})

        cfg_pages = [recs for sid, recs in written if sid == "board_configurations"]
        self.assertEqual(1, len(cfg_pages))          # written as a one-item page
        self.assertEqual(1, len(cfg_pages[0]))
        self.assertEqual(10, cfg_pages[0][0]["boardId"])

    def test_board_configurations_skipped_on_error(self):
        for exc in (JiraBadRequestError("400"), JiraNotFoundError("404")):
            with self.subTest(exc=type(exc).__name__):
                side_effect = [board_list({"id": 10}), exc]
                written = self.run_sync(side_effect, {"boards", "board_configurations"})
                self.assertNotIn("board_configurations",
                                 {sid for sid, _ in written})

    def test_unselected_board_config_makes_no_request(self):
        # Only boards selected: no board_backlog/config calls beyond the board listing.
        self.run_sync([board_list({"id": 10})], {"boards"})
        self.assertEqual(1, Context.client.request.call_count)


class TestBoardChildDependencies(unittest.TestCase):
    def validate_with_selected(self, selected):
        catalog = mock.MagicMock()
        catalog.streams = [mock.MagicMock(tap_stream_id=sid) for sid in streams.ALL_STREAM_IDS]
        Context.catalog = catalog
        with mock.patch.object(Context, "is_selected",
                               side_effect=lambda sid: sid in selected):
            streams.validate_dependencies()

    def test_board_backlog_and_config_require_boards(self):
        with self.assertRaises(streams.DependencyException) as ctx:
            self.validate_with_selected({"board_backlog", "board_configurations"})
        msg = str(ctx.exception)
        self.assertIn("Backlog", msg)
        self.assertIn("Board Configuration", msg)
        self.assertIn("Boards", msg)

    def test_ok_when_boards_selected(self):
        self.validate_with_selected({"boards", "board_backlog", "board_configurations"})


if __name__ == "__main__":
    unittest.main()
