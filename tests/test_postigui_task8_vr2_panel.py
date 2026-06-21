"""Post-Phase-IGUI Task 8 (MR-VR-2) - outer-loop variance-reduction panel tests.

Pure-Python, dependency-light structural + integrity checks on the shipped
offline-UI artifacts (ui_data.json + ui_app.html). The exhaustive in-browser
render / 0-network / 0-JS-error proof lives in scripts/ui_app_self_test.cjs
(jsdom); this module independently confirms:

  * the ADDITIVE contract bump 1.22.0 -> 1.23.0 (ONE new top-level key
    ``postigui_vr2``; every pre-existing key still present, including the
    MR-VR-1 ``postigui_vr`` from 1.22.0);
  * the panel figures (mean + SCR VR ratios + CIs, ESS, n*, unbiasedness,
    control-variate fit, adoption materiality) are carried BIT-FOR-BIT from the
    governed Task-7 model-output report (no recomputation);
  * the governed headline 39,975.654628199336 is unchanged / not relabelled;
  * the control-variate-alone-INEFFECTIVE-at-99.5%-SCR disclosure is present
    (work-normalised ratio below the 1.5x bar) and RQMC / stratification /
    RQMC+CV ARE useful on the tail (best technique stratified);
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
                         "POSTIGUI_TASK7_OUTER_VARIANCE_REDUCTION.json")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GOVERNED_HEADLINE = 39975.654628199336


class PostIguiTask8Vr2Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(UI_DATA, encoding="utf-8") as fh:
            cls.data = json.load(fh)
        with open(VR_REPORT, encoding="utf-8") as fh:
            cls.rep = json.load(fh)
        cls.vr2 = cls.data.get("postigui_vr2")
        cls.man = cls.data["contract_manifest"]

    def test_contract_bumped_additively_to_123(self):
        self.assertEqual(self.data["contract_version"], "1.23.0")
        self.assertEqual(self.man["expected_contract_version"], "1.23.0")
        # additive: pre-existing 1.22.0 keys all still present (incl MR-VR-1)
        for k in ("postigui_vr", "explainer", "a11y_audit", "owner_decision_p31",
                  "governance", "capital", "verdicts"):
            self.assertIn(k, self.data)

    def test_vr2_section_present_and_well_formed(self):
        self.assertIsInstance(self.vr2, dict)
        self.assertEqual(self.vr2["candidate_id"], "MR-VR-2")
        self.assertEqual(self.vr2["classification"], "EFFICIENCY")
        self.assertEqual(len(self.vr2["techniques"]), 4)

    def test_required_keys_advanced(self):
        req = self.man["required_top_level_keys"]
        self.assertIn("postigui_vr2", req)
        self.assertIn("postigui_vr", req)  # MR-VR-1 still required
        self.assertEqual(self.man["key_count"], len(req))

    def test_section_digested(self):
        sd = self.man["section_digests"]
        self.assertIn("postigui_vr2", sd)
        self.assertTrue(HEX64.match(sd["postigui_vr2"]))
        # digests cover exactly the top-level keys except the manifest itself
        expected = sorted(k for k in self.data.keys() if k != "contract_manifest")
        self.assertEqual(sorted(sd.keys()), expected)

    def test_mean_ratios_carried_bit_for_bit(self):
        self.assertEqual(self.vr2["mean_variance_reduction_ratios"],
                         self.rep["replicate_study"]["variance_reduction_ratios"])
        for k in ("sobol_rqmc", "control_variate", "stratified"):
            r = self.vr2["mean_variance_reduction_ratios"][k]
            self.assertLessEqual(r["ci95_lo"], r["ratio"])
            self.assertLessEqual(r["ratio"], r["ci95_hi"])

    def test_scr_tail_study_carried_and_disclosure(self):
        ts = self.vr2["scr_tail_study"]
        self.assertEqual(ts, self.rep["scr_tail_study"])
        rr = ts["variance_reduction_ratios"]
        # control-variate-alone INEFFECTIVE on the 99.5% SCR quantile leg
        self.assertFalse(rr["control_variate"]["useful_ge_threshold"])
        self.assertLess(rr["control_variate"]["ratio"], 1.5)
        # RQMC / stratification / RQMC+CV ARE useful on the tail
        self.assertTrue(rr["sobol_rqmc"]["useful_ge_threshold"])
        self.assertTrue(rr["stratified"]["useful_ge_threshold"])
        self.assertTrue(rr["rqmc_plus_cv"]["useful_ge_threshold"])
        self.assertEqual(self.vr2["best_tail_technique"], "stratified")
        self.assertIn("MEASURED", ts["disclosure"].upper())

    def test_control_variate_fit_carried(self):
        cv = self.vr2["control_variate_fit"]
        self.assertEqual(cv, self.rep["control_variate_fit"])
        # 1/(1-rho^2) consistent with rho carried
        self.assertAlmostEqual(cv["one_over_1_minus_rho2"],
                               1.0 / (1.0 - cv["rho"] ** 2), places=9)

    def test_ess_and_nstar_carried(self):
        self.assertEqual(self.vr2["mean_effective_sample_size"],
                         self.rep["replicate_study"]["effective_sample_size"])
        self.assertEqual(self.vr2["n_star_for_target_se"],
                         self.rep["replicate_study"]["n_star_for_target_se"])
        self.assertEqual(self.vr2["target_se_rel"],
                         self.rep["replicate_study"]["target_se_rel"])

    def test_unbiasedness_carried(self):
        self.assertEqual(self.vr2["mean_unbiasedness"],
                         self.rep["replicate_study"]["unbiasedness"])
        self.assertTrue(self.vr2["mean_unbiasedness"]["all_within_tol"])

    def test_adoption_reported_not_applied(self):
        am = self.vr2["adoption_materiality"]
        self.assertEqual(am, self.rep["adoption_materiality"])
        self.assertFalse(am["is_material"])
        self.assertFalse(am["applied"])

    def test_governed_headline_invariant_not_relabelled(self):
        hi = self.vr2["headline_invariance"]
        self.assertEqual(hi, self.rep["governed_headline_invariance"])
        self.assertTrue(hi["bit_identical"])
        self.assertEqual(hi["before"]["frozen_t_component_scr"], GOVERNED_HEADLINE)
        self.assertEqual(hi["after"]["frozen_t_component_scr"], GOVERNED_HEADLINE)

    def test_digest_and_validation_gate_carried(self):
        self.assertEqual(self.vr2["digest"], self.rep["digest"])
        self.assertTrue(self.vr2["validation_gate"]["ok"])
        self.assertEqual(self.vr2["validation_gate"]["n_checks"], 20)
        self.assertFalse(self.vr2["provenance"]["recomputes_model_quantity"])

    def test_ui_app_renders_panel_and_tab(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn('id="vr2panel"', html)
        self.assertIn("function renderVr2Panel(", html)
        self.assertIn('["vr2panel","Outer-Loop Variance Reduction (MR-VR-2)"]', html)
        # MR-VR-1 panel still present (additive, not replaced)
        self.assertIn('id="vrpanel"', html)
        self.assertIn("function renderVrPanel(", html)

    def test_embedded_payload_matches_standalone(self):
        with open(UI_APP, encoding="utf-8") as fh:
            html = fh.read()
        tok = "/*__UI_DATA__*/"
        i = html.find(tok) + len(tok)
        j = html.find("</script>", i)
        emb = json.loads(html[i:j])
        self.assertEqual(emb["contract_version"], "1.23.0")
        self.assertIn("postigui_vr2", emb)
        self.assertEqual(emb["postigui_vr2"], self.vr2)
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
