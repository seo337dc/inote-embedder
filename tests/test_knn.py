import unittest

from lab.knn import top_hit, vote_categories


class VoteCategoriesTest(unittest.TestCase):
    def test_유사도로_가중해서_합친다(self):
        ranked = vote_categories([("학습", 0.9), ("일기", 0.8), ("학습", 0.7)], k=3)
        self.assertEqual([name for name, _ in ranked], ["학습", "일기"])
        self.assertAlmostEqual(ranked[0][1], 1.6)

    def test_개수가_적어도_점수가_높은_이웃이_이길_수_있다(self):
        ranked = vote_categories([("A", 0.95), ("B", 0.3), ("B", 0.3), ("B", 0.3)], k=4)
        self.assertEqual(ranked[0][0], "A")  # 0.95 > 0.9

    def test_가장_가까운_k개만_쓴다(self):
        ranked = vote_categories([("A", 0.9), ("B", 0.8), ("C", 0.7)], k=2)
        self.assertEqual([name for name, _ in ranked], ["A", "B"])

    def test_입력_순서와_상관없이_점수_순으로_k개를_고른다(self):
        ranked = vote_categories([("C", 0.1), ("A", 0.9), ("B", 0.5)], k=2)
        self.assertEqual({name for name, _ in ranked}, {"A", "B"})

    def test_기준_점수_미만_이웃은_뺀다(self):
        ranked = vote_categories([("A", 0.9), ("B", 0.4)], k=5, min_score=0.5)
        self.assertEqual([name for name, _ in ranked], ["A"])

    def test_이웃이_없거나_모두_기준_미만이면_빈_목록(self):
        self.assertEqual(vote_categories([], k=5), [])
        self.assertEqual(vote_categories([("A", 0.2)], k=5, min_score=0.5), [])


class TopHitTest(unittest.TestCase):
    def test_상위_n개_안에_실제_카테고리가_있는지(self):
        ranked = [("A", 2.0), ("B", 1.0), ("C", 0.5)]
        self.assertTrue(top_hit("A", ranked, 1))
        self.assertFalse(top_hit("B", ranked, 1))
        self.assertTrue(top_hit("B", ranked, 2))
        self.assertFalse(top_hit("Z", ranked, 3))
        self.assertFalse(top_hit("A", [], 1))


if __name__ == "__main__":
    unittest.main()
