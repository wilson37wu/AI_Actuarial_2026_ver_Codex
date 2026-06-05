import fs from "node:fs";
import path from "node:path";

const reportDate = "2026-05-31";
const generatedAt = "2026-05-31 08:00 HKT";
const accessTime = "2026-05-31 08:00 HKT";
const outputDir = path.resolve("outputs");
const workbookPath = path.join(outputDir, `HK_Insurance_Daily_Briefing_${reportDate}.xlsx`);
const summaryPath = path.join(outputDir, `HK_Insurance_Daily_Briefing_${reportDate}_summary.json`);

const products = [
  {
    insurer: "China Life Insurance (Overseas) Company Limited (中國人壽保險（海外）)",
    productName: "Oncology direct-billing service expansion with New Frontier Health (腫瘤專科門診直付理賠服務)",
    category: "Medical",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "2026-05-26",
    sourceUrl: "https://www.chinalife.com.hk/zh-hk/about-us/news-center/china-life-overseas-and-new-frontier-health-hong-kong-forge-strategic",
    premiumTerms: "N/A - service/network enhancement for eligible personal medical insurance customers",
    premiumRange: "N/A",
    issueAge: "N/A",
    summary: "Strategic partnership extends China Life (Overseas)' medical direct-billing network from inpatient services into specialist oncology outpatient services, day treatment, drugs and imaging diagnosis via Hong Kong Integrated Oncology Centre and Icon Cancer Centre.",
    updateType: "Product-related service update",
    recentFlag: "Past 7 days",
    savings: {},
    medical: {
      planType: "Medical service/network enhancement for eligible personal medical insurance customers",
      roomClass: "N/A",
      annualLimit: "N/A",
      lifetimeLimit: "N/A",
      claimItems: "Oncology specialist outpatient, day treatment, drugs, imaging diagnosis and one-stop direct settlement support after pre-approval.",
      copay: "N/A",
      preExisting: "Subject to underlying medical policy terms; not disclosed in release.",
      cancerCoverage: "Cancer treatment pathway support through oncology centres and direct billing."
    },
    ci: {}
  },
  {
    insurer: "FWD Life Insurance Company (Bermuda) Limited (富衛人壽保險)",
    productName: "MyCover Critical Illness Plan",
    category: "Critical Illness",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "N/A - active official online promotion as of 2026-05-31; offer ends 2026-06-10",
    sourceUrl: "https://www.fwd.com.hk/online-insurance/term-critical-illness/en/",
    premiumTerms: "Yearly renewable / 10-year renewable; premium payment to policy anniversary immediately preceding age 85",
    premiumRange: "Monthly premium shown as low as HK$14.31; sum insured HK$300,000-HK$2,500,000 depending on age",
    issueAge: "Age next birthday 1 (15 days) to 70",
    summary: "Online term CI plan covering the big three diseases, carcinoma-in-situ and early malignancies; optional Crisis Benefit adds 59 additional critical illnesses, and MyCover 2-in-1 adds post-claim medical reimbursement for the big three diseases.",
    updateType: "Current promotion / product page update",
    recentFlag: "Current offer",
    savings: {},
    medical: {},
    ci: {
      conditions: "Big 3 diseases; carcinoma-in-situ / early-stage malignancies; optional additional 59 critical illnesses",
      severity: "Multi-tier: early carcinoma-in-situ / early malignancy plus major CI lump sum",
      multipay: "Single major CI structure; MyCover 2-in-1 adds two-year medical reimbursement after big-three claim",
      sumRange: "HK$300,000-HK$2,500,000 for ANB 1-60; HK$300,000-HK$1,500,000 for ANB 61-70",
      waiver: "N/A in public page",
      cancerDefinition: "Covers carcinoma-in-situ of specified organs and early-stage malignancy of prostate, thyroid and non-melanoma skin cancer; pays 35% of initial sum insured up to HK$400,000.",
      mentalDiabetes: "N/A in public page"
    }
  },
  {
    insurer: "FWD Life Insurance Company (Bermuda) Limited (富衛人壽保險)",
    productName: "vPrime Medical Plan (VHIS Flexi Plan)",
    category: "VHIS",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "N/A - active official online promotion as of 2026-05-31; offer ends 2026-06-10",
    sourceUrl: "https://www.fwd.com.hk/online-insurance/vhis-vprime-medical-plan/en/",
    premiumTerms: "Regular pay; online monthly/annual quote options shown",
    premiumRange: "Illustrative first-year monthly premium from HK$119-HK$917 for ANB31 depending on deductible, after promotion assumptions",
    issueAge: "N/A in public page excerpt",
    summary: "VHIS Flexi medical plan with annual benefit limit up to HK$12.5 million, no lifetime benefit limit, six deductible options, deductible waiver for designated crises, cash benefits and no-claims premium discount.",
    updateType: "Current promotion / product page update",
    recentFlag: "Current offer",
    savings: {},
    medical: {
      planType: "VHIS Flexi",
      roomClass: "N/A in page excerpt",
      annualLimit: "Up to HK$12.5 million per policy year",
      lifetimeLimit: "No lifetime benefit limit",
      claimItems: "Hospitalisation and surgical expenses, eligible medical expenses, cash benefits, day case procedures, ICU, major/complex surgeries.",
      copay: "Deductible options HK$0 / 16,000 / 25,000 / 50,000 / 100,000 / 250,000",
      preExisting: "Public page states unknown pre-existing conditions, including congenital conditions, are covered subject to terms.",
      cancerCoverage: "Deductible waiver for designated crises, example includes stage 3 breast cancer."
    },
    ci: {}
  },
  {
    insurer: "FWD Life Insurance Company (Bermuda) Limited (富衛人壽保險)",
    productName: "One&All Medical Insurance Plan",
    category: "Medical",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "2025-08-17; current online promotion as of 2026-05-31 ends 2026-06-10",
    sourceUrl: "https://www.fwd.com.hk/online-insurance/online-promotions/en/",
    premiumTerms: "Regular pay",
    premiumRange: "Daily premium less than HK$3; current promotion shows total 12-month premium waiver in first 2 years",
    issueAge: "N/A in public page excerpt",
    summary: "Mass-market medical cover positioned around flexible public/private hospital-type segmentation and affordable entry protection; active online promotion offers premium waiver benefits.",
    updateType: "Current promotion",
    recentFlag: "Current offer",
    savings: {},
    medical: {
      planType: "Medical insurance",
      roomClass: "Segmented by hospital type / benefit level",
      annualLimit: "N/A in current promotion page",
      lifetimeLimit: "N/A in current promotion page",
      claimItems: "Self-financed public hospital items, drugs, imaging tests and selected private medical support as described by FWD launch materials.",
      copay: "N/A",
      preExisting: "N/A",
      cancerCoverage: "N/A in current promotion page"
    },
    ci: {}
  },
  {
    insurer: "AIA International Limited (友邦保險)",
    productName: "ProsperLife Insurance Plan (活然人生保險計劃)",
    category: "Savings",
    iaClass: "Class A",
    currency: "HKD",
    announcementDate: "2026-03-31; campaign issuance deadline 2026-05-31",
    sourceUrl: "https://www.aia.com.hk/en/about-aia/about-us/media-centre/press-releases/2026/aia-press-release-20260331",
    premiumTerms: "Regular pay; product launch example cites premiums from HKD60 per day",
    premiumRange: "Example: HKD60 per day for HKD1.9 million sum assured",
    issueAge: "N/A in release",
    summary: "Participating whole life plan focused on mortality protection and family settlement flexibility, with death benefit settlement options and first-in-market Beneficiary Flexi Option for beneficiary-driven payout timing after designated age or specified illness.",
    updateType: "Latest 2026 launch / active campaign deadline",
    recentFlag: "Older launch; current campaign",
    savings: {
      guaranteedCash: "Guaranteed cash value not disclosed in release",
      projectedReturn: "N/A",
      bonus: "Participating whole life; release does not disclose dividend mechanics",
      flexibility: "Death Benefit Settlement Option; Beneficiary Flexi Option; add-on riders; PRMP eligible",
      policyLoan: "N/A in release",
      taxDeduction: "N/A",
      annuityCommencement: "N/A"
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "Zurich Life Insurance (Hong Kong) Limited (蘇黎世人壽保險（香港）)",
    productName: "Swiss Prime Savings Insurance Plan (瑞盈儲蓄保險計劃)",
    category: "Savings",
    iaClass: "Class A",
    currency: "Multi-currency / 7 settlement currencies",
    announcementDate: "2026-03-10; policy issue deadline for launch offer 2026-05-29",
    sourceUrl: "https://www.zurich.com.hk/en/about-zurich/news-and-announcements/2026/2026-0310",
    premiumTerms: "2-pay / 5-pay",
    premiumRange: "N/A in release; launch offer up to 58% first-year annualized premium discount plus prepayment interest offer",
    issueAge: "N/A in release",
    summary: "Participating savings plan with short premium commitment, guaranteed cash value, non-guaranteed terminal bonus, terminal bonus lock-in, premium holiday and estate/legacy options including policy split and contingent policyholder nomination.",
    updateType: "Latest 2026 launch / offer deadline",
    recentFlag: "Older launch; May offer deadline",
    savings: {
      guaranteedCash: "Guaranteed cash value offers predictable returns and may increase over policy years; detailed IRR not disclosed in release",
      projectedReturn: "Non-guaranteed terminal bonus; projected IRR not disclosed in release",
      bonus: "Non-guaranteed terminal bonus with lock-in option",
      flexibility: "Premium holiday, 7 settlement currencies, access to policy value, policy split, change of life insured/policyholder, contingent life insured and contingent policyholder nomination.",
      policyLoan: "Access to policy value disclosed; LTV not disclosed",
      taxDeduction: "N/A",
      annuityCommencement: "N/A"
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "Manulife (International) Limited (宏利人壽保險)",
    productName: "GoldenStart Whole Life Immediate Annuity Insurance Plan (宏瑞終身即期年金保險計劃)",
    category: "Savings",
    iaClass: "Class A",
    currency: "N/A in release",
    announcementDate: "2026-04-20",
    sourceUrl: "https://www.manulife.com.hk/en/individual/about/newsroom/manulife-launches-new-annuity-and-accident-protection-solutions.html",
    premiumTerms: "Single premium",
    premiumRange: "N/A in release",
    issueAge: "N/A in release",
    summary: "Whole-life immediate annuity converting single premium into guaranteed monthly income for life, with non-guaranteed terminal bonus potential, Whole Care Benefit for 14 designated critical/mental illness conditions and By Your Side annual payments for Severe Dementia or Parkinson's Disease before age 80.",
    updateType: "Latest 2026 launch found",
    recentFlag: "Older launch",
    savings: {
      guaranteedCash: "Guaranteed monthly income for life commencing from first monthiversary",
      projectedReturn: "Non-guaranteed terminal bonus may be payable on surrender, termination or death",
      bonus: "Non-guaranteed terminal bonus reviewed at least monthly",
      flexibility: "Whole Care Benefit can realize part of available terminal bonus after 14 specified critical/mental illnesses; By Your Side Benefit pays annual amounts for up to 10 years after Severe Dementia/Parkinson's diagnosis before age 80.",
      policyLoan: "N/A in release",
      taxDeduction: "N/A - immediate annuity, not identified as QDAP",
      annuityCommencement: "First monthiversary"
    },
    medical: {},
    ci: {}
  },
  {
    insurer: "AIA International Limited (友邦保險)",
    productName: "AIA Voluntary Health Insurance SelectWise Scheme",
    category: "VHIS",
    iaClass: "Class D",
    currency: "HKD",
    announcementDate: "2026-02-03",
    sourceUrl: "https://www.aia.com.hk/en/about-aia/about-us/media-centre/press-releases/2026/aia-press-release-20260203",
    premiumTerms: "Regular pay",
    premiumRange: "N/A in release",
    issueAge: "N/A in release",
    summary: "VHIS certified plan with no itemised benefit sublimits, designated hospital network, upgraded room options subject to pre-authorization and network doctor conditions, annual limit up to HK$12 million and lifetime limit up to HK$60 million.",
    updateType: "Latest 2026 launch found",
    recentFlag: "Older launch",
    savings: {},
    medical: {
      planType: "VHIS Flexi certified plan",
      roomClass: "Basic ward across Asia; semi-private at eligible designated hospitals in Hong Kong/Macau; Mainland designated hospital room options.",
      annualLimit: "Up to HK$12 million",
      lifetimeLimit: "Up to HK$60 million",
      claimItems: "Hospitalisation, surgical, pre/post confinement, day case outpatient, Chinese medicine outpatient, day surgery cash benefits and Care Concierge services.",
      copay: "Annual deductible options; elderly designated-cancer deductible waiver disclosed",
      preExisting: "Subject to VHIS policy terms; release highlights certified VHIS status",
      cancerCoverage: "Deductible waiver for designated cancer if insured age 75+ and conditions met; designated cancer includes malignant cancer and carcinoma-in-situ with exclusions."
    },
    ci: {}
  }
];

const sourceLog = [
  ["Search query", "Hong Kong life insurance new product launch 2026", accessTime, "Yes", "Specified English query; found AIA ProsperLife and other market results."],
  ["Search query", "AIA Manulife Prudential FWD Sun Life HSBC BOC Life new product Hong Kong 2026", accessTime, "Yes", "Specified English query; found current/older launches and official pages."],
  ["Search query", "QDAP Hong Kong new 2026", accessTime, "Limited", "Specified English query; IA QDAP list found, no new top-10 QDAP launch in past 7 days."],
  ["Search query", "VHIS new plan Hong Kong 2026", accessTime, "Yes", "Specified English query; VHIS official list and AIA/FWD VHIS product pages found."],
  ["Search query", "critical illness insurance Hong Kong new launch 2026", accessTime, "Yes", "Specified English query; found FWD MyCover and non-target insurer CI launches."],
  ["Search query", "savings insurance Hong Kong new 2026", accessTime, "Yes", "Specified English query; found AIA, Zurich and other savings products."],
  ["Search query", "site:aia.com.hk OR site:manulife.com.hk OR site:prudential.com.hk new product 2026", accessTime, "Yes", "Specified English query; official AIA/Manulife results found."],
  ["Search query", "香港人壽保險 新產品 2026", accessTime, "Yes", "Specified Traditional Chinese query."],
  ["Search query", "儲蓄保險 新推出 香港 2026", accessTime, "Yes", "Specified Traditional Chinese query."],
  ["Search query", "危疾保險 新計劃 香港 2026", accessTime, "Yes", "Specified Traditional Chinese query."],
  ["Search query", "QDAP 合資格延期年金 新計劃 2026", accessTime, "Limited", "Specified Traditional Chinese query; no new top-10 QDAP launch found."],
  ["Search query", "VHIS 自願醫保 新計劃 2026", accessTime, "Yes", "Specified Traditional Chinese query."],
  ["Search query", "友邦 宏利 保誠 富衛 永明 滙豐 新產品 2026", accessTime, "Yes", "Specified Traditional Chinese query; found Manulife launch and other market notes."],
  ["Official source", "https://www.chinalife.com.hk/zh-hk/about-us/news-center/china-life-overseas-and-new-frontier-health-hong-kong-forge-strategic", accessTime, "Yes", "Official China Life (Overseas) 2026-05-26 medical partnership update."],
  ["Official source", "https://www.fwd.com.hk/online-insurance/online-promotions/en/", accessTime, "Yes", "Official FWD current online promotions page."],
  ["Official source", "https://www.fwd.com.hk/online-insurance/term-critical-illness/en/", accessTime, "Yes", "Official FWD MyCover product page."],
  ["Official source", "https://www.fwd.com.hk/online-insurance/vhis-vprime-medical-plan/en/", accessTime, "Yes", "Official FWD vPrime product page."],
  ["Official source", "https://www.aia.com.hk/en/about-aia/about-us/media-centre/press-releases/2026/aia-press-release-20260331", accessTime, "Yes", "Official AIA ProsperLife launch release."],
  ["Official source", "https://www.zurich.com.hk/en/about-zurich/news-and-announcements/2026/2026-0310", accessTime, "Yes", "Official Zurich Swiss Prime launch release."],
  ["Official source", "https://www.manulife.com.hk/en/individual/about/newsroom/manulife-launches-new-annuity-and-accident-protection-solutions.html", accessTime, "Yes", "Official Manulife GoldenStart launch release."],
  ["Official source", "https://www.aia.com.hk/en/about-aia/about-us/media-centre/press-releases/2026/aia-press-release-20260203", accessTime, "Yes", "Official AIA SelectWise VHIS launch release."],
  ["Regulatory source", "https://www.ia.org.hk/en/qualifying_deferred_annuity_policy/qdap_all.html", accessTime, "Yes", "IA QDAP list and QDAP field definitions checked."],
  ["Regulatory source", "https://www.vhis.gov.hk/en/consumer_corner/faqs.html", accessTime, "Yes", "VHIS market statistics checked."],
  ["Regulatory source", "https://www.ia.org.hk/en/legislative_framework/circulars/reg_matters/circulars_on_regulatory_matters_2026.html", accessTime, "Yes", "IA circulars checked; no product-standard circular in past 7 days."],
  ["Regulatory source", "https://www.mpfa.org.hk/en/info-centre/laws-and-regulations/guidelines", accessTime, "Yes", "MPFA guideline updates checked; not directly life product related."],
  ["Financial news", "https://www.caproasia.com/2026/05/25/hong-kong-chow-tai-fook-life-insurance-ctf-life-launches-bnp-paribas-linked-index-universal-life-product-for-professional-investors-shiny-treasure-indexed-universal-life-insurance-plan-featuring/", accessTime, "Yes", "Non-target insurer market signal; not included in top-10 tracker rows."],
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
    p.recentFlag
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

const inWindowCount = products.filter(p => p.recentFlag === "Past 7 days").length;
const newLaunch48h = 0;
const productUpdateCount = products.filter(p => p.updateType.includes("update") || p.updateType.includes("promotion") || p.updateType.includes("deadline")).length;

const summaryRows = [
  ["HK Life Insurance Daily Product Briefing", "", "", "", "", ""],
  ["Report Date", reportDate, "Generated", generatedAt, "Research Window", "2026-05-24 to 2026-05-31"],
  ["Total tracked product/product-related entries", { f: "COUNTA('All Products'!A2:A9)", v: products.length }, "Official top-10 items in strict 7-day window", inWindowCount, "New launches past 48h", newLaunch48h],
  ["Product updates / active promotions", productUpdateCount, "Source credibility", "Official insurer/regulatory sources prioritized; financial press used only for market context", "", ""],
  ["Market note", "Quiet week: no official top-10 Class A/C/D new product launch found in the past 48 hours; one China Life (Overseas) medical service update fell within the 7-day window.", "", "", "", ""],
  ["", "", "", "", "", ""],
  ["Count by Category", "", "", "Count by Insurer", "", ""],
  ["Savings", { f: 'COUNTIF(\'All Products\'!C2:C9,"Savings")', v: byCategory.Savings || 0 }, "", "AIA International Limited", byInsurer["AIA International Limited"] || 0, ""],
  ["QDAP", { f: 'COUNTIF(\'All Products\'!C2:C9,"QDAP")', v: byCategory.QDAP || 0 }, "", "China Life Insurance", byInsurer["China Life Insurance"] || 0, ""],
  ["VHIS", { f: 'COUNTIF(\'All Products\'!C2:C9,"VHIS")', v: byCategory.VHIS || 0 }, "", "FWD Life Insurance Company", byInsurer["FWD Life Insurance Company"] || 0, ""],
  ["Medical", { f: 'COUNTIF(\'All Products\'!C2:C9,"Medical")', v: byCategory.Medical || 0 }, "", "Manulife (International) Limited", byInsurer["Manulife"] || 1, ""],
  ["Critical Illness", { f: 'COUNTIF(\'All Products\'!C2:C9,"Critical Illness")', v: byCategory["Critical Illness"] || 0 }, "", "Zurich Life Insurance", byInsurer["Zurich Life Insurance"] || 0, ""],
  ["", "", "", "", "", ""],
  ["Regulatory Intelligence", "", "", "", "", ""],
  ["VHIS", "VHIS FAQ states 100 Certified Plans and 573 products as of 2026-03-31.", "", "", "", ""],
  ["QDAP", "IA QDAP list checked; no top-10 new QDAP launch found in this run.", "", "", "", ""],
  ["IA / MPFA", "IA circulars and MPFA updates checked; no immediate pricing-product filing found in the past 7 days.", "", "", "", ""]
];

const sourceRows = [["Source Type", "Query / URL", "Date-Time Accessed", "Content Found", "Notes"], ...sourceLog];

const sheets = [
  { name: "Summary Dashboard", rows: summaryRows, validations: [] },
  { name: "All Products", rows: allRows, validations: [
    { sqref: `C2:C${products.length + 1}`, formula: '"Savings,QDAP,VHIS,Medical,Critical Illness"' },
    { sqref: `D2:D${products.length + 1}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "Savings & QDAP", rows: savingsRows, validations: [
    { sqref: `C2:C${savingsRows.length}`, formula: '"Savings,QDAP"' },
    { sqref: `D2:D${savingsRows.length}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "VHIS & Medical", rows: medicalRows, validations: [
    { sqref: `C2:C${medicalRows.length}`, formula: '"VHIS,Medical"' },
    { sqref: `D2:D${medicalRows.length}`, formula: '"Class A,Class C,Class D"' }
  ] },
  { name: "Critical Illness", rows: ciRows, validations: [
    { sqref: `C2:C${ciRows.length}`, formula: '"Critical Illness"' },
    { sqref: `D2:D${ciRows.length}`, formula: '"Class A,Class C,Class D"' }
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

function styleForCell(sheetName, rowIndex, colIndex, cell) {
  if (cell && typeof cell === "object" && cell.style != null) return cell.style;
  if (rowIndex === 0) return sheetName === "Summary Dashboard" ? 7 : 1;
  if (sheetName === "All Products" && colIndex === 5) {
    const p = products[rowIndex - 1];
    if (p?.recentFlag === "Past 7 days") return 4;
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
  if (cell.v === null || cell.v === undefined || cell.v === "") {
    return `<c r="${ref}" s="${style}"/>`;
  }
  if (typeof cell.v === "number") {
    return `<c r="${ref}" s="${style}"><v>${cell.v}</v></c>`;
  }
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
    widths.push(Math.min(Math.max(Math.ceil(max * 0.9), 10), c === 10 ? 70 : 48));
  }
  return widths;
}

function sheetXml(sheet) {
  const rows = sheet.rows;
  const cols = columnWidths(rows).map((width, i) => `<col min="${i + 1}" max="${i + 1}" width="${width}" customWidth="1"/>`).join("");
  const rowXml = rows.map((row, r) => {
    const cells = row.map((cell, c) => cellXml(sheet.name, r, c, cell)).join("");
    const height = r === 0 ? 24 : (String(row.join(" ")).length > 180 ? 60 : 30);
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
<dc:creator>Codex</dc:creator><cp:lastModifiedBy>Codex</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-05-31T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-05-31T00:00:00Z</dcterms:modified><dc:title>HK Insurance Daily Briefing ${reportDate}</dc:title></cp:coreProperties>`;
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

function dosDateTime(date = new Date("2026-05-31T00:00:00Z")) {
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
  emailSubject: `[HK Insurance Daily] Product Briefing - ${reportDate} | ${inWindowCount} new/updated product`,
  emailHtml: buildEmailHtml()
};
fs.writeFileSync(summaryPath, JSON.stringify(validation, null, 2), "utf8");
console.log(JSON.stringify(validation, null, 2));

function buildEmailHtml() {
  const recentProducts = products.filter(p => p.recentFlag === "Past 7 days");
  const updates = products.filter(p => p.recentFlag !== "Past 7 days");
  const categoryCounts = ["Savings", "QDAP", "VHIS", "Medical", "Critical Illness"]
    .map(c => `${c}(${byCategory[c] || 0})`).join(" | ");
  const launchHtml = recentProducts.length
    ? recentProducts.map(p => `<p><b style="color:#1f4e79;">${xmlEscape(p.insurer.split(" (")[0])}</b> - ${xmlEscape(p.productName)} (${xmlEscape(p.category)})<br><b>Key features:</b></p><ul><li>${xmlEscape(p.summary)}</li><li>${xmlEscape(p.medical?.claimItems || p.savings?.flexibility || p.ci?.conditions || "See tracker for details.")}</li></ul><p>Source: <a href="${xmlEscape(p.sourceUrl)}">${xmlEscape(p.sourceUrl)}</a></p>`).join("")
    : "<p>No official top-10 new product launch was found in the past 48 hours.</p>";
  const updatesHtml = updates.slice(0, 7).map(p => `<li><b>${xmlEscape(p.insurer.split(" (")[0])}</b> - ${xmlEscape(p.productName)}: ${xmlEscape(p.updateType)}. <a href="${xmlEscape(p.sourceUrl)}">Source</a></li>`).join("");
  return `<!doctype html><html><body style="font-family:Arial,sans-serif;font-size:14px;color:#1f1f1f;">
<h2>HK Life Insurance Daily Product Briefing</h2>
<p><b>Date:</b> ${reportDate} | <b>Generated at:</b> 08:00 HKT</p>
<h3>EXECUTIVE SUMMARY</h3>
<ul>
<li>Total products/product-related entries included: ${products.length}</li>
<li>New launches (past 48 hrs): ${newLaunch48h}</li>
<li>Official top-10 product-related updates in past 7 days: ${inWindowCount}</li>
<li>Product updates / active promotions tracked: ${productUpdateCount}</li>
<li>Categories covered: ${categoryCounts}</li>
</ul>
<p><b>Market note:</b> The strict 7-day window was quiet for top-10 Hong Kong life insurers. The only official top-10 product-related update found was China Life (Overseas)' medical direct-billing network expansion. The workbook also includes current official product pages/promotions and latest 2026 launch references for pricing context.</p>
<h3>HIGHLIGHTS - NEW LAUNCHES / UPDATES</h3>
${launchHtml}
<h3>RECENT UPDATES AND CURRENT PRODUCT WATCHLIST</h3>
<ul>${updatesHtml}</ul>
<h3>MARKET INTELLIGENCE</h3>
<ul>
<li>VHIS official FAQ states that as of 2026-03-31 there were 100 Certified Plans and 573 products in market.</li>
<li>IA QDAP list was checked; no new target-insurer QDAP launch was identified in this run.</li>
<li>IA circulars and MPFA updates were checked; no immediate Class A/C/D pricing-product regulatory filing was found for the past 7 days.</li>
</ul>
<h3>NOTES</h3>
<ul>
<li>Data sourced from public insurer websites, IA, VHIS, MPFA and selected financial press for market context.</li>
<li>Covers Class A, C and D product categories requested; IA class labels are inferred from public category where not explicitly stated in source.</li>
<li>Full Excel tracker is attached and saved in the local outputs folder.</li>
<li>This is an automated research digest - verify details against official product documents before pricing work.</li>
</ul>
</body></html>`;
}
