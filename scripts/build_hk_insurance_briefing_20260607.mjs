import fs from "node:fs";
import path from "node:path";

const reportDate = "2026-06-07";
const generatedAt = "2026-06-07 09:00 HKT";
const accessTime = "2026-06-07 09:00 HKT";
const researchWindow = "2026-06-01 to 2026-06-07";
const outputDir = path.resolve("outputs");
const workbookPath = path.join(outputDir, `HK_Insurance_Daily_Briefing_${reportDate}.xlsx`);
const summaryPath = path.join(outputDir, `HK_Insurance_Daily_Briefing_${reportDate}_summary.json`);

const products = [
  {
    insurer: "Chubb Life Insurance Hong Kong Limited (\u5b89\u9054\u4eba\u58fd\u4fdd\u96aa)",
    productName: "Chubb MyLegacy Insurance Plan V - Harvest (\u5b89\u9054\u50b3\u627f\u5b88\u5275\u5132\u84c4\u4fdd\u96aa\u8a08\u5283V - Harvest)",
    category: "Savings",
    iaClass: "Class A",
    currency: "N/A - public release does not restate policy currencies",
    announcementDate: "2026-06-01",
    sourceUrl: "https://chubb.mediaroom.com/news-releases?item=126560",
    premiumTerms: "Harvest option: 3-pay / 5-pay; Blossom option referenced as 2-pay / 5-pay / 8-pay / 12-pay",
    premiumRange: "N/A in public release",
    issueAge: "N/A in public release",
    summary: "Chubb enhanced MyLegacy V with a new 3-year premium payment option under Harvest. The release positions the plan as a whole-life savings and legacy product with guaranteed cash value, non-guaranteed reversionary and terminal bonuses, and a 6-year guaranteed breakeven for the new 3-pay option.",
    updateType: "Product enhancement",
    recencyFlag: "Past 7 days",
    savings: {
      guaranteedCash: "Guaranteed cash value disclosed; new 3-pay Harvest option aims for full guaranteed breakeven by the 6th policy anniversary.",
      projectedReturn: "N/A - projected IRR not disclosed in release.",
      bonus: "Non-guaranteed reversionary bonus plus non-guaranteed terminal bonus.",
      flexibility: "Cash withdrawal, standby regular withdrawal, annuity option, successor owner / successor insured, policy continuation and charity beneficiary features disclosed.",
      policyLoan: "N/A in public release.",
      taxDeduction: "N/A",
      annuityCommencement: "Optional annuity conversion/withdrawal features disclosed; exact commencement rules not in release."
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "Manulife (International) Limited (\u5b8f\u5229\u4eba\u58fd\u4fdd\u96aa)",
    productName: "Genesis Centurion Insurance Plan (\u5b8f\u646f\u5bb6\u50b3\u627f\u4fdd\u96aa\u8a08\u5283)",
    category: "Savings",
    iaClass: "Class A",
    currency: "Multi-currency / seven currencies referenced in release",
    announcementDate: "2026-01-05; official customer offer active to 2026-06-30",
    sourceUrl: "https://www.manulife.com.hk/en/individual/about/newsroom/manulife-hong-kong-launches-genesis-centurion-insurance-plan-and-prestige-achiever-insurance-plan.html",
    premiumTerms: "N/A in launch release; check product illustration for selected payment term",
    premiumRange: "N/A in launch release",
    issueAge: "N/A in launch release",
    summary: "High-net-worth whole-life participating savings product designed for cross-generational wealth planning. Manulife disclosed a long-term projected surrender value path of about 4x total premiums by policy year 25, 6x by year 31 and 8x by year 35 under its assumptions.",
    updateType: "Current 2026 watchlist / active offer",
    recencyFlag: "Older 2026 launch / current offer",
    savings: {
      guaranteedCash: "Guaranteed cash value exists; launch release emphasizes projected long-term surrender value rather than guaranteed IRR.",
      projectedReturn: "Illustrative surrender value around 4x total premiums paid by year 25, 6x by year 31 and 8x by year 35; non-guaranteed components apply.",
      bonus: "Participating product with terminal bonus potential; Manulife release emphasizes long-term projected value.",
      flexibility: "Policy currency switching, policy split, change of life insured, contingent policyholder, estate distribution and Body and Mind Advance Benefit features disclosed.",
      policyLoan: "N/A in release.",
      taxDeduction: "N/A",
      annuityCommencement: "N/A"
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "Manulife (International) Limited (\u5b8f\u5229\u4eba\u58fd\u4fdd\u96aa)",
    productName: "Prestige Achiever Insurance Plan (\u8ca1\u646f\u5b8f\u8000\u4fdd\u96aa\u8a08\u5283)",
    category: "Savings",
    iaClass: "Class A",
    currency: "N/A in launch release",
    announcementDate: "2026-01-05; official customer offer active to 2026-06-30",
    sourceUrl: "https://www.manulife.com.hk/en/individual/about/newsroom/manulife-hong-kong-launches-genesis-centurion-insurance-plan-and-prestige-achiever-insurance-plan.html",
    premiumTerms: "N/A in launch release; current offer page should be checked for campaign terms",
    premiumRange: "N/A in launch release",
    issueAge: "N/A in launch release",
    summary: "Savings product aimed at affluent customers seeking earlier liquidity. Manulife disclosed guaranteed cash value up to 83% of total premiums paid from day one and a total IRR projected to reach 4.6% by policy year 10 under its assumptions.",
    updateType: "Current 2026 watchlist / active offer",
    recencyFlag: "Older 2026 launch / current offer",
    savings: {
      guaranteedCash: "Guaranteed cash value can reach up to 83% of total premiums paid from the first policy day according to Manulife release.",
      projectedReturn: "Total IRR projected to reach 4.6% by policy year 10 in release illustration.",
      bonus: "Participating savings plan; non-guaranteed component details should be verified against product brochure.",
      flexibility: "Marketed for liquidity and wealth management; detailed policy flexibility not fully disclosed in launch release.",
      policyLoan: "N/A in release.",
      taxDeduction: "N/A",
      annuityCommencement: "N/A"
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "Prudential Hong Kong Limited (\u4fdd\u8aa0\u4eba\u58fd\u4fdd\u96aa)",
    productName: "Selected Health Insurance Plans Q2 Promotion - PRUHealth VHIS / Medical",
    category: "VHIS",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "2026-04-01 to 2026-06-30 promotion period",
    sourceUrl: "https://www.prudential.com.hk/content/dam/prudential-phkl/pdf/en/promotion/medical-CI-promotion.pdf.coredownload.inline.pdf",
    premiumTerms: "Regular pay; campaign terms vary by eligible plan",
    premiumRange: "N/A - campaign describes premium refund percentages, not base premium grid",
    issueAge: "N/A in promotion PDF",
    summary: "Prudential's active Q2 campaign covers selected health insurance plans, including PRUHealth VHIS VIP, PRUHealth CoreChoice, PRUHealth VHIS EasyChoice and PRUHealth FlexiChoice. The promotion offers basic premium refund incentives subject to plan and campaign terms.",
    updateType: "Active promotion / product watchlist",
    recencyFlag: "Current offer",
    savings: {},
    medical: {
      planType: "VHIS Flexi / medical plans in eligible campaign set.",
      roomClass: "N/A in promotion PDF.",
      annualLimit: "N/A in promotion PDF; check individual product brochure.",
      lifetimeLimit: "N/A in promotion PDF.",
      claimItems: "Health insurance plans; claimable items vary by selected plan.",
      copay: "N/A in promotion PDF.",
      preExisting: "Subject to plan terms and VHIS requirements where applicable.",
      cancerCoverage: "N/A in promotion PDF; plan-specific."
    },
    ci: {}
  },
  {
    insurer: "BOC Life Insurance Company Limited (\u4e2d\u9280\u4eba\u58fd\u4fdd\u96aa)",
    productName: "BOC Life Deferred Annuity Plan (Fixed Term) (\u4e2d\u9280\u4eba\u58fd\u5ef6\u671f\u5e74\u91d1\u8a08\u5283 - \u56fa\u5b9a\u5e74\u671f)",
    category: "QDAP",
    iaClass: "Class A",
    currency: "HKD / RMB / USD",
    announcementDate: "2026-06-30 offer deadline; product page checked 2026-06-07",
    sourceUrl: "https://www.boclife.com.hk/tc/promotion.html",
    premiumTerms: "5-year premium payment; annuity income period 10 years after deferred period",
    premiumRange: "Indicative monthly premium from HKD 3,500; minimum total premium HKD 180,000 shown in public material",
    issueAge: "N/A in promotion page; underlying product materials should be checked by policy term",
    summary: "BOC Life's active mobile-application offer applies to its fixed-term qualifying deferred annuity product. Public materials position it as a 5-pay QDAP with annualized guaranteed IRR references and a 10-year annuity payout period.",
    updateType: "Active QDAP promotion",
    recencyFlag: "Current offer",
    savings: {
      guaranteedCash: "Public product material references annualized guaranteed IRR of about 1.73% to 3.30% depending policy term/currency.",
      projectedReturn: "N/A - non-guaranteed return not highlighted in promotion.",
      bonus: "N/A - fixed-term QDAP annuity structure.",
      flexibility: "Deferred annuity period and annuity payout term vary by selected plan option; mobile application promotion available.",
      policyLoan: "N/A in promotion page.",
      taxDeduction: "Qualifying deferred annuity premiums may count toward the HKD 60,000 annual tax deduction cap shared with tax-deductible voluntary MPF contributions, subject to Hong Kong tax rules.",
      annuityCommencement: "After deferred period; product literature references 10-year annuity income period."
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "Sun Life Hong Kong Limited (\u6c38\u660e\u91d1\u878d)",
    productName: "Critical Medical Care Insurance Plan II",
    category: "Critical Illness",
    iaClass: "Class D",
    currency: "HKD / USD",
    announcementDate: "Product page / official offer checked 2026-06-07",
    sourceUrl: "https://www.sunlife.com.hk/en/insurance/health/critical-illness/critical-medical-care-insurance-plan-ii/",
    premiumTerms: "N/A in public page excerpt",
    premiumRange: "N/A in public page excerpt",
    issueAge: "N/A in public page excerpt",
    summary: "Critical illness plan with a combined CI and medical-cost positioning. Sun Life states coverage for 51 critical illnesses, optional Multi-pay Benefit for repeat CI and cancer claims, and optional Major Medical Benefit for designated overseas or local medical expense support.",
    updateType: "Current product watchlist / official offer",
    recencyFlag: "Current offer",
    savings: {},
    medical: {},
    ci: {
      conditions: "51 critical illnesses disclosed on official product page.",
      severity: "Major CI structure with optional early/extra medical support features; detailed tiering requires brochure check.",
      multipay: "Optional Multi-pay Benefit covers up to 5 critical illness claims and up to 3 cancer claims per insured life, subject to terms.",
      sumRange: "N/A in public page excerpt.",
      waiver: "N/A in public page excerpt.",
      cancerDefinition: "Optional Multi-pay Benefit includes repeated cancer claim structure; definitions subject to brochure.",
      mentalDiabetes: "N/A in public page excerpt."
    }
  },
  {
    insurer: "AIA International Limited (\u53cb\u90a6\u4fdd\u96aa)",
    productName: "AIA Voluntary Health Insurance SelectWise Scheme",
    category: "VHIS",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "2026-02-03; official product still current",
    sourceUrl: "https://www.aia.com.hk/en/about-aia/about-us/media-centre/press-releases/2026/aia-press-release-20260203",
    premiumTerms: "Regular pay",
    premiumRange: "N/A in press release",
    issueAge: "N/A in press release",
    summary: "VHIS-certified Flexi plan with no itemized benefit sublimits, annual benefit limit up to HKD 12 million, lifetime limit up to HKD 60 million, designated-hospital network mechanics and Care Concierge support.",
    updateType: "Latest 2026 VHIS launch watchlist",
    recencyFlag: "Older 2026 launch",
    savings: {},
    medical: {
      planType: "VHIS Flexi certified plan.",
      roomClass: "Basic ward across Asia; semi-private / Mainland room options subject to designated hospital and pre-authorization rules.",
      annualLimit: "Up to HKD 12 million.",
      lifetimeLimit: "Up to HKD 60 million.",
      claimItems: "Hospitalization, surgical, pre/post-confinement, day-case outpatient, Chinese medicine outpatient, day-surgery cash benefits and Care Concierge services.",
      copay: "Annual deductible options; designated cancer deductible waiver for elderly insureds disclosed in release.",
      preExisting: "Subject to VHIS policy terms.",
      cancerCoverage: "Designated cancer deductible waiver for eligible age 75+ insureds subject to rules."
    },
    ci: {}
  }
];

const sourceLog = [
  ["Search query", "Hong Kong life insurance new product launch 2026", accessTime, "Yes", "Specified English query; one strict-window Chubb top-10 enhancement and several older/current 2026 product items found."],
  ["Search query", "AIA Manulife Prudential FWD Sun Life HSBC BOC Life new product Hong Kong 2026", accessTime, "Yes", "Specified English query; found AIA, Manulife and other official 2026 product pages/releases."],
  ["Search query", "QDAP Hong Kong new 2026", accessTime, "Limited", "Specified English query; no strict-window top-10 QDAP launch found; BOC Life active QDAP promotion logged as context."],
  ["Search query", "VHIS new plan Hong Kong 2026", accessTime, "Yes", "Specified English query; AIA SelectWise and Prudential/FWD current VHIS materials found."],
  ["Search query", "critical illness insurance Hong Kong new launch 2026", accessTime, "Yes", "Specified English query; Sun Life and other CI product pages found, but no strict-window top-10 launch."],
  ["Search query", "savings insurance Hong Kong new 2026", accessTime, "Yes", "Specified English query; Chubb and Manulife savings products found."],
  ["Search query", "site:aia.com.hk OR site:manulife.com.hk OR site:prudential.com.hk new product 2026", accessTime, "Yes", "Specified English query; official AIA/Manulife/Prudential sources checked."],
  ["Search query", "\u9999\u6e2f\u4eba\u58fd\u4fdd\u96aa \u65b0\u7522\u54c1 2026", accessTime, "Yes", "Specified Traditional Chinese query; market quiet in the strict 7-day window."],
  ["Search query", "\u5132\u84c4\u4fdd\u96aa \u65b0\u63a8\u51fa \u9999\u6e2f 2026", accessTime, "Yes", "Specified Traditional Chinese query; Chubb and Manulife savings watchlist items checked."],
  ["Search query", "\u5371\u75be\u4fdd\u96aa \u65b0\u8a08\u5283 \u9999\u6e2f 2026", accessTime, "Yes", "Specified Traditional Chinese query; no strict-window top-10 CI launch found."],
  ["Search query", "QDAP \u5408\u8cc7\u683c\u5ef6\u671f\u5e74\u91d1 \u65b0\u8a08\u5283 2026", accessTime, "Limited", "Specified Traditional Chinese query; no strict-window new target-insurer QDAP found."],
  ["Search query", "VHIS \u81ea\u9858\u91ab\u4fdd \u65b0\u8a08\u5283 2026", accessTime, "Yes", "Specified Traditional Chinese query; AIA SelectWise and official VHIS materials checked."],
  ["Search query", "\u53cb\u90a6 \u5b8f\u5229 \u4fdd\u8aa0 \u5bcc\u885b \u6c38\u660e \u6ed9\u8c50 \u65b0\u7522\u54c1 2026", accessTime, "Yes", "Specified Traditional Chinese query; no additional strict-window top-10 launch identified."],
  ["Official source", "https://chubb.mediaroom.com/news-releases?item=126560", accessTime, "Yes", "Chubb official 2026-06-01 MyLegacy V product enhancement."],
  ["Official source", "https://www.manulife.com.hk/en/individual/about/newsroom/manulife-hong-kong-launches-genesis-centurion-insurance-plan-and-prestige-achiever-insurance-plan.html", accessTime, "Yes", "Manulife 2026 savings launches used as current watchlist items."],
  ["Official source", "https://www.manulife.com.hk/en/individual/products/latest-customer-offers.html", accessTime, "Yes", "Manulife customer offers checked for June 2026 active campaign context."],
  ["Official source", "https://www.prudential.com.hk/content/dam/prudential-phkl/pdf/en/promotion/medical-CI-promotion.pdf.coredownload.inline.pdf", accessTime, "Yes", "Prudential active medical/CI promotion PDF checked."],
  ["Official source", "https://www.boclife.com.hk/tc/promotion.html", accessTime, "Yes", "BOC Life active mobile-application insurance promotion checked."],
  ["Official source", "https://www.sunlife.com.hk/en/insurance/health/critical-illness/critical-medical-care-insurance-plan-ii/", accessTime, "Yes", "Sun Life official Critical Medical Care II page checked."],
  ["Official source", "https://www.aia.com.hk/en/about-aia/about-us/media-centre/press-releases/2026/aia-press-release-20260203", accessTime, "Yes", "AIA SelectWise VHIS launch release retained as watchlist context."],
  ["Regulatory source", "https://www.ia.org.hk/en/qualifying_deferred_annuity_policy/qdap_all.html", accessTime, "Yes", "IA QDAP list checked; no new strict-window top-10 launch identified."],
  ["Regulatory source", "https://www.vhis.gov.hk/en/consumer_corner/faqs.html", accessTime, "Yes", "VHIS public market statistics and certified-plan context checked."],
  ["Regulatory source", "https://www.ia.org.hk/en/legislative_framework/circulars/reg_matters/circulars_on_regulatory_matters_2026.html", accessTime, "Yes", "IA 2026 circular page checked; no immediate product-pricing circular found in strict window."],
  ["Regulatory source", "https://www.mpfa.org.hk/en/info-centre/laws-and-regulations/guidelines", accessTime, "Yes", "MPFA guidelines checked for annuity-adjacent updates; no direct life product update found."],
  ["Industry source", "https://www.hkfi.org.hk/news/", accessTime, "Yes", "HKFI news checked for product-standard and Q Mark context; no strict-window top-10 launch found."]
];

const allHeaders = [
  "Insurer",
  "Product Name",
  "Product Category",
  "IA Class",
  "Currency",
  "Issue Date / Announcement Date",
  "Source URL",
  "Premium Payment Terms",
  "Premium Range",
  "Issue Age",
  "Key Benefit Summary",
  "Update Type",
  "Recency Flag"
];

const savingsHeaders = [
  ...allHeaders,
  "Guaranteed Cash Value / IRR",
  "Non-Guaranteed Projected Return",
  "Bonus / Dividend Structure",
  "Premium Holiday / Flexibility",
  "Policy Loan",
  "QDAP Tax Deduction",
  "Annuity Commencement"
];

const medicalHeaders = [
  ...allHeaders,
  "Plan Type",
  "Room Class",
  "Annual Benefit Limit",
  "Lifetime Benefit Limit",
  "Key Claimable Items",
  "Co-payment / Deductible",
  "Pre-existing Condition",
  "Cancer Coverage"
];

const ciHeaders = [
  ...allHeaders,
  "Number of Covered Conditions",
  "Severity Structure",
  "Multi-pay Structure",
  "Sum Assured Range",
  "Premium Waiver",
  "Cancer Definition",
  "Mental Health / Diabetes Coverage"
];

function hlink(url, label = "Open source") {
  return { f: `HYPERLINK("${url.replaceAll('"', '""')}","${label}")`, v: label, style: 5 };
}

function baseProductRow(p) {
  return [
    p.insurer,
    p.productName,
    p.category,
    { v: p.iaClass, style: 6 },
    p.currency,
    p.announcementDate,
    hlink(p.sourceUrl),
    p.premiumTerms,
    p.premiumRange,
    p.issueAge,
    p.summary,
    p.updateType,
    p.recencyFlag
  ];
}

const allRows = [allHeaders, ...products.map(baseProductRow)];
const savingsRows = [
  savingsHeaders,
  ...products.filter(p => p.category === "Savings" || p.category === "QDAP").map(p => [
    ...baseProductRow(p),
    p.savings.guaranteedCash ?? "N/A",
    p.savings.projectedReturn ?? "N/A",
    p.savings.bonus ?? "N/A",
    p.savings.flexibility ?? "N/A",
    p.savings.policyLoan ?? "N/A",
    p.savings.taxDeduction ?? "N/A",
    p.savings.annuityCommencement ?? "N/A"
  ])
];
const medicalRows = [
  medicalHeaders,
  ...products.filter(p => p.category === "Medical" || p.category === "VHIS").map(p => [
    ...baseProductRow(p),
    p.medical.planType ?? "N/A",
    p.medical.roomClass ?? "N/A",
    p.medical.annualLimit ?? "N/A",
    p.medical.lifetimeLimit ?? "N/A",
    p.medical.claimItems ?? "N/A",
    p.medical.copay ?? "N/A",
    p.medical.preExisting ?? "N/A",
    p.medical.cancerCoverage ?? "N/A"
  ])
];
const ciRows = [
  ciHeaders,
  ...products.filter(p => p.category === "Critical Illness").map(p => [
    ...baseProductRow(p),
    p.ci.conditions ?? "N/A",
    p.ci.severity ?? "N/A",
    p.ci.multipay ?? "N/A",
    p.ci.sumRange ?? "N/A",
    p.ci.waiver ?? "N/A",
    p.ci.cancerDefinition ?? "N/A",
    p.ci.mentalDiabetes ?? "N/A"
  ])
];

const countBy = (field) => products.reduce((acc, p) => {
  acc[p[field]] = (acc[p[field]] || 0) + 1;
  return acc;
}, {});
const byCategory = countBy("category");
const byInsurer = products.reduce((acc, p) => {
  const name = p.insurer.split(" (")[0];
  acc[name] = (acc[name] || 0) + 1;
  return acc;
}, {});

const strictWindowItems = products.filter(p => p.recencyFlag === "Past 7 days");
const inWindowCount = strictWindowItems.length;
const newLaunch48h = 0;
const productUpdateCount = products.filter(p => /update|promotion|offer|watchlist/i.test(p.updateType)).length;
const allLastRow = products.length + 1;

const summaryRows = [
  ["HK Life Insurance Daily Product Briefing", "", "", "", "", ""],
  ["Report Date", reportDate, "Generated", generatedAt, "Research Window", researchWindow],
  ["Total tracked product/product-related entries", { f: `COUNTA('All Products'!A2:A${allLastRow})`, v: products.length }, "Strict-window top-10 items", inWindowCount, "New launches past 48h", newLaunch48h],
  ["Product updates / active offers tracked", productUpdateCount, "Source credibility", "Official insurer/regulatory sources prioritized; press/news used only for discovery context", "", ""],
  ["Market note", "Quiet strict-window result: one official top-10 Class A/C/D product enhancement found in the past 7 days and no new top-10 launch in the past 48 hours. Current 2026 product/offers are included as watchlist context.", "", "", "", ""],
  ["", "", "", "", "", ""],
  ["Count by Category", "", "", "Count by Insurer", "", ""],
  ["Savings", { f: `COUNTIF('All Products'!C2:C${allLastRow},"Savings")`, v: byCategory.Savings || 0 }, "", "AIA International Limited", byInsurer["AIA International Limited"] || 0, ""],
  ["QDAP", { f: `COUNTIF('All Products'!C2:C${allLastRow},"QDAP")`, v: byCategory.QDAP || 0 }, "", "BOC Life Insurance Company Limited", byInsurer["BOC Life Insurance Company Limited"] || 0, ""],
  ["VHIS", { f: `COUNTIF('All Products'!C2:C${allLastRow},"VHIS")`, v: byCategory.VHIS || 0 }, "", "Chubb Life Insurance Hong Kong Limited", byInsurer["Chubb Life Insurance Hong Kong Limited"] || 0, ""],
  ["Medical", { f: `COUNTIF('All Products'!C2:C${allLastRow},"Medical")`, v: byCategory.Medical || 0 }, "", "Manulife (International) Limited", byInsurer["Manulife (International) Limited"] || 0, ""],
  ["Critical Illness", { f: `COUNTIF('All Products'!C2:C${allLastRow},"Critical Illness")`, v: byCategory["Critical Illness"] || 0 }, "", "Prudential Hong Kong Limited", byInsurer["Prudential Hong Kong Limited"] || 0, ""],
  ["", "", "", "Sun Life Hong Kong Limited", byInsurer["Sun Life Hong Kong Limited"] || 0, ""],
  ["", "", "", "", "", ""],
  ["Regulatory Intelligence", "", "", "", "", ""],
  ["QDAP", "IA QDAP list checked; no strict-window new target-insurer QDAP launch identified. BOC Life active QDAP promotion retained as pricing-watch context.", "", "", "", ""],
  ["VHIS", "VHIS official materials checked; no strict-window certified-plan addition by a target insurer found in this run.", "", "", "", ""],
  ["HKFI / IA / MPFA", "HKFI news, IA circulars and MPFA guidelines checked; no immediate pricing-product regulatory filing found for the strict 7-day window.", "", "", "", ""]
];

const sourceRows = [["Source Type", "Query / URL", "Date-Time Accessed", "Content Found", "Notes"], ...sourceLog];

const sheets = [
  { name: "Summary Dashboard", rows: summaryRows, validations: [] },
  { name: "All Products", rows: allRows, validations: [
    { sqref: `C2:C${products.length + 1}`, formula: '"Savings,QDAP,VHIS,Medical,Critical Illness"' },
    { sqref: `D2:D${products.length + 1}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "Savings & QDAP", rows: savingsRows, validations: [
    { sqref: `C2:C${Math.max(2, savingsRows.length)}`, formula: '"Savings,QDAP"' },
    { sqref: `D2:D${Math.max(2, savingsRows.length)}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "VHIS & Medical", rows: medicalRows, validations: [
    { sqref: `C2:C${Math.max(2, medicalRows.length)}`, formula: '"VHIS,Medical"' },
    { sqref: `D2:D${Math.max(2, medicalRows.length)}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "Critical Illness", rows: ciRows, validations: [
    { sqref: `C2:C${Math.max(2, ciRows.length)}`, formula: '"Critical Illness"' },
    { sqref: `D2:D${Math.max(2, ciRows.length)}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "Sources Log", rows: sourceRows, validations: [] }
];

function xmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function colName(index) {
  let n = index + 1;
  let s = "";
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function styleForCell(sheetName, rowIndex, colIndex, raw) {
  if (raw && typeof raw === "object" && !Array.isArray(raw) && raw.style != null) return raw.style;
  if (rowIndex === 0) return sheetName === "Summary Dashboard" ? 7 : 1;
  if (sheetName === "All Products" && colIndex === 5) {
    const p = products[rowIndex - 1];
    if (p?.recencyFlag === "Past 7 days") return 4;
  }
  if (rowIndex % 2 === 0) return 2;
  return 3;
}

function cellXml(sheetName, rowIndex, colIndex, raw) {
  const ref = `${colName(colIndex)}${rowIndex + 1}`;
  const cell = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : { v: raw };
  const style = styleForCell(sheetName, rowIndex, colIndex, raw);
  if (cell.f) {
    const cached = cell.v ?? "";
    const t = typeof cached === "string" ? ' t="str"' : "";
    return `<c r="${ref}" s="${style}"${t}><f>${xmlEscape(cell.f)}</f><v>${xmlEscape(cached)}</v></c>`;
  }
  if (cell.v === null || cell.v === undefined || cell.v === "") return `<c r="${ref}" s="${style}"/>`;
  if (typeof cell.v === "number") return `<c r="${ref}" s="${style}"><v>${cell.v}</v></c>`;
  return `<c r="${ref}" s="${style}" t="inlineStr"><is><t>${xmlEscape(cell.v)}</t></is></c>`;
}

function columnWidths(rows) {
  const maxCols = Math.max(...rows.map(r => r.length));
  const widths = [];
  for (let c = 0; c < maxCols; c++) {
    let max = 8;
    for (const row of rows) {
      const raw = row[c];
      const v = raw && typeof raw === "object" && !Array.isArray(raw) ? raw.v : raw;
      max = Math.max(max, String(v ?? "").length);
    }
    const cap = c === 10 ? 75 : c === 1 ? 58 : 48;
    widths.push(Math.min(Math.max(Math.ceil(max * 0.9), 10), cap));
  }
  return widths;
}

function sheetXml(sheet) {
  const rows = sheet.rows.length ? sheet.rows : [[""]];
  const cols = columnWidths(rows).map((width, i) => `<col min="${i + 1}" max="${i + 1}" width="${width}" customWidth="1"/>`).join("");
  const rowXml = rows.map((row, r) => {
    const cells = row.map((cell, c) => cellXml(sheet.name, r, c, cell)).join("");
    const textLen = row.map(cell => typeof cell === "object" && cell !== null ? cell.v ?? "" : cell).join(" ").length;
    const height = r === 0 ? 24 : (textLen > 180 ? 62 : 30);
    return `<row r="${r + 1}" ht="${height}" customHeight="1">${cells}</row>`;
  }).join("");
  const lastCol = colName(Math.max(...rows.map(r => r.length)) - 1);
  const lastRow = rows.length;
  const autoFilter = sheet.name !== "Summary Dashboard" ? `<autoFilter ref="A1:${lastCol}${lastRow}"/>` : "";
  const validations = sheet.validations?.length
    ? `<dataValidations count="${sheet.validations.length}">${sheet.validations.map(v => `<dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="${v.sqref}"><formula1>${xmlEscape(v.formula)}</formula1></dataValidation>`).join("")}</dataValidations>`
    : "";
  const merge = sheet.name === "Summary Dashboard" ? `<mergeCells count="1"><mergeCell ref="A1:F1"/></mergeCells>` : "";
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft"/></sheetView></sheetViews>
<sheetFormatPr baseColWidth="10" defaultRowHeight="15"/>
<cols>${cols}</cols>
<sheetData>${rowXml}</sheetData>
${autoFilter}
${validations}
${merge}
<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>`;
}

function contentTypesXml() {
  const sheetOverrides = sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
${sheetOverrides}
</Types>`;
}

function workbookXml() {
  const sheetEntries = sheets.map((s, i) => `<sheet name="${xmlEscape(s.name)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<workbookPr date1904="false"/>
<calcPr calcId="191029" calcMode="auto"/>
<sheets>${sheetEntries}</sheets>
</workbook>`;
}

function workbookRelsXml() {
  const sheetRels = sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
${sheetRels}
<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`;
}

function rootRelsXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`;
}

function stylesXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="5">
<font><sz val="10"/><name val="Arial"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
<font><u/><sz val="10"/><color rgb="FF0000FF"/><name val="Arial"/></font>
<font><sz val="10"/><color rgb="FF0000FF"/><name val="Arial"/></font>
<font><b/><sz val="12"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>
</fonts>
<fills count="6">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F3864"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFD6E4F0"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFFF00"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEAF2F8"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFB7C9DA"/></left><right style="thin"><color rgb="FFB7C9DA"/></right><top style="thin"><color rgb="FFB7C9DA"/></top><bottom style="thin"><color rgb="FFB7C9DA"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="8">
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="1" xfId="0" applyFont="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="4" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;
}

function appXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>Codex</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop><HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>${sheets.length}</vt:i4></vt:variant></vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="${sheets.length}" baseType="lpstr">${sheets.map(s => `<vt:lpstr>${xmlEscape(s.name)}</vt:lpstr>`).join("")}</vt:vector></TitlesOfParts><Company></Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0300</AppVersion></Properties>`;
}

function coreXml() {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:creator>Codex</dc:creator><cp:lastModifiedBy>Codex</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-06-07T01:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-06-07T01:00:00Z</dcterms:modified><dc:title>HK Insurance Daily Briefing ${reportDate}</dc:title></cp:coreProperties>`;
}

const crcTable = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
  crcTable[n] = c >>> 0;
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (const b of buf) crc = crcTable[(crc ^ b) & 0xFF] ^ (crc >>> 8);
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function dosDateTime(date = new Date("2026-06-07T01:00:00Z")) {
  const time = ((date.getUTCHours() & 0x1F) << 11) | ((date.getUTCMinutes() & 0x3F) << 5) | ((Math.floor(date.getUTCSeconds() / 2)) & 0x1F);
  const d = (((date.getUTCFullYear() - 1980) & 0x7F) << 9) | (((date.getUTCMonth() + 1) & 0xF) << 5) | (date.getUTCDate() & 0x1F);
  return { time, date: d };
}

function u16(n) {
  const b = Buffer.alloc(2);
  b.writeUInt16LE(n);
  return b;
}

function u32(n) {
  const b = Buffer.alloc(4);
  b.writeUInt32LE(n >>> 0);
  return b;
}

function createZip(files) {
  const chunks = [];
  const central = [];
  let offset = 0;
  const dt = dosDateTime();
  for (const file of files) {
    const nameBuf = Buffer.from(file.name, "utf8");
    const data = Buffer.from(file.data, "utf8");
    const crc = crc32(data);
    const local = Buffer.concat([
      u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(dt.time), u16(dt.date),
      u32(crc), u32(data.length), u32(data.length), u16(nameBuf.length), u16(0), nameBuf, data
    ]);
    chunks.push(local);
    central.push(Buffer.concat([
      u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(dt.time), u16(dt.date),
      u32(crc), u32(data.length), u32(data.length), u16(nameBuf.length), u16(0), u16(0),
      u16(0), u16(0), u32(0), u32(offset), nameBuf
    ]));
    offset += local.length;
  }
  const centralDir = Buffer.concat(central);
  const end = Buffer.concat([
    u32(0x06054b50), u16(0), u16(0), u16(files.length), u16(files.length),
    u32(centralDir.length), u32(offset), u16(0)
  ]);
  return Buffer.concat([...chunks, centralDir, end]);
}

function buildEmailHtml() {
  const categoryCounts = ["Savings", "QDAP", "VHIS", "Medical", "Critical Illness"]
    .map(c => `${c}(${byCategory[c] || 0})`).join(" | ");
  const launchHtml = strictWindowItems.length
    ? strictWindowItems.map(p => `<p><b style="color:#1f4e79;">${xmlEscape(p.insurer.split(" (")[0])}</b> - ${xmlEscape(p.productName)} (${xmlEscape(p.category)})<br><b>Key features:</b></p><ul><li>${xmlEscape(p.summary)}</li><li>${xmlEscape(p.savings?.guaranteedCash || p.medical?.claimItems || p.ci?.conditions || "See tracker for details.")}</li></ul><p>Source: <a href="${xmlEscape(p.sourceUrl)}">${xmlEscape(p.sourceUrl)}</a></p>`).join("")
    : "<p>No official top-10 product launch or update was found in the strict past-7-day window.</p>";
  const recentHtml = products.filter(p => p.recencyFlag !== "Past 7 days").map(p =>
    `<li><b>${xmlEscape(p.insurer.split(" (")[0])}</b> - ${xmlEscape(p.productName)}: ${xmlEscape(p.updateType)}. <a href="${xmlEscape(p.sourceUrl)}">Source</a></li>`
  ).join("");

  return `<!doctype html><html><body style="font-family:Arial,sans-serif;font-size:14px;color:#1f1f1f;">
<h2>HK Life Insurance Daily Product Briefing</h2>
<p><b>Date:</b> ${reportDate} | <b>Generated at:</b> ${generatedAt}</p>
<h3>EXECUTIVE SUMMARY</h3>
<ul>
<li>Total products/product-related entries included: ${products.length}</li>
<li>New launches (past 48 hrs): ${newLaunch48h}</li>
<li>Official top-10 product updates in past 7 days: ${inWindowCount}</li>
<li>Product updates / active offers tracked: ${productUpdateCount}</li>
<li>Categories covered: ${categoryCounts}</li>
</ul>
<p><b>Market note:</b> The strict ${researchWindow} window was quiet. I found one official top-10 product enhancement, Chubb MyLegacy V on 2026-06-01, and no official top-10 launch in the past 48 hours. Older/current 2026 products and offers are included only as pricing-watch context.</p>
<h3>HIGHLIGHTS - NEW LAUNCHES</h3>
${launchHtml}
<h3>RECENT UPDATES (Past 7 Days)</h3>
${strictWindowItems.length ? "<ul>" + strictWindowItems.map(p => `<li><b>${xmlEscape(p.insurer.split(" (")[0])}</b> - ${xmlEscape(p.productName)}: ${xmlEscape(p.updateType)}. <a href="${xmlEscape(p.sourceUrl)}">Source</a></li>`).join("") + "</ul>" : "<p>No additional official top-10 updates found.</p>"}
<h3>CURRENT WATCHLIST</h3>
<ul>${recentHtml}</ul>
<h3>MARKET INTELLIGENCE</h3>
<ul>
<li>IA QDAP list checked; no strict-window new target-insurer QDAP launch identified.</li>
<li>VHIS official materials checked; no strict-window certified-plan addition by a target insurer identified.</li>
<li>IA circulars, HKFI news and MPFA guidelines checked; no immediate Class A/C/D pricing-product regulatory filing found for the strict window.</li>
</ul>
<h3>NOTES</h3>
<ul>
<li>Data sourced from public insurer websites, IA, VHIS, HKFI, MPFA and selected financial press for discovery context.</li>
<li>Covers Class A, C and D product categories requested; IA class labels are inferred from public product category where not explicit.</li>
<li>Full Excel tracker is attached and saved in the local outputs folder.</li>
<li>This is an automated research digest - verify details against official product documents before pricing work.</li>
</ul>
</body></html>`;
}

const files = [
  { name: "[Content_Types].xml", data: contentTypesXml() },
  { name: "_rels/.rels", data: rootRelsXml() },
  { name: "xl/workbook.xml", data: workbookXml() },
  { name: "xl/_rels/workbook.xml.rels", data: workbookRelsXml() },
  { name: "xl/styles.xml", data: stylesXml() },
  { name: "docProps/app.xml", data: appXml() },
  { name: "docProps/core.xml", data: coreXml() },
  ...sheets.map((sheet, i) => ({ name: `xl/worksheets/sheet${i + 1}.xml`, data: sheetXml(sheet) }))
];

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(workbookPath, createZip(files));

const allXml = files.map(f => f.data).join("\n");
const formulaErrors = ["#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A"].filter(term => allXml.includes(term));
const validation = {
  reportDate,
  workbookPath,
  productCount: products.length,
  inWindowCount,
  newLaunch48h,
  productUpdateCount,
  formulaErrors,
  generatedAt,
  requestedOutputPath: "/sessions/relaxed-kind-volta/mnt/outputs/HK_Insurance_Daily_Briefing_2026-06-07.xlsx",
  actualOutputPath: workbookPath,
  emailSubject: `[HK Insurance Daily] Product Briefing - ${reportDate} | ${inWindowCount} new/updated product`,
  emailHtml: buildEmailHtml()
};
fs.writeFileSync(summaryPath, JSON.stringify(validation, null, 2), "utf8");
console.log(JSON.stringify(validation, null, 2));
