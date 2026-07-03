"""PC-1c: every console page must carry the shared navigation bar
(owner report 2026-07-03: pages were not inter-accessible)."""

import os
import sys
import tempfile
import threading
import unittest
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (_REPO, os.path.join(_REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_gui
from par_model_v2.viewer.igui_portfolio_builder import NAV_LINKS

PAGES = ["/", "/model-points", "/assumptions", "/esg", "/run-gate",
         "/run-execution", "/cashflows", "/stress", "/calibration",
         "/history", "/portfolio"]


class TestNavOnEveryPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = run_gui.make_server(
            0, os.path.join(tempfile.mkdtemp(prefix="nav_"), "mi.json"))
        host, port = cls.srv.server_address
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = "http://%s:%d" % (host, port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_every_console_page_has_exactly_one_nav_with_all_links(self):
        for page in PAGES:
            with urllib.request.urlopen(self.base + page, timeout=15) as r:
                html = r.read().decode("utf-8")
            self.assertEqual(html.count("<nav "), 1, page)
            for href, _label in NAV_LINKS:
                self.assertIn('href="%s"' % href, html,
                              "%s missing link to %s" % (page, href))

    def test_active_page_is_highlighted(self):
        with urllib.request.urlopen(self.base + "/portfolio", timeout=15) as r:
            html = r.read().decode("utf-8")
        nav = html[html.index("<nav "):html.index("</nav>")]
        self.assertIn('href="/portfolio" style="text-decoration:none;'
                      'padding:5px 11px;border-radius:7px;font-size:13px;'
                      'background:#2b6cff', nav)


if __name__ == "__main__":
    unittest.main()
