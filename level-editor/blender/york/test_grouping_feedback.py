import json
from pathlib import Path
import tempfile
import unittest
from record_grouping_feedback import record


class GroupingFeedbackTests(unittest.TestCase):
    def test_explicit_feedback_is_scoped_to_the_displayed_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);revision='a'*64
            item={'id':'york-wall','review_revision':revision,'approval_scope':'grouping-only'}
            (root/'evidence.json').write_text(json.dumps({'items':[item]}))
            destination=root/'decisions.json'
            rows=record('York grouping review\nyork-wall: approved — Correct ownership [review '+revision[:16]+']',root,destination)
            self.assertEqual(rows[0]['scope'],'grouping-only')
            self.assertEqual(rows[0]['review_revision'],revision)
            self.assertEqual(rows[0]['decision'],'approved')
            record('york-wall: needs refinement — Move stairs [review '+revision[:16]+']',root,destination)
            self.assertEqual(len(json.loads(destination.read_text())['decisions']),2)
            before=destination.read_bytes()
            for text in ['pretty good','york-wall: approved [review '+'b'*16+']']:
                with self.assertRaises(ValueError):record(text,root,destination)
                self.assertEqual(before,destination.read_bytes())

    def test_archived_revision_can_receive_feedback_but_not_new_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);archive=root/'history/old';archive.mkdir(parents=True)
            for folder,letter in [(root,'b'),(archive,'a')]:
                (folder/'evidence.json').write_text(json.dumps({'items':[{'id':'york-wall',
                    'review_revision':letter*64,'approval_scope':'grouping-only'}]}))
            with self.assertRaisesRegex(ValueError,'outdated'):
                record('york-wall: approved [review '+'a'*16+']',root,root/'decisions.json')
            rows=record('york-wall: needs refinement — Move stairs [review '+'a'*16+']',root,root/'decisions.json')
            self.assertEqual(rows[0]['review_revision'],'a'*64)


if __name__=='__main__':unittest.main()
