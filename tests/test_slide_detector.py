import unittest

from slide_detector import SlideDetector


class FakeShape:
    def __init__(self, text):
        self.text = text


class FakeSlide:
    def __init__(self, text):
        self.shapes = [FakeShape(text)]


class SlideDetectorProjectRulesTest(unittest.TestCase):
    def test_ar_issue_routes_to_ar_project(self):
        detector = SlideDetector()

        project_key = detector._detect_issue_and_project(
            FakeSlide("AR issue: Report rendering error")
        )

        self.assertEqual(project_key, "AR")

    def test_ar_issue_routes_to_ar_project_from_bulleted_slide_text(self):
        detector = SlideDetector()

        project_key = detector._detect_issue_and_project(
            FakeSlide(
                "Is katG:c.944_945delGCinsCG confirmed?\n"
                "\u2022 AR issue: INF drug name should be included in the email note."
            )
        )

        self.assertEqual(project_key, "AR")

    def test_ar_issue_routes_to_ar_project_from_indented_slide_text(self):
        detector = SlideDetector()

        project_key = detector._detect_issue_and_project(
            FakeSlide(
                "Is katG:c.944_945delGCinsCG confirmed?\n"
                "    AR issue: INF drug name should be included in the email note."
            )
        )

        self.assertEqual(project_key, "AR")


if __name__ == "__main__":
    unittest.main()
