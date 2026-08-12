from __future__ import annotations

import json
import sys
import unittest
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_RUNTIME = ROOT / "plugins" / "yonsei-student-companion" / "runtime"
sys.path.insert(0, str(BRIDGE_RUNTIME))

from yonsei_bridge.cdp import BridgeError  # noqa: E402
from yonsei_bridge.course_catalog import (  # noqa: E402
    COURSE_CATALOG_URL,
    OfficialCourseCatalogClient,
)


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_arguments):
        return False

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class FakeOpener:
    def __init__(self, *, row_count: int = 2, valid_bootstrap: bool = True) -> None:
        self.row_count = row_count
        self.valid_bootstrap = valid_bootstrap
        self.requests = []

    @staticmethod
    def _json(value) -> FakeResponse:
        return FakeResponse(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def open(self, request, timeout: float):
        self.requests.append((request, timeout))
        url = request.full_url
        if url == COURSE_CATALOG_URL:
            html = (
                '<script>cpr.core.Platform.INSTANCE.initParameter({'
                '"menuId":"M105675","pgmId":"P004512",'
                '"uri":"contents/sch/sles/slessy/slessy0180"});</script>'
                if self.valid_bootstrap
                else "<html>changed</html>"
            )
            return FakeResponse(html.encode("utf-8"))
        if url.endswith("/com/cmsv/MenuCtr/findMenu.do"):
            return self._json(
                {"dsMenuInfo": [{"menuId": "M105675", "pgmId": "P004512"}]}
            )
        fields = urllib.parse.parse_qs(
            request.data.decode("utf-8"), keep_blank_values=True
        )
        if url.endswith("findSlesYySmtScheList.do"):
            return self._json({"dmSyySmt": {"syy": "2026", "smtDivCd": "20"}})
        if url.endswith("findSchSlesHandbList.do"):
            dataset = fields["@d1#dsNm"][0]
            if dataset == "dsCampsBusnsCd":
                rows = [
                    {
                        "deptCd": "s1",
                        "deptNm": "학부(신촌)",
                        "engDeptNm": "Undergraduate Programs",
                    }
                ]
            elif dataset == "dsUnivCd":
                rows = [
                    {
                        "deptCd": "s1104",
                        "deptNm": "공과대학",
                        "engDeptNm": "College of Engineering",
                    }
                ]
            else:
                rows = [
                    {
                        "deptCd": "04202",
                        "deptNm": "전기전자공학전공",
                        "engDeptNm": "Electrical and Electronic Engineering",
                    }
                ]
            return self._json({dataset: rows})
        if url.endswith("findAtnlcHandbList.do"):
            rows = [
                {
                    "subjtnbCorsePrcts": f"ENG1108-{index + 1:02d}-01",
                    "subjtnb": "ENG1108",
                    "corseDvclsNo": f"{index + 1:02d}",
                    "prctsCorseDvclsNo": "01",
                    "subjtNm": "공학정보처리",
                    "subjtEngNm": "ENGINEERING INFORMATION PROCESSING",
                    "cdt": 3,
                    "cgprfNm": "홍민석",
                    "lctreTimeNm": "월7,8/목1,2",
                    "lecrmNm": "공A213/공A685",
                    "estblDeprtNm": "공과대학 공과대학공통",
                    "campsDivNm": "신촌",
                }
                for index in range(self.row_count)
            ]
            return self._json({"dsSles251": rows})
        raise AssertionError(f"Unexpected request: {url}")


class OfficialCourseCatalogClientTests(unittest.TestCase):
    def test_queries_english_filters_without_a_browser_or_login(self):
        opener = FakeOpener()
        result = OfficialCourseCatalogClient(opener=opener, max_rows=1).search(
            year="2026",
            semester="2학기",
            college="College of Engineering",
            department="Electrical and Electronic Engineering",
            keyword="공학정보처리",
        )

        self.assertEqual(result["state"], "available")
        self.assertEqual(result["transport"], "direct_https_json")
        self.assertFalse(result["browser_used"])
        self.assertFalse(result["login_required"])
        self.assertEqual(result["official_result_count"], 2)
        self.assertEqual(result["returned_result_count"], 1)
        self.assertTrue(result["returned_result_limited"])
        self.assertFalse(result["result_limited"])
        self.assertEqual(
            result["rows"][0]["fields"]["학정번호-분반-실습"],
            "ENG1108-01-01",
        )
        search_request = next(
            request
            for request, _timeout in opener.requests
            if request.full_url.endswith("findAtnlcHandbList.do")
        )
        fields = urllib.parse.parse_qs(
            search_request.data.decode("utf-8"), keep_blank_values=True
        )
        self.assertEqual(fields["@d1#smtDivCd"], ["20"])
        self.assertEqual(fields["@d1#campsBusnsCd"], ["s1"])
        self.assertEqual(fields["@d1#univCd"], ["s1104"])
        self.assertEqual(fields["@d1#faclyCd"], ["04202"])
        self.assertEqual(fields["@d1#allKwd"], ["공학정보처리"])

    def test_uses_the_official_current_term_when_omitted(self):
        opener = FakeOpener(row_count=1)
        result = OfficialCourseCatalogClient(opener=opener).search()

        self.assertEqual(result["filters"]["학년도/학기"], ["2026", "2학기"])
        self.assertTrue(
            any(
                request.full_url.endswith("findSlesYySmtScheList.do")
                for request, _timeout in opener.requests
            )
        )

    def test_marks_the_official_two_hundred_row_cap(self):
        result = OfficialCourseCatalogClient(
            opener=FakeOpener(row_count=200), max_rows=50
        ).search(year="2026", semester="2학기", college="공과대학")

        self.assertTrue(result["result_limited"])
        self.assertTrue(result["returned_result_limited"])
        self.assertEqual(result["official_result_count"], 200)
        self.assertEqual(result["returned_result_count"], 50)
        self.assertTrue(any("200건" in notice for notice in result["notices"]))

    def test_invalid_semester_is_not_sent_to_the_search_endpoint(self):
        opener = FakeOpener()
        result = OfficialCourseCatalogClient(opener=opener).search(
            year="2026", semester="third semester"
        )

        self.assertEqual(result["state"], "field_mapping_required")
        self.assertEqual(result["unmatched_filters"], ["semester"])
        self.assertFalse(
            any(
                request.full_url.endswith("findAtnlcHandbList.do")
                for request, _timeout in opener.requests
            )
        )

    def test_rejects_a_changed_bootstrap_before_querying(self):
        with self.assertRaisesRegex(BridgeError, "bootstrap changed"):
            OfficialCourseCatalogClient(
                opener=FakeOpener(valid_bootstrap=False)
            ).search(year="2026", semester="2학기")


if __name__ == "__main__":
    unittest.main()
