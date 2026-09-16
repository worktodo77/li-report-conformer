"""Fictitious forensic-delay prose pools. Composed into paragraphs of varied length so a compact
module emits report-scale content. All names, projects, numbers are invented test data."""

PROJECT = "the Marisol Bay LNG Terminal"
EMPLOYER = "Costa Verde Energia S.A."
CONTRACTOR = "Northbridge EPC Constructors, Ltd."
EXPERT = "Dr. Evelyn A. Marchetti, P.E., CCP, PSP"
FIRM = "Meridian Forensic Advisors"
CASE = "ICC Arbitration No. 27,431/MHM"
COUNSEL = "Halloran & Voss LLP"

AUTHORS = [
    ("Dr. Evelyn Marchetti", "EM"),
    ("James Okonkwo", "JO"),
    ("Priya Raman", "PR"),
    ("Counsel review", "CR"),
    ("T. Nakamura", "TN"),
]

# sentence pools by rhetorical role -------------------------------------------------
FINDING = [
    "The contemporaneous schedule updates demonstrate that the critical path ran through the {a} works from data date {m}.",
    "As shown in the record, the {a} activity absorbed its available float by the {m} update and thereafter drove the forecast completion date.",
    "The delay to {a} was neither foreseeable at tender nor within the Contractor's control, based on the documents reviewed.",
    "My analysis indicates a net slippage of {n} working days to the Contract Completion Date attributable to the {a} events.",
    "The evidence establishes that the {a} interface was not released for construction until well after the planned start.",
    "Progress on {a} stalled during the window, and the as-built records show no compensating acceleration.",
]
METHOD = [
    "I applied a windows-based analysis consistent with AACE International Recommended Practice 29R-03, measuring loss or gain of time update to update.",
    "For each window I validated the schedule update, identified the controlling path, and quantified movement of the completion milestone.",
    "Where the contemporaneous updates were unreliable, I reconstructed the as-built critical path from the daily records.",
    "Float ownership was assessed in accordance with the governing Subcontract and the Society of Construction Law Delay and Disruption Protocol.",
    "Concurrency was tested against the four established prerequisites before any offset was applied to the compensable position.",
]
BACKGROUND = [
    "The Project comprised the engineering, procurement, and construction of a two-train liquefaction facility with associated marine works.",
    "The Contract incorporated a lump-sum price with liquidated damages of USD {n},000 per day for late completion.",
    "Notice to Proceed was issued and the planned duration was {n} calendar months to mechanical completion.",
    "The baseline programme was accepted by the Engineer subject to the qualifications recorded in the transmittal.",
    "The parties are in dispute over responsibility for a delay of approximately {n} months to first production.",
]
OPINION = [
    "In my opinion, and to a reasonable degree of professional certainty, the {a} delay is excusable and compensable.",
    "It is my opinion that the Contractor is entitled to an extension of time of {n} working days for the {a} events.",
    "I hold the opinion that the concurrent-delay assertion advanced in the Rebuttal is not supported by the contemporaneous record.",
]
QUOTE = [
    "The Contractor shall be entitled to an extension of time if and to the extent that completion is or will be delayed by any of the Employer's Risk Events, provided that notice is given within the period stated in the Contract.",
    "Neither party shall be liable to the other for any delay or failure to perform to the extent such delay is caused by a Force Majeure Event, subject to the mitigation obligations set out herein.",
    "Ownership of float shall reside with the Project and shall be available to the party first requiring it, save where the Contract expressly provides otherwise.",
]
ACRONYMS = [
    ("AACE", "Association for the Advancement of Cost Engineering"),
    ("APAB", "As-Planned versus As-Built"),
    ("CPM", "Critical Path Method"),
    ("EOT", "Extension of Time"),
    ("LD", "Liquidated Damages"),
    ("NTP", "Notice to Proceed"),
    ("RFI", "Request for Information"),
    ("SCL", "Society of Construction Law"),
    ("TIA", "Time Impact Analysis"),
    ("WBS", "Work Breakdown Structure"),
]
ACTIVITIES = ["piling", "substructure", "LNG tank", "pipe-rack", "compressor foundation",
              "jetty topsides", "flare package", "control building", "electrical building",
              "commissioning"]
EXHIBITS = [
    "Baseline Programme Rev. 0 (native P6 .xer)",
    "Monthly Progress Reports Nos. 1 through 24",
    "Subcontract Agreement and General Conditions",
    "Engineer's Determination Letter dated 14 March",
    "Request-for-Information Log (consolidated)",
    "As-Built Schedule reconstructed by the expert",
    "Correspondence bundle (delay notices)",
    "Weather records for the Project site",
    "Change Order Register Rev. 6",
    "Minutes of the Monthly Progress Meetings",
]
ATTACHMENTS = [
    "Curriculum Vitae of the Expert",
    "Materials Considered / Reliance List",
    "Windows Analysis Workbook (native)",
    "Fragnet Library and Logic Basis",
    "Concurrency Candidates Register",
    "Fee Schedule and Statement of Independence",
]
SECTIONS = [
    ("Introduction and Qualifications", "intro"),
    ("Scope of the Assignment", "scope"),
    ("Summary of Opinions", "opinions"),
    ("The Project and the Parties", "background"),
    ("Sources Relied Upon and Their Validation", "sources"),
    ("Methodology", "method"),
    ("Window Analysis of the Critical Path", "windows"),
    ("The Delay Events", "events"),
    ("Concurrency and Pacing", "concurrency"),
    ("Quantification of Extension of Time", "quantum"),
    ("The Respondent's Rebuttal Considered", "rebuttal"),
    ("Conclusions", "conclusions"),
]
FOOTNOTES = [
    "AACE International, Recommended Practice No. 29R-03, Forensic Schedule Analysis (rev. 2011), §3.",
    "Society of Construction Law, Delay and Disruption Protocol (2nd ed., 2017), Core Principle 4.",
    "Baseline Programme Rev. 0, activity {a}, total float as reported at data date.",
    "Monthly Progress Report No. {n}, narrative section, page reference omitted for brevity.",
    "Engineer's Determination Letter, paragraph 12; see Exhibit for the full text.",
    "Witness Statement of the Project Controls Manager, paragraph {n}.",
]
