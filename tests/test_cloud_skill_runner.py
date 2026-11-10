"""Exercise the cloud entry point against existing academic and timetable scripts."""
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_cloud_skill.py"


class CloudSkillRunnerTests(unittest.TestCase):
    def invoke(self, name, payload):
        result = subprocess.run(
            [sys.executable, "-B", str(RUNNER), name],
            input=json.dumps(payload), text=True, capture_output=True, check=False,
            cwd=ROOT.parent,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_graduation_calculation_plan_and_recalculation(self):
        # Synthetic rules: the official-domain URL is a source-link format fixture,
        # not a claim that these requirements came from that document.
        payload = {
            "profile": {"campus": "sinchon", "college": "example", "major": "example", "admission_year": "2024"},
            "sources": [{"id": "fixture", "url": "https://www.yonsei.ac.kr/example", "checked_on": "2026-11-10"}],
            "courses": [{"course_code": "DONE", "credits": 3, "status": "completed", "categories": ["major"]}],
            "facts": {"chapel": True},
            "requirements": [
                {"id": "total", "label": "총학점", "type": "total_credits", "minimum": 9, "source_id": "fixture"},
                {"id": "major", "label": "전공", "type": "category_credits", "category": "major", "minimum": 9, "source_id": "fixture"},
                {"id": "chapel", "label": "채플", "type": "fact", "key": "chapel", "source_id": "fixture"},
            ],
        }
        progress = self.invoke("calculate-yonsei-graduation-progress", payload)
        self.assertTrue(progress["complete"])
        self.assertFalse(progress["all_requirements_satisfied"])
        self.assertEqual(progress["requirements"][0]["remaining"], 6)
        plan = self.invoke("plan-yonsei-graduation-path", {
            "progress": progress, "terms": ["2027-1", "2027-2"], "max_credits_per_term": 3,
            "completed_course_codes": ["DONE"],
            "courses": [
                {"course_code": "NEXT1", "credits": 3, "requirement_ids": ["total", "major"], "offered_terms": ["2027-1"]},
                {"course_code": "NEXT2", "credits": 3, "requirement_ids": ["total", "major"], "prerequisites": ["NEXT1"], "offered_terms": ["2027-2"]},
            ],
        })
        self.assertTrue(plan["feasible_with_supplied_courses"])
        self.assertEqual([term["credits"] for term in plan["planned_terms"]], [3, 3])
        for term in plan["planned_terms"]:
            for course in term["courses"]:
                payload["courses"].append({"course_code": course["course_code"], "credits": course["credits"], "status": "completed", "categories": ["major"]})
        recalculated = self.invoke("calculate-yonsei-graduation-progress", payload)
        self.assertTrue(recalculated["all_requirements_satisfied"])
        self.assertFalse(recalculated["official_audit"])

    def test_normalize_build_check_and_audit_timetable(self):
        def course(identifier, code, day, start, end):
            return {"id": identifier, "section": identifier.split("-")[1], "course_code": code, "title": code, "credits": 3, "campus": "sinchon",
                    "meetings": [{"day": day, "start": start, "end": end, "campus": "sinchon"}]}
        normalized = self.invoke("normalize-yonsei-courses", {
            "courses": [course("A-01", "A", "mon", "10:00", "11:00"),
                        course("A-02", "A", "tue", "10:00", "11:00"),
                        course("B-01", "B", "mon", "10:30", "12:00")],
            "requirements": [{"id": "a", "course_ids": ["A-01", "A-02"]}, {"id": "b", "course_ids": ["B-01"]}],
            "constraints": {"min_credits": 6, "max_credits": 6, "days_off": ["fri"]},
        })
        built = self.invoke("build-yonsei-timetable", normalized)
        self.assertTrue(built["feasible"])
        selected_ids = built["solutions"][0]["course_ids"]
        self.assertEqual(selected_ids, ["A-02", "B-01"])
        selected = {"courses": [course for course in normalized["courses"] if course["id"] in selected_ids], "constraints": normalized["constraints"]}
        checked = self.invoke("check-yonsei-schedule", selected)
        self.assertTrue(checked["conflict_free"])
        audited = self.invoke("audit-yonsei-course-plan", selected)
        self.assertTrue(audited["constraints_met"])

    def test_preserves_script_validation_error(self):
        result = subprocess.run([sys.executable, "-B", str(RUNNER), "build-yonsei-timetable"],
                                input="{}", text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
