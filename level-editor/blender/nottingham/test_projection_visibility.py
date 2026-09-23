import unittest
from build_gallery import projection_available_nodes


def layers(*nodes):
    return [{"receiver_nodes": list(nodes), "occluder_nodes": list(nodes)}]


class ProjectionVisibilityTests(unittest.TestCase):
    def test_restored_owned_piers(self):
        self.assertEqual(projection_available_nodes(layers("neighbor", "arch"),
            layers("neighbor", "arch", "pier"), ["arch", "pier"]),
            {"neighbor", "arch", "pier"})

    def test_hidden_owned_part(self):
        self.assertEqual(projection_available_nodes(layers("neighbor", "door"),
            layers("neighbor"), ["door"]), {"neighbor"})

    def test_foreign_visibility_change_rejected(self):
        for before, after in [(layers("arch"), layers("arch", "neighbor")),
                              (layers("arch", "neighbor"), layers("arch"))]:
            with self.assertRaises(ValueError):
                projection_available_nodes(before, after, ["arch"])
