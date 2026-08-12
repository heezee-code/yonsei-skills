# End-to-end validation

Last checked: 2026-08-12

This page separates an actual official-service run from local implementation
and cross-platform checks. It contains no student name, student number,
document contents, browser cookie, or certificate file.

## Actual official-service results

| Workflow | Result | Evidence |
| --- | --- | --- |
| Certificate free-print PDF | Completed | Authenticated Portal → internet certificate → immediate issue → free printer output; one document-number reservation; durable local PDF save; digest reread; official completion acknowledgement HTTP 200 |
| Certificate typography | Completed | One A4 page, 540,885 bytes; template-used Yonsei body face embedded as `/FontFile2`; bundled title and body font files both matched their pinned hashes; no generic substitute font accepted |
| Certificate replay | Completed | Saved PDF SHA-256 `eab91545b8dda64a72d41e0c89b5cffaca2117e43ac62f53fabe1230aa80469e`; deterministic replay matched |
| Certificate 0.11.0 regression | Local checks completed | Two-page page/object-specific logo and serial bindings, full render before reservation, exact `arm_id` job tracking, cached startup, and the 55-second hot-path budget are covered without reserving another live document number |
| Portal daily read | Completed before session expiry | Portal plus available scholarships, mileage, classes, graduation, teaching, LearnUs, and attendance sources were queried through the managed browser profile |
| Underwood public course handbook | Completed without browser or login | Exact English request `2026 / 2nd semester / Engineering` completed through the packaged MCP stdio server and official HTTPS JSON response in about 2.1 seconds; the browser endpoint was deliberately made unavailable, 50 structured rows were returned from the official 200-row capped result, and requested filters were read back |
| Public notice search | Completed | Both bounded official notice feeds returned 50 current entries without partial-fetch errors; detail pages and deadline extraction were checked |

## Cross-platform and package results

| Check | Result |
| --- | --- |
| Windows/macOS/Linux action routing | Certificate PDF, Windows named physical-printer routing, shuttle, and space paths covered by the three-OS CI matrix |
| Repository tests | All repository and plugin-local tests pass; the optional strict `pypdf` parse is skipped only when that dependency is unavailable |
| Plugin-local tests | All 14 discovered plugin test directories pass |
| Skill structure | All 52 skill folders pass the official `quick_validate.py`; all 52 UI metadata files contain a matching invocation prompt |
| Student downloads | Four deterministic archives build successfully; all 40 student workflows and both authorized Yonsei fonts are present; published checksums are verified |
| Marketplace | All 13 plugin entries validate as installable; 9 student plugins contain 40 student skills and 4 research/administration plugins contain 12 skills |

## Browser automation choice

Playwright and Selenium were reviewed for unattended browser setup. Playwright
can install pinned Chromium builds and runs headless by default; Selenium
Manager can discover and download matching drivers and browsers. Neither is a
runtime dependency here because a public catalogue query does not need browser
rendering, and bundling either would add a browser download and package setup to
the student's first use. The release check instead starts the packaged MCP
stdio server from the terminal, deliberately points any browser connection at
an unavailable local port, and requires the official structured result to
complete through direct HTTPS JSON.

- Playwright browser management: `https://playwright.dev/docs/browsers`
- Selenium Manager: `https://www.selenium.dev/documentation/selenium_manager/`

## Login-dependent acceptance still requiring a live student session

The public course handbook is not in this category. It uses no browser profile,
credential, cookie export, Accessibility permission, Screen Recording permission,
or Computer Use session. Personal mileage history and current registration data
remain login-dependent and are requested only when the student asks for them.

The managed browser session expired after the authenticated reads and
certificate run. The implementation now reports `login_required` instead of a
false empty or completed result. A current eligible shuttle trip and an
available space request therefore still require the student to complete the
official login screen and provide the exact trip/room, date, time, purpose, and
other required details. No guessed reservation or application was submitted.

Windows and Linux CI proves package and runtime compatibility, not a real
student-account transaction on those operating systems. A live reservation,
cancellation, space application, or physical-printer acceptance must be
reported only after the official history screen confirms it.
