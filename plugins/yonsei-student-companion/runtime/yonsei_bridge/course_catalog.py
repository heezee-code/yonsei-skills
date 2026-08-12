#!/usr/bin/env python3
"""Read the public Yonsei course handbook without launching a browser."""

from __future__ import annotations

import http.cookiejar
import json
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from yonsei_bridge.cdp import BridgeError
else:
    from .cdp import BridgeError


COURSE_CATALOG_URL = (
    "https://underwood1.yonsei.ac.kr/com/lgin/SsoCtr/"
    "initExtPageWork.do?link=handbList&locale=ko"
)
BASE_URL = "https://underwood1.yonsei.ac.kr"
MENU_PATH = "/com/cmsv/MenuCtr/findMenu.do"
CURRENT_TERM_PATH = "/sch/sles/SlessyCtr/findSlesYySmtScheList.do"
HIERARCHY_PATH = "/sch/sles/SlescsCtr/findSchSlesHandbList.do"
SEARCH_PATH = "/sch/sles/SlessyCtr/findAtnlcHandbList.do"

# These are the anonymous handbook screen's server-side context identifiers.
# The bootstrap and menu checks below verify that they still resolve to the
# public course-handbook program before any catalogue query is sent.
CONTEXT_FIELDS = (
    ("_menuId", "MTA5MzM2MTI3MjkzMTI2NzYwMDA="),
    ("_menuNm", ""),
    ("_pgmId", "NDE0MDA4NTU1NjY="),
)
PUBLIC_MENU_ID = "M105675"
PUBLIC_PROGRAM_ID = "P004512"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_AGENT_ROWS = 50

SEMESTER_CODES = {
    "1": "10",
    "1학기": "10",
    "10": "10",
    "2": "20",
    "2학기": "20",
    "20": "20",
}
SEMESTER_LABELS = {"10": "1학기", "20": "2학기"}


def _normalized(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").casefold())


def _form_map(values: dict[str, Any]) -> list[tuple[str, str]]:
    fields = list(CONTEXT_FIELDS)
    fields.extend((f"@d1#{key}", str(value)) for key, value in values.items())
    fields.extend((("@d#", "@d1#"), ("@d1#", "dmCond"), ("@d1#tp", "dm")))
    return fields


def _row_label(row: dict[str, Any]) -> str:
    return str(row.get("deptNm") or row.get("engDeptNm") or row.get("deptCd") or "")


def _resolve_row(rows: list[dict[str, Any]], requested: Any) -> dict[str, Any] | None:
    wanted = _normalized(requested)
    if not wanted:
        return rows[0] if rows else None
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for row in rows:
        candidates = (
            row.get("deptCd"),
            row.get("deptNm"),
            row.get("engDeptNm"),
        )
        normalized = [_normalized(value) for value in candidates if value]
        if wanted in normalized:
            exact.append(row)
        elif any(wanted in value or value in wanted for value in normalized):
            partial.append(row)
    if exact:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return partial[0] if partial else None


def _course_row(raw: dict[str, Any], index: int) -> dict[str, Any]:
    fields = {
        "학정번호-분반-실습": raw.get("subjtnbCorsePrcts"),
        "학정번호": raw.get("subjtnb"),
        "분반": raw.get("corseDvclsNo"),
        "실습분반": raw.get("prctsCorseDvclsNo"),
        "교과목명": raw.get("subjtNm"),
        "영문교과목명": raw.get("subjtEngNm"),
        "학점": raw.get("cdt"),
        "교수": raw.get("cgprfNm"),
        "영문교수": raw.get("cgprfEngNm"),
        "강의시간": raw.get("lctreTimeNm"),
        "영문강의시간": raw.get("lctreTimeEngNm"),
        "강의실": raw.get("lecrmNm"),
        "영문강의실": raw.get("lecrmEngNm"),
        "개설학과": raw.get("estblDeprtNm"),
        "캠퍼스": raw.get("campsDivNm"),
        "이수구분": raw.get("subsrtDivNm"),
        "수업방식": raw.get("subjtClNm"),
        "유의사항": raw.get("atntnMattrDesc"),
    }
    cleaned = {
        label: str(value).strip()
        for label, value in fields.items()
        if value is not None and str(value).strip()
    }
    summary_labels = (
        "학정번호-분반-실습",
        "교과목명",
        "교수",
        "학점",
        "강의시간",
        "강의실",
    )
    return {
        "grid": 0,
        "row": index,
        "fields": cleaned,
        "text": " | ".join(cleaned[label] for label in summary_labels if label in cleaned),
    }


class OfficialCourseCatalogClient:
    """Small, dependency-free client for the official public handbook screen."""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        opener: Any | None = None,
        max_rows: int = MAX_AGENT_ROWS,
    ) -> None:
        self.timeout = timeout
        self.max_rows = max(1, min(int(max_rows), 200))
        self._bootstrapped = False
        if opener is None:
            jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(jar)
            )
        self.opener = opener

    @staticmethod
    def _request(url: str, fields: list[tuple[str, str]] | None = None) -> urllib.request.Request:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": COURSE_CATALOG_URL,
            "User-Agent": "YonseiSkills/0.7 public-course-handbook",
        }
        data = None
        if fields is not None:
            data = urllib.parse.urlencode(fields).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        return urllib.request.Request(url, data=data, headers=headers)

    def _read(self, request: urllib.request.Request) -> bytes:
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, socket.timeout, TimeoutError, urllib.error.URLError) as error:
            raise BridgeError("The official course handbook is temporarily unavailable.") from error
        if len(body) > MAX_RESPONSE_BYTES:
            raise BridgeError("The official course handbook returned an oversized response.")
        return body

    def _json(self, path: str, fields: list[tuple[str, str]]) -> dict[str, Any]:
        body = self._read(self._request(BASE_URL + path, fields))
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BridgeError("The official course handbook response changed.") from error
        if not isinstance(payload, dict):
            raise BridgeError("The official course handbook response changed.")
        return payload

    def _bootstrap(self) -> None:
        if self._bootstrapped:
            return
        body = self._read(self._request(COURSE_CATALOG_URL))
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BridgeError("The official course handbook bootstrap changed.") from error
        menu_match = re.search(r'"menuId"\s*:\s*"([^"]+)"', html)
        program_match = re.search(r'"pgmId"\s*:\s*"([^"]+)"', html)
        if (
            menu_match is None
            or program_match is None
            or menu_match.group(1) != PUBLIC_MENU_ID
            or program_match.group(1) != PUBLIC_PROGRAM_ID
            or "contents/sch/sles/slessy/slessy0180" not in html
        ):
            raise BridgeError("The official course handbook bootstrap changed.")
        menu = self._json(
            MENU_PATH,
            [
                ("menuId", PUBLIC_MENU_ID),
                ("sysCd", "BIZ"),
                *CONTEXT_FIELDS,
            ],
        ).get("dsMenuInfo", [])
        if (
            not isinstance(menu, list)
            or not menu
            or menu[0].get("menuId") != PUBLIC_MENU_ID
            or menu[0].get("pgmId") != PUBLIC_PROGRAM_ID
        ):
            raise BridgeError("The official course handbook menu mapping changed.")
        self._bootstrapped = True

    def _current_term(self) -> tuple[str, str]:
        values = {
            "syy": "",
            "smtDivCd": "",
            "campsBusnsCd": "",
            "univCd": "",
            "faclyCd": "",
            "hy": "",
            "cdt": "%",
            "kwdDivCd": "1",
            "searchGbn": "",
            "kwd": "",
            "allKwd": "",
            "engChg": "",
            "prnGbn": "false",
            "lang": "",
            "campsDivCd": "",
            "stuno": "",
        }
        current = self._json(CURRENT_TERM_PATH, _form_map(values)).get("dmSyySmt", {})
        if not isinstance(current, dict):
            raise BridgeError("The official course handbook term response changed.")
        year = str(current.get("syy") or "").strip()
        semester = str(current.get("smtDivCd") or "").strip()
        if not re.fullmatch(r"20\d{2}", year) or semester not in SEMESTER_LABELS:
            raise BridgeError("The official course handbook did not publish a current term.")
        return year, semester

    def _hierarchy(
        self,
        dataset: str,
        *,
        year: str,
        semester: str,
        first: str = "%",
        second: str = "%",
        third: str = "%",
    ) -> list[dict[str, Any]]:
        values = {
            "dsNm": dataset,
            "level": "B",
            "lv1": first,
            "lv2": second,
            "lv3": third,
            "sysinstDivCd": "%",
            "univGbn": "A",
            "findAuthGbn": "8",
            "syy": year,
            "smtDivCd": semester,
        }
        rows = self._json(HIERARCHY_PATH, _form_map(values)).get(dataset, [])
        if not isinstance(rows, list):
            raise BridgeError("The official course handbook filter response changed.")
        return [row for row in rows if isinstance(row, dict)]

    def search(
        self,
        *,
        year: str | None = None,
        semester: str | None = None,
        campus: str | None = None,
        college: str | None = None,
        department: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        self._bootstrap()
        if year and semester:
            current_year, current_semester = "", ""
        else:
            current_year, current_semester = self._current_term()
        requested_year = str(year or current_year).strip()
        requested_semester = str(semester or current_semester).strip()
        semester_code = SEMESTER_CODES.get(requested_semester)
        applied: dict[str, bool] = {
            "year": bool(re.fullmatch(r"20\d{2}", requested_year)),
            "semester": semester_code is not None,
        }
        if not applied["year"] or semester_code is None:
            unmatched = [name for name, matched in applied.items() if not matched]
            return self._mapping_failure(applied, unmatched)

        campuses = self._hierarchy(
            "dsCampsBusnsCd",
            year=requested_year,
            semester=semester_code,
        )
        campus_row = _resolve_row(campuses, campus) if campus else (campuses[0] if campuses else None)
        if campus:
            applied["campus"] = campus_row is not None
        if campus_row is None:
            return self._mapping_failure(applied, ["campus"])

        college_row: dict[str, Any] | None = None
        campus_candidates = [campus_row]
        if college and not campus:
            campus_candidates.extend(row for row in campuses if row is not campus_row)
        for candidate in campus_candidates:
            colleges = self._hierarchy(
                "dsUnivCd",
                year=requested_year,
                semester=semester_code,
                first=str(candidate.get("deptCd") or "%"),
            )
            college_row = _resolve_row(colleges, college) if college else None
            if not college or college_row is not None:
                campus_row = candidate
                break
        if college:
            applied["college"] = college_row is not None
        if college and college_row is None:
            return self._mapping_failure(applied, ["college"])

        department_row: dict[str, Any] | None = None
        if department and college_row is not None:
            departments = self._hierarchy(
                "dsFaclyCd",
                year=requested_year,
                semester=semester_code,
                first=str(campus_row.get("deptCd") or "%"),
                second=str(college_row.get("deptCd") or "%"),
            )
            department_row = _resolve_row(departments, department)
        if department:
            applied["department"] = department_row is not None
        if department and department_row is None:
            return self._mapping_failure(applied, ["department"])
        if keyword:
            applied["keyword"] = True

        conditions = {
            "syy": requested_year,
            "smtDivCd": semester_code,
            "campsBusnsCd": str(campus_row.get("deptCd") or ""),
            "univCd": str(college_row.get("deptCd") or "") if college_row else "",
            "faclyCd": str(department_row.get("deptCd") or "") if department_row else "",
            "hy": "",
            "cdt": "%",
            "kwdDivCd": "1",
            "searchGbn": "1",
            "kwd": "",
            "allKwd": str(keyword or "").strip(),
            "engChg": "",
            "prnGbn": "false",
            "lang": "",
            "campsDivCd": "",
            "stuno": "",
        }
        raw_rows = self._json(SEARCH_PATH, _form_map(conditions)).get("dsSles251", [])
        if not isinstance(raw_rows, list):
            raise BridgeError("The official course handbook result response changed.")
        raw_rows = [row for row in raw_rows if isinstance(row, dict)]
        limited = len(raw_rows) >= 200
        notices: list[str] = []
        if limited:
            notices.append(
                "공식 수강편람이 검색 결과를 200건으로 제한했습니다. "
                "학과나 과목명을 추가하면 전체 후보를 더 정확히 확인할 수 있습니다."
            )
        if len(raw_rows) > self.max_rows:
            notices.append(
                f"응답 크기를 줄이기 위해 공식 결과 중 앞 {self.max_rows}건을 반환했습니다."
            )
        rows = [_course_row(row, index) for index, row in enumerate(raw_rows[: self.max_rows])]
        selected_filters = {
            "학년도/학기": [requested_year, SEMESTER_LABELS[semester_code]],
            "구분": [_row_label(campus_row)],
            "대학(원)/분류": [_row_label(college_row)] if college_row else [],
            "개설학과": [_row_label(department_row)] if department_row else [],
            "통합검색": [str(keyword).strip()] if keyword else [],
        }
        return {
            "schema": "yonsei-course-catalog-command/v1",
            "state": "available" if rows else "no_results",
            "source": "underwood-course-handbook",
            "source_url": COURSE_CATALOG_URL,
            "transport": "direct_https_json",
            "browser_used": False,
            "login_required": False,
            "registration_period_required": False,
            "filters": selected_filters,
            "requested_filters_applied": applied,
            "unmatched_filters": [],
            "result_limited": limited,
            "returned_result_limited": len(raw_rows) > self.max_rows,
            "official_result_count": len(raw_rows),
            "returned_result_count": len(rows),
            "notices": notices,
            "rows": rows,
        }

    @staticmethod
    def _mapping_failure(applied: dict[str, bool], unmatched: list[str]) -> dict[str, Any]:
        return {
            "schema": "yonsei-course-catalog-command/v1",
            "state": "field_mapping_required",
            "source": "underwood-course-handbook",
            "source_url": COURSE_CATALOG_URL,
            "transport": "direct_https_json",
            "browser_used": False,
            "login_required": False,
            "registration_period_required": False,
            "filters": {},
            "requested_filters_applied": applied,
            "unmatched_filters": unmatched,
            "result_limited": False,
            "returned_result_limited": False,
            "official_result_count": 0,
            "returned_result_count": 0,
            "notices": [],
            "rows": [],
        }
