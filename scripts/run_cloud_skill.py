#!/usr/bin/env python3
"""Run existing, offline academic/course scripts without plugin installation."""
import argparse
from pathlib import Path
import subprocess
import sys


SCRIPTS = {
    "calculate-yonsei-graduation-progress": ("yonsei-academic-copilot", "calculate_graduation_progress.py"),
    "plan-yonsei-graduation-path": ("yonsei-academic-copilot", "plan_graduation_path.py"),
    "normalize-yonsei-courses": ("yonsei-course-registration", "normalize_courses.py"),
    "build-yonsei-timetable": ("yonsei-course-registration", "build_timetable.py"),
    "check-yonsei-schedule": ("yonsei-course-registration", "check_schedule.py"),
    "audit-yonsei-course-plan": ("yonsei-course-registration", "audit_course_plan.py"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", choices=sorted(SCRIPTS))
    parser.add_argument("--input", default="-", help="JSON file, or - for stdin")
    args = parser.parse_args()
    plugin, filename = SCRIPTS[args.skill]
    script = Path(__file__).resolve().parents[1] / "plugins" / plugin / "skills" / args.skill / "scripts" / filename
    return subprocess.run([sys.executable, "-B", str(script), "--input", args.input], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
