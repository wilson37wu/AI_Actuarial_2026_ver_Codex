#!/usr/bin/env python3
"""Phase 35 Task 3 (gap A2) - per-section cryptographic content digest in the
H1 integrity panel + in-browser tamper-evident verifier.

ADDITIVE contract bump 1.19.0 -> 1.20.0. The bump is purely a manifest-schema
addition: three new keys are added INSIDE the existing ``contract_manifest``
envelope - ``digest_algo`` ("sha256"), ``section_digests`` (a per-top-level-section
SHA-256 over the canonical form of each section value) and ``root_digest`` (a
SHA-256 over the canonical form of the sorted section-digest map). No NEW
top-level key is introduced; every pre-existing ``ui_data.json`` key renders
bit-identically. The governed model figures are untouched.

Why this closes a real gap: Phase 34 Task 2 (gap H1) proved the required data
SECTIONS are PRESENT and the contract version matches, but it could not detect
whether the CONTENT of a section had been altered. A2 adds tamper-evidence: the
build embeds a SHA-256 digest of every section; the page recomputes those
digests IN THE BROWSER from the embedded payload (a self-contained pure-JS
SHA-256 + canonical serialiser - NO network, NO storage API, works under
``file://``) and renders a verified/altered table plus an overall badge.

Design (the digest scope, frozen here):
  * canonical(value) = recursive JSON with object keys sorted lexicographically,
    compact separators, and JS-native number formatting (String(Number)). The
    SAME canonical serialiser source is embedded in the page AND executed in
    Node at build time, so the build-time digests are computed by the identical
    code the browser runs -> byte-for-byte agreement by construction (no
    Python/JS float-formatting divergence is possible).
  * section_digests[k] = sha256(canonical(DATA[k]))  for every top-level key k
    EXCEPT ``contract_manifest`` (the digests live inside it; excluding it
    avoids self-reference).
  * root_digest = sha256(canonical(section_digests)).

What this script patches IN PLACE (the established direct-artifact pattern - the
live ``ui_app.html`` carries Phase 34/35 markup the legacy ``build_ui_data.py``
template does not regenerate, so the artifacts are patched directly):
  1. ui_data.json (standalone)        : contract 1.20.0 + manifest digest fields
  2. ui_app.html  (embedded payload)  : same data, byte-synced into the <script>
  3. ui_app.html  (JS)               : shared canonical+SHA-256 helpers +
                                        renderIntegrityVerifierHtml() rendered
                                        read-only into the Integrity (H1) panel

NO model parameter changes. The binding Phase 30 stop-rule stands and the
MR-016/MR-017 owner decision is not pre-empted.

Run:  python3 scripts/build_phase35_task3_a2_digests.py [--check]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DATA = os.path.join(REPO, "ui_data.json")
UI_APP = os.path.join(REPO, "ui_app.html")

PRIOR_CONTRACT = "1.19.0"
NEW_CONTRACT = "1.20.0"
GENERATOR = "scripts/build_phase35_task3_a2_digests.py (Phase 35 Task 3, gap A2)"
DIGEST_ALGO = "sha256"

# --- Shared, dependency-free JS: canonical serialiser + pure-JS SHA-256 +
#     section-digest computation. This EXACT source is (a) embedded in the page
#     for the in-browser verifier and (b) eval'd in Node at build time so the
#     shipped digests are produced by the identical code the browser runs. ---
SHARED_JS = r"""
  // Phase 35 Task 3 (gap A2): dependency-free content-integrity primitives.
  // canonical JSON (sorted keys, compact, JS-native numbers) + pure-JS SHA-256.
  // NO network, NO storage API, works offline under file://. The build embeds
  // SHA-256 digests computed by this SAME source, so the browser recompute
  // agrees byte-for-byte by construction.
  function _ciCanon(v){
    if(v===null||v===undefined) return "null";
    var t=typeof v;
    if(t==="number") return isFinite(v)?String(v):"null";
    if(t==="boolean") return v?"true":"false";
    if(t==="string") return JSON.stringify(v);
    if(Object.prototype.toString.call(v)==="[object Array]"){
      var a=[]; for(var i=0;i<v.length;i++) a.push(_ciCanon(v[i]));
      return "["+a.join(",")+"]";
    }
    var ks=Object.keys(v).sort(), p=[];
    for(var j=0;j<ks.length;j++) p.push(JSON.stringify(ks[j])+":"+_ciCanon(v[ks[j]]));
    return "{"+p.join(",")+"}";
  }
  function _ciSha256(str){
    function rotr(x,n){return (x>>>n)|(x<<(32-n));}
    var K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
      0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
      0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
      0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
      0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
      0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
      0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
      0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    var H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    var b=[],i,c,c2,cp;
    for(i=0;i<str.length;i++){
      c=str.charCodeAt(i);
      if(c<0x80) b.push(c);
      else if(c<0x800) b.push(0xc0|(c>>6),0x80|(c&0x3f));
      else if(c>=0xd800&&c<0xdc00){ c2=str.charCodeAt(++i); cp=0x10000+(((c&0x3ff)<<10)|(c2&0x3ff));
        b.push(0xf0|(cp>>18),0x80|((cp>>12)&0x3f),0x80|((cp>>6)&0x3f),0x80|(cp&0x3f)); }
      else b.push(0xe0|(c>>12),0x80|((c>>6)&0x3f),0x80|(c&0x3f));
    }
    var l=b.length; b.push(0x80);
    while(b.length%64!==56) b.push(0);
    var bl=l*8, hi=Math.floor(bl/0x100000000);
    b.push((hi>>>24)&0xff,(hi>>>16)&0xff,(hi>>>8)&0xff,hi&0xff);
    b.push((bl>>>24)&0xff,(bl>>>16)&0xff,(bl>>>8)&0xff,bl&0xff);
    var w=new Array(64),t,a,bb,cc,d,e,f,g,h,S0,S1,ch,maj,t1,t2,s0,s1;
    for(i=0;i<b.length;i+=64){
      for(t=0;t<16;t++) w[t]=((b[i+4*t]<<24)|(b[i+4*t+1]<<16)|(b[i+4*t+2]<<8)|(b[i+4*t+3]))|0;
      for(t=16;t<64;t++){
        s0=rotr(w[t-15],7)^rotr(w[t-15],18)^(w[t-15]>>>3);
        s1=rotr(w[t-2],17)^rotr(w[t-2],19)^(w[t-2]>>>10);
        w[t]=(((w[t-16]+s0)|0)+((w[t-7]+s1)|0))|0;
      }
      a=H[0];bb=H[1];cc=H[2];d=H[3];e=H[4];f=H[5];g=H[6];h=H[7];
      for(t=0;t<64;t++){
        S1=rotr(e,6)^rotr(e,11)^rotr(e,25);
        ch=(e&f)^((~e)&g);
        t1=(((((h+S1)|0)+((ch+K[t])|0))|0)+w[t])|0;
        S0=rotr(a,2)^rotr(a,13)^rotr(a,22);
        maj=(a&bb)^(a&cc)^(bb&cc);
        t2=(S0+maj)|0;
        h=g;g=f;f=e;e=(d+t1)|0;d=cc;cc=bb;bb=a;a=(t1+t2)|0;
      }
      H[0]=(H[0]+a)|0;H[1]=(H[1]+bb)|0;H[2]=(H[2]+cc)|0;H[3]=(H[3]+d)|0;
      H[4]=(H[4]+e)|0;H[5]=(H[5]+f)|0;H[6]=(H[6]+g)|0;H[7]=(H[7]+h)|0;
    }
    var hex="";
    for(i=0;i<8;i++) hex+=("00000000"+(H[i]>>>0).toString(16)).slice(-8);
    return hex;
  }
  function _ciSectionDigests(obj){
    var ks=Object.keys(obj).filter(function(k){return k!=="contract_manifest";}).sort();
    var sd={};
    for(var i=0;i<ks.length;i++) sd[ks[i]]=_ciSha256(_ciCanon(obj[ks[i]]));
    return { section_digests:sd, root_digest:_ciSha256(_ciCanon(sd)), keys:ks };
  }
"""

# --- Browser-only render function (uses esc/DATA already in the page). ---
VERIFIER_RENDER_JS = r"""
  // Phase 35 Task 3 (gap A2): in-browser tamper-evident content verifier.
  // RECOMPUTES the per-section SHA-256 digests from the embedded payload and
  // compares them to the build-time digests in contract_manifest. This is the
  // one integrity surface that DOES recompute - but it recomputes a DIGEST of
  // the embedded snapshot, not any model figure. No network, no storage API.
  function renderIntegrityVerifierHtml(){
    var man=DATA&&DATA.contract_manifest;
    var head='<h3 style="margin:18px 0 6px">Content integrity &mdash; per-section SHA-256 (recomputed in the browser)</h3>';
    if(!man||!man.section_digests||!man.root_digest){
      return head+'<p class="note">This snapshot predates per-section content digests (pre-1.20.0); '+
        'the integrity panel can verify section <b>presence</b> but not content. No figures are recomputed.</p>';
    }
    var algo=String(man.digest_algo||"sha256");
    var stored=man.section_digests, storedRoot=String(man.root_digest);
    var rec=_ciSectionDigests(DATA);
    var recSd=rec.section_digests;
    // union of stored + recomputed section keys (detect added/removed sections)
    var seen={}, all=[], i;
    var sk=Object.keys(stored), rk=rec.keys;
    for(i=0;i<sk.length;i++){ if(!seen[sk[i]]){seen[sk[i]]=1; all.push(sk[i]);} }
    for(i=0;i<rk.length;i++){ if(!seen[rk[i]]){seen[rk[i]]=1; all.push(rk[i]);} }
    all.sort();
    var rows='', nVer=0, nAlt=0, nMiss=0, nExtra=0;
    for(i=0;i<all.length;i++){
      var k=all[i], s=stored[k], r=recSd[k], st, cls;
      if(s===undefined){ st='added (no build digest)'; cls='fail'; nExtra++; }
      else if(r===undefined){ st='section missing'; cls='fail'; nMiss++; }
      else if(s===r){ st='verified'; cls='pass'; nVer++; }
      else { st='ALTERED'; cls='fail'; nAlt++; }
      rows+='<tr data-int-verify="'+(cls==='pass'?'ok':'alt')+'">'+
        '<td class="mono">'+esc(k)+'</td>'+
        '<td class="mono" title="'+esc(s||"--")+'">'+esc((s||"--").slice(0,16))+'</td>'+
        '<td class="mono" title="'+esc(r||"--")+'">'+esc((r||"--").slice(0,16))+'</td>'+
        '<td><span class="chip '+cls+'">'+esc(st)+'</span></td></tr>';
    }
    var rootMatch=(rec.root_digest===storedRoot);
    var allOk=(nAlt===0 && nMiss===0 && nExtra===0 && rootMatch);
    var badge=allOk
      ? '<span class="chip pass">INTEGRITY VERIFIED</span>'
      : '<span class="chip fail">CONTENT ALTERED</span>';
    var html=head+
      '<p class="note">Each top-level data section (every key except '+
      '<span class="mono">contract_manifest</span>) carries a build-time '+
      '<span class="mono">'+esc(algo)+'</span> digest written by '+
      '<span class="mono">'+esc(GENERATOR_LABEL)+'</span>. This panel RECOMPUTES those digests in your '+
      'browser from the embedded snapshot using a self-contained pure-JS SHA-256 '+
      '(no network, no storage) and compares them. A digest mismatch means the embedded content '+
      'was altered after the build. It recomputes a content digest, <b>not</b> a model figure.</p>'+
      '<div class="cards">'+
      '<div class="card"><div class="k">Overall</div><div class="v">'+badge+'</div></div>'+
      '<div class="card"><div class="k">Sections verified</div><div class="v">'+nVer+' / '+all.length+'</div></div>'+
      '<div class="card"><div class="k">Root digest match</div><div class="v">'+(rootMatch?'<span class="chip pass">yes</span>':'<span class="chip fail">no</span>')+'</div></div>'+
      '<div class="card"><div class="k">Digest algorithm</div><div class="v mono">'+esc(algo)+'</div></div>'+
      '</div>'+
      '<table class="a11ytbl intverify"><thead><tr><th>Section</th>'+
      '<th>Build digest (sha256, first 16)</th><th>Recomputed (first 16)</th>'+
      '<th>Status</th></tr></thead><tbody>'+rows+'</tbody></table>'+
      '<p class="muted">Root digest (build): <span class="mono" title="'+esc(storedRoot)+'">'+esc(storedRoot.slice(0,24))+'&hellip;</span> '+
      '&middot; recomputed: <span class="mono" title="'+esc(rec.root_digest)+'">'+esc(rec.root_digest.slice(0,24))+'&hellip;</span> '+
      '&middot; '+all.length+' sections digested; verifier runs entirely offline in the browser.</p>';
    return html;
  }
"""

NODE_DRIVER = r"""
const fs = require("fs");
%s
const data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const r = _ciSectionDigests(data);
process.stdout.write(JSON.stringify({
  section_digests: r.section_digests,
  root_digest: r.root_digest,
  keys: r.keys,
  selfcheck_abc: _ciSha256("abc"),
  selfcheck_empty: _ciSha256(""),
}));
"""

KNOWN_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
KNOWN_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def compute_digests_via_node(data: dict) -> dict:
    """Run the EXACT embedded JS in Node to produce the section digests."""
    with tempfile.TemporaryDirectory() as td:
        data_path = os.path.join(td, "payload.json")
        with open(data_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, default=str))
        driver = os.path.join(td, "driver.cjs")
        with open(driver, "w", encoding="utf-8") as fh:
            fh.write(NODE_DRIVER % SHARED_JS)
        out = subprocess.run(
            ["node", driver, data_path],
            capture_output=True, text=True, check=True,
        )
        res = json.loads(out.stdout)
    assert res["selfcheck_abc"] == KNOWN_ABC, (
        "pure-JS SHA-256 failed the 'abc' NIST vector: %r" % res["selfcheck_abc"])
    assert res["selfcheck_empty"] == KNOWN_EMPTY, (
        "pure-JS SHA-256 failed the empty-string vector: %r" % res["selfcheck_empty"])
    return res


def _embed_token_swap(html: str, new_json: str) -> str:
    tok = "/*__UI_DATA__*/"
    i = html.find(tok)
    assert i != -1, "embed token not found"
    j = html.find("</script>", i)
    assert j != -1, "embed script close not found"
    assert "/*__UI_DATA__*/" not in new_json, "payload must not contain the embed token"
    return html[:i] + tok + new_json + html[j:]


def main(check_only: bool = False) -> int:
    with open(UI_DATA, encoding="utf-8") as fh:
        data = json.load(fh)

    assert data.get("contract_version") == PRIOR_CONTRACT, (
        "unexpected prior contract %r (expected %r)"
        % (data.get("contract_version"), PRIOR_CONTRACT))
    man = data.get("contract_manifest")
    assert isinstance(man, dict), "contract_manifest missing"
    assert "section_digests" not in man, "section_digests already present"

    # 1. bump contract version (affects the 'contract_version' section digest).
    data["contract_version"] = NEW_CONTRACT
    man["expected_contract_version"] = NEW_CONTRACT

    # 2. compute per-section digests via the EXACT embedded JS in Node.
    res = compute_digests_via_node(data)
    section_digests = res["section_digests"]
    root_digest = res["root_digest"]
    digested_keys = res["keys"]

    expected_top = sorted(k for k in data.keys() if k != "contract_manifest")
    assert digested_keys == expected_top, (
        "digest key set mismatch: %r vs %r" % (digested_keys, expected_top))
    assert len(section_digests) == len(expected_top)
    for k, hexd in section_digests.items():
        assert len(hexd) == 64 and all(c in "0123456789abcdef" for c in hexd), (
            "bad digest for %r: %r" % (k, hexd))
    assert len(root_digest) == 64

    if check_only:
        print(json.dumps({
            "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
            "sections_digested": len(section_digests),
            "root_digest": root_digest,
            "sha256_selfcheck": "abc+empty OK",
        }, indent=1))
        return 0

    # 3. write the digest fields INSIDE contract_manifest (no new top-level key).
    man["digest_algo"] = DIGEST_ALGO
    man["section_digests"] = section_digests
    man["root_digest"] = root_digest
    man["digest_scope"] = (
        "sha256 over canonical(JSON) of every top-level section except "
        "contract_manifest; root_digest = sha256 over canonical(section_digests)."
    )
    man["digest_generated_by"] = GENERATOR
    base_note = man.get("note", "")
    add_note = (" Per-section SHA-256 content digests added in 1.20.0 (gap A2): "
                "recomputed in-browser, tamper-evident.")
    if "1.20.0" not in base_note:
        man["note"] = (base_note + add_note).strip()

    new_json = json.dumps(data, default=str)
    json.loads(new_json)  # re-parse guard

    # 4. patch the HTML: embedded payload + shared JS + verifier render.
    with open(UI_APP, encoding="utf-8") as fh:
        html = fh.read()

    html = _embed_token_swap(html, new_json)

    # inject shared primitives + verifier render just before renderAll()
    RENDERALL_ANCHOR = "\n  function renderAll(){\n    renderHeader();"
    assert html.count(RENDERALL_ANCHOR) == 1, "renderAll anchor not unique/found"
    GEN_LABEL_JS = '  var GENERATOR_LABEL=%s;\n' % json.dumps(GENERATOR)
    inject = "\n" + SHARED_JS + GEN_LABEL_JS + VERIFIER_RENDER_JS + RENDERALL_ANCHOR
    html = html.replace(RENDERALL_ANCHOR, inject)

    # call the verifier render in renderIntegrity, after the a11y audit block
    INTEGRITY_ANCHOR = "    html += renderA11yAuditHtml();\n    el.innerHTML=html;"
    assert html.count(INTEGRITY_ANCHOR) == 1, "integrity render anchor not unique/found"
    html = html.replace(
        INTEGRITY_ANCHOR,
        "    html += renderA11yAuditHtml();\n"
        "    html += renderIntegrityVerifierHtml();\n"
        "    el.innerHTML=html;",
    )

    # --- write artifacts ---
    with open(UI_DATA, "w", encoding="utf-8") as fh:
        fh.write(new_json)
    with open(UI_APP, "w", encoding="utf-8") as fh:
        fh.write(html)

    # --- re-parse + integrity guards on disk ---
    with open(UI_DATA, encoding="utf-8") as fh:
        chk = json.load(fh)
    assert chk["contract_version"] == NEW_CONTRACT
    cman = chk["contract_manifest"]
    assert cman["root_digest"] == root_digest
    assert cman["digest_algo"] == DIGEST_ALGO
    assert len(cman["section_digests"]) == len(expected_top)

    h2 = open(UI_APP, encoding="utf-8").read()
    a = h2.find("/*__UI_DATA__*/") + len("/*__UI_DATA__*/")
    b = h2.find("</script>", a)
    emb = json.loads(h2[a:b])
    assert emb["contract_version"] == NEW_CONTRACT
    assert emb["contract_manifest"]["root_digest"] == root_digest
    assert "_ciSectionDigests" in h2 and "renderIntegrityVerifierHtml" in h2

    # confirm the embedded payload recomputes to the SAME digests via Node
    # (this is exactly what the browser will do).
    recheck = compute_digests_via_node(emb)
    assert recheck["root_digest"] == root_digest, "embedded recompute root mismatch"
    assert recheck["section_digests"] == section_digests, "embedded recompute mismatch"

    print(json.dumps({
        "verdict": "PASS",
        "contract": "%s -> %s" % (PRIOR_CONTRACT, NEW_CONTRACT),
        "sections_digested": len(section_digests),
        "root_digest": root_digest,
        "embedded_recompute_matches": True,
        "ui_data_bytes": len(new_json.encode("utf-8")),
        "ui_app_bytes": len(h2.encode("utf-8")),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check_only="--check" in sys.argv))
