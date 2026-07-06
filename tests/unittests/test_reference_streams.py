import unittest
from unittest import mock

from tap_jira import streams
from tap_jira.context import Context


def get_stream(tap_stream_id):
    return next(s for s in streams.ALL_STREAMS if s.tap_stream_id == tap_stream_id)


class TestReferenceStreams(unittest.TestCase):
    """fields and statuses are plain FULL_TABLE streams hitting a flat-array
    endpoint via the base Stream.sync()."""

    def _run(self, tap_stream_id, response):
        Context.client = mock.MagicMock()
        Context.client.request.return_value = response
        written = []
        with mock.patch.object(streams.Stream, "write_page",
                               new=lambda self, page: written.append(page)):
            get_stream(tap_stream_id).sync()
        return written

    def test_fields_stream(self):
        st = get_stream("issue_fields")
        self.assertEqual(["id"], st.pk_fields)
        self.assertEqual("/rest/api/2/field", st.path)
        self.assertEqual("FULL_TABLE", st.forced_replication_method)

        payload = [{"id": "customfield_10016", "name": "Story Points", "custom": True}]
        written = self._run("issue_fields", payload)
        Context.client.request.assert_called_once_with("issue_fields", "GET", "/rest/api/2/field")
        self.assertEqual([payload], written)

    def test_statuses_stream(self):
        st = get_stream("workflow_statuses")
        self.assertEqual(["id"], st.pk_fields)
        self.assertEqual("/rest/api/2/status", st.path)

        payload = [{"id": "10000", "name": "To Do",
                    "statusCategory": {"key": "new", "name": "To Do"}}]
        written = self._run("workflow_statuses", payload)
        Context.client.request.assert_called_once_with("workflow_statuses", "GET", "/rest/api/2/status")
        self.assertEqual([payload], written)

    def test_reference_streams_have_no_parent_dependency(self):
        # They are independent top-level streams; validate_dependencies must not
        # require anything for them.
        for name in ("issue_fields", "workflow_statuses"):
            self.assertIsNone(get_stream(name).parent_tap_stream_id)


if __name__ == "__main__":
    unittest.main()
