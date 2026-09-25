import unittest

from texture_face_sampling import eligibility, face_sampling


class FaceSamplingTests(unittest.TestCase):
    def manifest(self, **changes):
        row = {'minimum_cosine': .03, 'two_sided': False,
               'reason': 'Measured visible cut face has positive cosine .0398.'}
        row.update(changes)
        return {'texture_generated_face_sampling': {'wall': {'6': row}}}

    def test_only_named_face_changes(self):
        policy = face_sampling(self.manifest(), {'wall': 8, 'roof': 3})
        self.assertEqual(eligibility(policy, 'wall', 6), (.03, False))
        self.assertEqual(eligibility(policy, 'wall', 5), (.12, False))
        self.assertEqual(eligibility(policy, 'roof', 1), (.12, False))

    def test_two_sided_is_explicit_and_scoped(self):
        policy = face_sampling(self.manifest(two_sided=True), {'wall': 8})
        self.assertEqual(eligibility(policy, 'wall', 6), (.03, True))
        self.assertEqual(eligibility(policy, 'wall', 7), (.12, False))
        self.assertEqual(eligibility({}, 'legacy', 0, legacy_two_sided=True), (.12, True))

    def test_rejects_unsafe_values(self):
        for value in [0, -.1, .009, .121, float('nan'), True, '0.03']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                face_sampling(self.manifest(minimum_cosine=value), {'wall': 8})
        for values in [{'two_sided': 1}, {'reason': ''}]:
            with self.assertRaises(ValueError):
                face_sampling(self.manifest(**values), {'wall': 8})

    def test_rejects_foreign_absent_and_out_of_scope_faces(self):
        for counts in [{'roof': 8}, {'wall': 6}]:
            with self.assertRaises(ValueError):
                face_sampling(self.manifest(), counts)
        manifest = self.manifest()
        manifest['texture_receiver_face_indices'] = {'wall': [5]}
        with self.assertRaises(ValueError):
            face_sampling(manifest, {'wall': 8})


if __name__ == '__main__':
    unittest.main()
