"""Tests for the PDF reflow step (extractors/pdf_extractor.py).

Run with:  python -m unittest discover tests
"""
import unittest

from extractors.pdf_extractor import normalize_cjk_text, reflow_pages

EM = " "


class NormalizeTests(unittest.TestCase):
    def test_vertical_punctuation(self):
        self.assertEqual(normalize_cjk_text("﹁認識自己﹂︵Delphi︶"), "「認識自己」（Delphi）")

    def test_kangxi_radicals(self):
        # ⾃⼰ are Kangxi radical code points, not 自己.
        self.assertEqual(normalize_cjk_text("⾃⼰成⻑"), "自己成長")

    def test_bare_radical_kept(self):
        self.assertEqual(normalize_cjk_text("『⺅』"), "『⺅』")


class VerticalReflowTests(unittest.TestCase):
    def test_rejoins_characters_into_paragraphs(self):
        page = "\n".join(
            ["７", EM]
            + list("找出你的本來面目")
            + [EM, EM]
            + list("認識自己︵")
            + ["Gnothi Seauton", "︶──"]
            + list("這幾個希臘字。")
            + [EM, EM]
            + list("第二段開始，")
        )
        page2 = "\n".join(list("繼續下一頁。你認為自己是誰") + [EM, EM] + list("新段落。"))
        self.assertEqual(
            reflow_pages([page, page2]),
            [
                "找出你的本來面目",
                "認識自己（Gnothi Seauton）──這幾個希臘字。",
                "第二段開始，繼續下一頁。",
                "你認為自己是誰",
                "新段落。",
            ],
        )

    def test_space_before_rotated_dash_removed(self):
        page = "\n".join(list("有些人") + ["⼈ ──"] + list("可以很快地告訴你。" * 3))
        self.assertEqual(reflow_pages([page]), ["有些人人──" + "可以很快地告訴你。" * 3])


class HorizontalReflowTests(unittest.TestCase):
    def test_wrapped_lines_still_reflow(self):
        page = (
            "This is a long line of body text that runs to the margin\n"
            "and this one wraps onto the next line too, all the way\n"
            "short end.\n"
            "\n"
            "Next paragraph — with a dash."
        )
        self.assertEqual(
            reflow_pages([page]),
            [
                "This is a long line of body text that runs to the margin "
                "and this one wraps onto the next line too, all the way short end.",
                "Next paragraph — with a dash.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
