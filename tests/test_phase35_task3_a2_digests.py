"""Phase 35 Task 3 (gap A2) - per-section content digest + verifier tests.

Pure-Python, dependency-light structural + integrity checks on the shipped
artifacts. The exhaustive *in-browser recompute matches the build digests*
proof lives in the jsdom self-test (scripts/ui_app_self_test.cjs) and the
build-time Node cross-check in scripts/build_phase35_task3_a2_digests.py; this
module independently confirms the manifest shape, the additive contract bump,
the embedded-vs-standalone payload agreement, and re-derives the root_digest in
pure Python (the section-digest map is all strings, so it is reproducible here
with no JS/Python float-formatting concern).
"""
import hashlib
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DATA = os.path.join(REPO, "ui_data.json")
UI_APP = os.path.join(REPO, "ui_app.html")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canon(v):
    """Canonical serialiser matching the embedded JS _ciCanon (sorted keys,
    compact separators, JS-native number formatting). Only used here over the
    section-digest map (string keys -> 64-hex strings), so no float formatting
    is exercised."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return "{" + ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + _canon(v[k])
            for k in sorted(v.keys())) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_canon(x) for x in v) + "]"
    raise AssertionError("unexpected type in section-digest map: %r" % type(v))


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class Phase35Task3A2Digests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(UI_DATA, encoding="utf-8") as fh:
            cls.data = json.load(fh)
        cls.man = cls.data["contract_manifest"]

    def test_contract_bumped_to_120(self):
        self.assertEqual(self.data["contract_version"], "1.23.0")
        self.assertEqual(self.man["expected_contract_version"], "1.23.0")

    def test_manifest_digest_fields_present(self):
        self.assertEqual(self.man["digest_algo"], "sha256")
        self.assertIn("section_digests", self.man)
        self.assertIn("root_digest", self.man)
        self.assertTrue(HEX64.match(self.man["root_digest"]))

    def test_digests_cover_every_section_except_manifest(self):
        expected = sorted(k for k in self.data.keys() if k != "contract_manifest")
        self.assertEqual(sorted(self.man["section_digests"].keys()), expected)

    def test_each_section_digest_is_well_formed_sha256(self):
        for k, d in self.man["section_digests"].items():
            self.assertTrue(HEX64.match(d), "bad digest for %r: %r" % (k, d))

    def test_root_digest_derivation_reproducible_in_python(self):
        # root_digest = sha256(canonical(section_digests)); independent re-derive.
        self.assertEqual(_sha(_canon(self.man["section_digests"])),
                         self.man["root_digest"])

    def test_no_new_top_level_key(self):
        # A2 is additive INSIDE contract_manifest; the top-level key set must be
        # unchanged from the 1.19.0 (A1) payload.
        self.assertNotIn("section_digests", self.data)
        self.assertNotIn("root_digest", self.data)
        self.assertIn("a11y_audit", self.data)  # 1.19.0 key still present

    def test_embedded_payload_matches_standalone(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        tok = "/*__UI_DATA__*/"
        i = html.find(tok) + len(tok)
        j = html.find("</script>", i)
        emb = json.loads(html[i:j])
        self.assertEqual(emb["contract_version"], "1.23.0")
        self.assertEqual(emb["contract_manifest"]["root_digest"],
                         self.man["root_digest"])
        self.assertEqual(emb["contract_manifest"]["section_digests"],
                         self.man["section_digests"])

    def test_verifier_helpers_embedded(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        for needle in ("_ciSha256", "_ciCanon", "_ciSectionDigests",
                       "renderIntegrityVerifierHtml"):
            self.assertIn(needle, html)

    def test_no_external_refs_in_ui_app(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        ext = [u for u in re.findall(r"https?://[^\s\"'<>]+", html)
               if "www.w3.org" not in u]
        self.assertEqual(ext, [], "unexpected external refs: %r" % ext[:5])


if __name__ == "__main__":
    unittest.main()
