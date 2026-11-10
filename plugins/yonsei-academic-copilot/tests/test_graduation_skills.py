import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "skills"
CALCULATE = ROOT / "calculate-yonsei-graduation-progress" / "scripts" / "calculate_graduation_progress.py"
PLAN = ROOT / "plan-yonsei-graduation-path" / "scripts" / "plan_graduation_path.py"


def run(script, payload):
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )


def progress_payload():
    return {
        "profile": {
            "campus": "sinchon",
            "college": "example-college",
            "major": "example-major",
            "admission_year": "2024",
        },
        "sources": [
            {
                "id": "catalog",
                "url": "https://www.yonsei.ac.kr/example",
                "checked_on": "2026-07-30",
            }
        ],
        "courses": [
            {
                "course_code": "MAJ1001",
                "title": "기초",
                "credits": 3,
                "status": "completed",
                "categories": ["major_required"],
            },
            {
                "course_code": "MAJ2001",
                "title": "심화",
                "credits": 3,
                "status": "in_progress",
                "categories": ["major_required"],
            },
        ],
        "facts": {"chapel_passes": 4},
        "requirements": [
            {
                "id": "total",
                "label": "총학점",
                "type": "total_credits",
                "minimum": 6,
                "source_id": "catalog",
            },
            {
                "id": "major",
                "label": "전공필수",
                "type": "category_credits",
                "category": "major_required",
                "minimum": 6,
                "source_id": "catalog",
            },
            {
                "id": "chapel",
                "label": "채플",
                "type": "fact",
                "key": "chapel_passes",
                "expected": 4,
                "source_id": "catalog",
            },
        ],
    }


class GraduationSkillTests(unittest.TestCase):
    def plan(self, requirements, courses, **overrides):
        payload = {
            "progress": {"schema": "yonsei-graduation-progress/v1", "complete": True, "requirements": requirements},
            "terms": ["2027-1", "2027-2"],
            "max_credits_per_term": 18,
            "courses": courses,
        }
        payload.update(overrides)
        result = run(PLAN, payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_thirty_missing_credits_are_not_filled_by_three(self):
        output = self.plan(
            [{"id": "total", "type": "total_credits", "remaining": 30, "satisfied": False}],
            [{"course_code": "A", "credits": 3, "requirement_ids": ["total"]}],
        )
        self.assertFalse(output["feasible_with_supplied_courses"])
        self.assertEqual(output["remaining_requirements"], {"total": 27})

    def test_thirty_credits_require_ten_three_credit_courses(self):
        output = self.plan(
            [{"id": "total", "type": "total_credits", "remaining": 30, "satisfied": False}],
            [{"course_code": f"A{index:02}", "credits": 3, "requirement_ids": ["total"]} for index in range(10)],
        )
        self.assertTrue(output["feasible_with_supplied_courses"])
        self.assertEqual([term["credits"] for term in output["planned_terms"]], [18, 12])
        self.assertEqual(output["remaining_requirements"], {})

    def test_accumulates_credits_across_terms_without_reusing_courses(self):
        output = self.plan(
            [{"id": "major", "type": "category_credits", "remaining": 6, "satisfied": False}],
            [{"course_code": code, "credits": 3, "requirement_ids": ["major"]} for code in ["A", "B"]],
            max_credits_per_term=3,
        )
        self.assertTrue(output["feasible_with_supplied_courses"])
        self.assertEqual([term["credits"] for term in output["planned_terms"]], [3, 3])
        self.assertEqual(output["remaining_requirements"], {})

    def test_course_set_requires_distinct_eligible_courses(self):
        rule = {"id": "core", "type": "course_set", "remaining_count": 2, "course_codes": ["A", "B"], "satisfied": False}
        output = self.plan([rule], [
            {"course_code": "A", "credits": 3, "requirement_ids": ["core"]},
            {"course_code": "OTHER", "credits": 3, "requirement_ids": ["core"]},
        ])
        self.assertFalse(output["feasible_with_supplied_courses"])
        self.assertEqual(output["remaining_requirements"], {"core": 1})
        output = self.plan([rule], [
            {"course_code": code, "credits": 3, "requirement_ids": ["core"]} for code in ["A", "B"]
        ])
        self.assertTrue(output["feasible_with_supplied_courses"])

    def test_fact_cannot_be_satisfied_by_mapping_a_course(self):
        output = self.plan(
            [{"id": "chapel", "type": "fact", "satisfied": False}],
            [{"course_code": "A", "credits": 3, "requirement_ids": ["chapel"]}],
        )
        self.assertFalse(output["feasible_with_supplied_courses"])
        self.assertIn("chapel", output["unresolved_requirement_ids"])

    def test_incomplete_progress_cannot_claim_feasible(self):
        output = self.plan([], [], progress={"schema": "yonsei-graduation-progress/v1", "complete": False, "requirements": []})
        self.assertFalse(output["feasible_with_supplied_courses"])

    def test_non_overlap_categories_do_not_double_count(self):
        output = self.plan(
            [{"id": name, "type": "category_credits", "allow_overlap": False, "remaining": 3, "satisfied": False} for name in ["one", "two"]],
            [{"course_code": "A", "credits": 3, "requirement_ids": ["one", "two"]}],
        )
        self.assertFalse(output["feasible_with_supplied_courses"])
        self.assertEqual(output["remaining_requirements"], {"two": 3})

    def test_completed_course_from_progress_is_not_scheduled_again(self):
        output = self.plan(
            [{"id": "core", "type": "course_set", "remaining_count": 1, "completed_courses": ["A"], "course_codes": ["A", "B"], "satisfied": False}],
            [{"course_code": "A", "credits": 3, "requirement_ids": ["core"]}],
        )
        self.assertFalse(output["feasible_with_supplied_courses"])
        self.assertEqual(output["planned_terms"][0]["courses"], [])

    def test_calculates_completed_and_projected_progress(self):
        result = run(CALCULATE, progress_payload())
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        total = next(item for item in output["requirements"] if item["id"] == "total")
        self.assertEqual(total["completed"], 3.0)
        self.assertEqual(total["projected_remaining"], 0.0)
        self.assertFalse(output["all_requirements_satisfied"])
        self.assertTrue(output["complete"])
        self.assertTrue(output["advisory_only"])

    def test_missing_source_keeps_calculation_incomplete(self):
        payload = progress_payload()
        payload["requirements"][0]["source_id"] = "missing"
        result = run(CALCULATE, payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["complete"])
        self.assertEqual(output["unknowns"][0]["type"], "missing-official-source")

    def test_plans_remaining_requirement(self):
        progress = json.loads(run(CALCULATE, progress_payload()).stdout)
        result = run(
            PLAN,
            {
                "progress": progress,
                "terms": ["2026-2", "2027-1"],
                "max_credits_per_term": 3,
                "completed_course_codes": ["MAJ1001"],
                "courses": [
                    {
                        "course_code": "MAJ2001",
                        "title": "심화",
                        "credits": 3,
                        "requirement_ids": ["total", "major"],
                        "prerequisites": ["MAJ1001"],
                        "offered_terms": ["2026-2"],
                        "required": True,
                        "priority": 5,
                    }
                ],
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["feasible_with_supplied_courses"])
        self.assertEqual(output["planned_terms"][0]["courses"][0]["course_code"], "MAJ2001")
        self.assertFalse(output["registration_performed"])

    def test_schedules_unmapped_prerequisite_before_required_course(self):
        progress = json.loads(run(CALCULATE, progress_payload()).stdout)
        result = run(
            PLAN,
            {
                "progress": progress,
                "terms": ["2026-2", "2027-1"],
                "max_credits_per_term": 3,
                "completed_course_codes": [],
                "courses": [
                    {
                        "course_code": "PRE1000",
                        "title": "선수과목",
                        "credits": 3,
                        "requirement_ids": [],
                        "prerequisites": [],
                        "offered_terms": ["2026-2"],
                    },
                    {
                        "course_code": "MAJ2001",
                        "title": "전공필수",
                        "credits": 3,
                        "requirement_ids": ["total", "major"],
                        "prerequisites": ["PRE1000"],
                        "offered_terms": ["2027-1"],
                        "required": True,
                    },
                ],
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["planned_terms"][0]["courses"][0]["course_code"], "PRE1000")
        self.assertEqual(output["planned_terms"][1]["courses"][0]["course_code"], "MAJ2001")


if __name__ == "__main__":
    unittest.main()
