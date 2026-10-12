import unittest

from lab.textprep import build_embedding_text, content_hash, html_to_text


class HtmlToTextTest(unittest.TestCase):
    def test_태그를_지우고_문단은_줄바꿈으로_남긴다(self):
        self.assertEqual(html_to_text("<h1>제목</h1><p>첫 문단</p><p>둘째 <strong>문단</strong></p>"), "제목\n첫 문단\n둘째 문단")

    def test_목록과_표_셀도_줄로_나눈다(self):
        text = html_to_text("<ul><li>하나</li><li>둘</li></ul><table><tr><td>가</td><td>나</td></tr></table>")
        self.assertIn("하나\n둘", text)

    def test_script와_style_안의_글자는_버린다(self):
        self.assertEqual(html_to_text("<p>본문</p><script>alert(1)</script><style>p{color:red}</style>"), "본문")

    def test_HTML_엔티티를_풀고_공백을_정리한다(self):
        self.assertEqual(html_to_text("<p>a&nbsp;&nbsp;b &amp;   c\t d</p>"), "a b & c d")

    def test_코드_블록의_글자는_남긴다(self):
        self.assertIn("print('hi')", html_to_text("<pre><code>print('hi')</code></pre>"))

    def test_빈_입력이나_None은_빈_문자열(self):
        self.assertEqual(html_to_text(""), "")
        self.assertEqual(html_to_text(None), "")  # type: ignore[arg-type]

    def test_깨진_HTML도_글자는_건진다(self):
        self.assertEqual(html_to_text("<p>열린 태그<p>다음"), "열린 태그\n다음")


class BuildEmbeddingTextTest(unittest.TestCase):
    def test_제목_다음_줄에_본문을_붙인다(self):
        self.assertEqual(build_embedding_text("제목", "본문입니다"), "제목\n본문입니다")

    def test_최대_글자수에서_자른다(self):
        text = build_embedding_text("제목", "가" * 100, max_chars=10)
        self.assertEqual(len(text), 10)
        self.assertTrue(text.startswith("제목\n"))

    def test_앞뒤_공백은_지운다(self):
        self.assertEqual(build_embedding_text("  제목  ", "  본문  "), "제목\n본문")

    def test_카테고리_같은_다른_정보는_들어가지_않는다(self):
        # 함수가 제목과 본문만 받는다 — 카테고리를 넘길 방법이 없다는 것이 설계(정답 누출 방지)
        import inspect

        self.assertEqual(list(inspect.signature(build_embedding_text).parameters), ["title", "content_text", "max_chars"])


class ContentHashTest(unittest.TestCase):
    def test_같은_글은_같은_해시_다르면_다른_해시(self):
        self.assertEqual(content_hash("가나다"), content_hash("가나다"))
        self.assertNotEqual(content_hash("가나다"), content_hash("가나라"))

    def test_64자리_16진수(self):
        self.assertRegex(content_hash("x"), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
