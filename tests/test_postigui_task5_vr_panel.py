"""Post-Phase-IGUI Task 5 (MR-VR-1) - variance-reduction efficiency panel tests.

Pure-Python, dependency-light structural + integrity checks on the shipped
offline-UI artifacts (ui_data.json + ui_app.html). The exhaustive in-browser
render / 0-network / 0-JS-error proof lives in scripts/ui_app_self_test.cjs
(jsdom); this module independently confirms:

  * the ADDITIVE contract bump 1.21.0 -> 1.22.0 (ONE new top-level key
    ``postigui_vr``; every pre-existing key still present);
  * the panel figures (VR ratios + CIs, ESS, n*, unbiasedness, tail study,
    adoption materiality) are carried BIT-FOR-BIT from the governed Task-4
    model-output report (no recomputation);
  * the governed headline 39,975.654628199336 is unchanged / not relabelled;
  * the antithetic-99.5% INEFFECTIVE disclosure is present;
  * the new section is digested (A2) and the manifest required-keys advanced;
  * zero-install preserved (no external refs added; the embedded payload equals
    the standalone ui_data.json).
"""
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DATA = os.path.join(REPO, "ui_data.json")
UI_APP = os.path.join(REPO, "ui_app.html")
VR_REPORT = os.path.join(REPO, "docs", "validation",
                         "POSTIGUI_TASK4_VARIANCE_REDUCTION.json")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GOVERNED_HEADLINE = 39975.654628199336


class PostIguiTask5VrPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(UI_DATA, encoding="utf-8") as fh:
            cls.data = json.load(fh)
        with open(VR_REPORT, encoding="utf-8") as fh:
            cls.rep = json.load(fh)
        cls.vr = cls.data.get("postigui_vr")
        cls.man = cls.data["contract_manifest"]

    def test_contract_bumped_additively_to_122(self):
        self.assertEqual(self.data["contract_version"], "1.22.0")
        self.assertEqual(self.man["expected_contract_version"], "1.22.0")
        # additive: pre-existing 1.21.0 keys all still present
        for k in ("explainer", "a11y_audit", "owner_decision_p31", "governance",
                  "capital", "verdicts"):
            self.assertIn(k, self.data)

    def test_vr_section_present_and_well_formed(self):
        self.assertIsInstance(self.vr, dict)
        self.assertEqual(self.vr["candidate_id"], "MR-VR-1")
        self.assertEqual(self.vr["classification"], "EFFICIENCY")
        self.assertEqual(len(self.vr["techniques"]), 4)

    def test_required_keys_advanced(self):
        req = self.man["required_top_level_keys"]
        self.assertIn("postigui_vr", req)
        self.assertEqual(self.man["key_count"], len(req))

    def test_section_digested(self):
        sd = self.man["section_digests"]
        self.assertIn("postigui_vr", sd)
        self.assertTrue(HEX64.match(sd["postigui_vr"]))
        # digests cover exactly the top-level keys except the manifest itself
        expected = sorted(k for k in self.data.keys() if k != "contract_manifest")
        self.assertEqual(sorted(sd.keys()), expected)

    def test_vr_ratios_carried_bit_for_bit(self):
        self.assertEqual(self.vr["variance_reduction_ratios"],
                         self.rep["replicate_study"]["variance_reduction_ratios"])
        for k in ("antithetic", "crn", "sobol_qmc"):
            r = self.vr["variance_reduction_ratios"][k]
            self.assertLessEqual(r["ci95_lo"], r["ratio"])
            self.assertLessEqual(r["ratio"], r["ci95_hi"])
        # the two useful levers and the threshold dispositions
        self.assertTrue(self.vr["variance_reduction_ratios"]["sobol_qmc"]["useful_ge_threshold"])
        self.assertTrue(self.vr["variance_reduction_ratios"]["crn"]["useful_ge_threshold"])

    def test_ess_and_nstar_carried(self):
        self.assertEqual(self.vr["effective_sample_size"],
                         self.rep["replicate_study"]["effective_sample_size"])
        self.assertEqual(self.vr["n_star_for_target_se"],
                         self.rep["replicate_study"]["n_star_for_target_se"])
        self.assertEqual(self.vr["target_se_rel"],
                         self.rep["replicate_study"]["target_se_rel"])

    def test_unbiasedness_carried(self):
        self.assertEqual(self.vr["unbiasedness"],
                         self.rep["replicate_study"]["unbiasedness"])
        self.assertTrue(self.vr["unbiasedness"]["all_within_tol"])

    def test_antithetic_995_ineffective_disclosed(self):
        ts = self.vr["tail_study"]
        self.assertEqual(ts, self.rep["tail_study"])
        self.assertTrue(ts["antithetic_ineffective_at_995"])
        self.assertFalse(ts["antithetic_work_normalised_ratio"]["useful_ge_threshold"])

    def test_adoption_reported_not_applied(self):
        am = self.vr["adoption_materiality"]
        self.assertEqual(am, self.rep["adoption_materiality"])
        self.assertFalse(am["is_material"])
        self.assertFalse(am["applied"])

    def test_governed_headline_invariant_not_relabelled(self):
        hi = self.vr["headline_invariance"]
        self.assertEqual(hi, self.rep["governed_headline_invariance"])
        self.assertTrue(hi["bit_identical"])
        self.assertEqual(hi["before"]["frozen_t_component_scr"], GOVERNED_HEADLINE)
        self.assertEqual(hi["after"]["frozen_t_component_scr"], GOVERNED_HEADLINE)

    def test_digest_and_validation_gate_carried(self):
        self.assertEqual(self.vr["digest"], self.rep["digest"])
        self.assertTrue(self.vr["validation_gate"]["ok"])
        self.assertEqual(self.vr["validation_gate"]["n_checks"], 16)
        self.assertFalse(self.vr["provenance"]["recomputes_model_quantity"])

    def test_ui_app_renders_panel_and_tab(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn('id="vrpanel"', html)
        self.assertIn("function renderVrPanel(", html)
        self.assertIn('["vrpanel","Variance Reduction (MR-VR-1)"]', html)

    def test_embedded_payload_matches_standalone(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        tok = "/*__UI_DATA__*/"
        i = html.find(tok) + len(tok)
        j = html.find("</script>", i)
        emb = json.loads(html[i:j])
        self.assertEqual(emb["contract_version"], "1.22.0")
        self.assertIn("postigui_vr", emb)
        self.assertEqual(emb["postigui_vr"], self.vr)
        self.assertEqual(emb["contract_manifest"]["root_digest"],
                         self.man["root_digest"])

    def test_no_external_refs_in_ui_app(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        ext = [u for u in re.findall(r"https?://[^\s\"'<>]+", html)
               if "www.w3.org" not in u]
        self.assertEqual(ext, [], "unexpected external refs: %r" % ext[:5])


if __name__ == "__main__":
    unittest.main()
