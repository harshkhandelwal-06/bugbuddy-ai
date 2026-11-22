"""Build the submission documents from the real data in this repository.

  python code/build_docs.py            # draft: missing items are shown in red as TO FILL
  python code/build_docs.py --final    # refuses to finish while anything is still TO FILL

Creates in docs/:  M2_<TeamID>_<Title>.pdf, <TeamName>_BMC.pdf and FORM_ANSWERS.md
Numbers, test tables and iteration results come ONLY from test-data/results.json
(written by run_tests.py evaluate). Nothing is invented here.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from bugbuddy.prompts import VERSIONS, load_prompt, load_version  # noqa: E402

TEAM = json.loads((ROOT / "team.json").read_text(encoding="utf-8"))
TESTS = json.loads((ROOT / "test-data/tests.json").read_text(encoding="utf-8"))
RES_PATH = ROOT / "test-data/results.json"
RESULTS = json.loads(RES_PATH.read_text(encoding="utf-8")) if RES_PATH.exists() else {}
DOCS = ROOT / "docs"
WARN: list[str] = []

ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.2)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=7.6, leading=9.4)
CELL = ParagraphStyle("c", parent=BODY, fontSize=7.8, leading=9.6)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, spaceBefore=4, spaceAfter=6,
                    textColor=colors.HexColor("#1F3A6E"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11, spaceBefore=8, spaceAfter=3,
                    textColor=colors.HexColor("#1F3A6E"))
H3 = ParagraphStyle("h3", parent=BODY, fontName="Helvetica-Bold", fontSize=9.2, spaceBefore=5, spaceAfter=2)
CODE = ParagraphStyle("code", fontName="Courier", fontSize=6.6, leading=7.8, backColor=colors.HexColor("#F5F5F5"),
                      borderPadding=3, spaceAfter=4)
TITLE = ParagraphStyle("t", parent=H1, fontSize=22, leading=27, alignment=TA_LEFT, spaceAfter=10)
RED = "#C0392B"


def clean(s) -> str:
    return str(s).encode("latin-1", "replace").decode("latin-1")


def ph(value, what="") -> str:
    """Escaped text; unresolved TO_FILL becomes a red marker and a warning."""
    v = clean(value)
    if v.strip() in ("TO_FILL", "", "None"):
        WARN.append(what or "a TO_FILL value")
        return f'<font color="{RED}"><b>[TO FILL{": " + escape(what) if what else ""}]</b></font>'
    return escape(v)


def P(text, style=BODY):
    return Paragraph(text, style)


def pending(msg):
    WARN.append(msg)
    return P(f'<font color="{RED}"><b>[{escape(msg)}]</b></font>', BODY)


def code_block(text: str, width=105):
    lines = []
    for ln in clean(text).replace("\t", "    ").splitlines() or [""]:
        lines += textwrap.wrap(ln, width, replace_whitespace=False, drop_whitespace=False,
                               subsequent_indent="   ", break_long_words=True) or [""]
    return Preformatted("\n".join(lines), CODE)


def grid(data, widths, header=True, font=7.8, zebra=True):
    rows = [[c if not isinstance(c, str) else P(c, CELL) for c in r] for r in data]
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA7BD")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F7"))]
    if zebra:
        st += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")])]
    t.setStyle(TableStyle(st))
    return t


def hdr(*cols):
    return [f"<b>{escape(c)}</b>" for c in cols]


# ---------------------------------------------------------------- data helpers
HAS_V4 = bool(RESULTS.get("tests", {}).get("v4"))
MODEL = (f"{RESULTS['provider']} / {RESULTS['model']}" if RESULTS.get("model") else "TO_FILL")


def verdict(version, tid):
    return RESULTS.get("tests", {}).get(version, {}).get(str(tid))


def record(version, tid):
    p = ROOT / "test-data/outputs" / version / f"test{tid:02d}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def module_status():
    out = []
    for m in TEAM["modules"]:
        st = m["status"]
        if st == "LIVE":
            st = "Working" if HAS_V4 else "Not verified yet"
        out.append({**m, "status": st})
    return out


def metrics_text(v):
    m = RESULTS.get("versions", {}).get(v)
    if not m:
        return None
    js = f"{m['json_valid']}/{m['json_total']}" if m["json_total"] else "not JSON"
    return (f"Overall {m['pass_total']}/{m['runs']} tests passed. Fixed code ran and printed the expected output "
            f"in {m['fix_pass']}/{m['fix_total']} fix tests; invalid inputs declined correctly "
            f"{m['decline_pass']}/{m['decline_total']}; valid JSON {js}. Average time {m['avg_latency_s']} s per input.")


def short_actual(tid):
    v = verdict("v4", tid)
    if not v:
        return "(not run yet)"
    if v["pass"]:
        first = (v.get("stdout") or "").strip().splitlines()[:1]
        return clean(v["reason"] + (f" - printed: {first[0][:40]}" if first else ""))
    return clean(v["reason"])


# ---------------------------------------------------------------- BMC
def bmc_flowables(width):
    def cell(title, items):
        body = "<br/>".join("- " + escape(i) for i in items)
        return [P(f"<b>{escape(title)}</b>", ParagraphStyle("bt", parent=CELL, fontSize=8.6, textColor=colors.HexColor("#1F3A6E"))),
                P(body, ParagraphStyle("bb", parent=CELL, fontSize=7.4, leading=9.3))]
    KP = cell("Key Partners", ["LLM providers (Google Gemini, Anthropic Claude, OpenAI-compatible APIs)",
                               "Hosting platforms (Streamlit Community Cloud, Hugging Face Spaces)",
                               "Universities, faculty and teaching assistants (pilot users, feedback)",
                               "Coding-practice platforms and student clubs (distribution)"])
    KA = cell("Key Activities", ["Designing and improving prompts (P1, P2) with versioned testing",
                                 "Testing against a growing set of common beginner errors",
                                 "Maintaining the web app and the LLM adapter",
                                 "Collecting user feedback and fixing failing cases",
                                 "Adding more programming languages"])
    KR = cell("Key Resources", ["Prompt library and test suite (14 cases, growing)",
                                "App code (Streamlit, Python) and automatic checker",
                                "LLM API access and hosting",
                                "Team skills in prompt engineering and Python"])
    VP = cell("Value Proposition", ["Paste code and error, get the cause, a fix that has been checked on our tests, and a simple explanation in seconds",
                                    "Teaches how to debug (steps + tip) instead of only giving the answer",
                                    "Says what is missing instead of guessing when input is incomplete",
                                    "Never repeats secrets such as API keys from pasted code",
                                    "Free to try, no setup"])
    CR = cell("Customer Relationships", ["Self-service web app",
                                         "Thumbs up/down feedback on every answer (planned)",
                                         "Instructor-facing guidance for classroom use (planned)",
                                         "Student community channels for tips and bug samples"])
    CH = cell("Channels", ["Web app (public link)", "College LMS and coding-lab announcements",
                           "GitHub README and student communities (Discord, WhatsApp)",
                           "Future: VS Code extension"])
    CS = cell("Customer Segments", ["First- and second-year CS students (main users)",
                                    "Self-learners and bootcamp students",
                                    "Junior developers",
                                    "Teachers and lab assistants who answer many debugging questions",
                                    "Colleges and coding clubs (institutional buyers)"])
    CO = cell("Cost Structure", ["LLM API usage cost per request (largest variable cost)",
                                 "Hosting and domain", "Development and prompt-testing time",
                                 "Campus outreach and support", "Test infrastructure"])
    RV = cell("Revenue Streams", ["Freemium: free daily limit for students",
                                  "Paid student plan with higher limits and history",
                                  "Institution licence for colleges and coding bootcamps",
                                  "API or LMS plug-in for coding platforms"])
    w = width / 5
    data = [[KP, KA, VP, CR, CS], ["", KR, "", CH, ""], [CO, "", "", RV, ""]]
    t = Table(data, colWidths=[w] * 5, rowHeights=[5.3 * cm, 4.3 * cm, 3.6 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#3B5B9A")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (2, 0), (2, 1)), ("SPAN", (4, 0), (4, 1)),
        ("SPAN", (0, 2), (2, 2)), ("SPAN", (3, 2), (4, 2)),
        ("BACKGROUND", (2, 0), (2, 1), colors.HexColor("#EEF3FB")),
        ("BACKGROUND", (0, 2), (2, 2), colors.HexColor("#FFF8E6")), ("BACKGROUND", (3, 2), (4, 2), colors.HexColor("#EAF7EE")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return [t]


def build_bmc(path: Path):
    doc = BaseDocTemplate(str(path), pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                          topMargin=1.0 * cm, bottomMargin=1.0 * cm, title="Business Model Canvas - BugBuddy AI")
    w = landscape(A4)[0] - 2.4 * cm
    doc.addPageTemplates([PageTemplate("p", [Frame(doc.leftMargin, doc.bottomMargin, w, landscape(A4)[1] - 2 * cm, id="f")])])
    story = [P("Business Model Canvas - BugBuddy AI (Bug Explanation and Fix Assistant)", ParagraphStyle("x", parent=H1, fontSize=13, spaceAfter=2)),
             P(f"Team {ph(TEAM['team_name'])} | Team ID {ph(TEAM['team_id'], 'Team ID')} | SCSE4041 Prompt Engineering", SMALL),
             Spacer(1, 5)] + bmc_flowables(w)
    doc.build(story)


# ---------------------------------------------------------------- M2 PDF
def prompt_sheet(pid_file):
    pr = load_prompt(pid_file)
    s = pr.settings
    rec = record("v4", 1)
    sample = []
    if rec:
        step = next((x for x in rec["steps"] if x["prompt_id"] == pr.id), None)
        if step:
            sample = [P("<b>One sample run</b> (test 1, real input and actual output of the saved run)", BODY),
                      P("Input sent:", SMALL), code_block(step["user_prompt"]), P("Actual output:", SMALL),
                      code_block(step["raw"][:1800])]
    if not sample:
        sample = [pending(f"sample run for {pr.id}: run python code/run_tests.py run, then evaluate")]
    vars_ = ("{language} = programming language chosen by the user; {code} = the code snippet; "
             "{error} = error message or description of the wrong behaviour")
    if pr.id == "P2":
        vars_ += "; {diagnosis} = JSON diagnosis produced by P1 (error_type, root_cause, location, bugs_found, other_bugs, contains_secret)"
    rows = [[P("<b>Prompt ID and name</b>", CELL), P(escape(f"{pr.id} - {s.get('name', '')}"), CELL)],
            [P("<b>Step in the workflow</b>", CELL), P(escape(s.get("step", "")), CELL)],
            [P("<b>Purpose</b>", CELL), P(escape(s.get("purpose", "")), CELL)],
            [P("<b>Tool and model</b>", CELL), P(ph(MODEL, "model (appears after the test run)"), CELL)],
            [P("<b>Settings</b>", CELL), P(f"temperature {escape(s.get('temperature', 'default'))}; other settings default", CELL)],
            [P("<b>Examples included</b>", CELL), P(escape(s.get("examples", "0")), CELL)],
            [P("<b>Output format</b>", CELL), P(escape(s.get("output", "")), CELL)],
            [P("<b>Variables</b>", CELL), P(escape(vars_), CELL)]]
    t = Table(rows, colWidths=[3.6 * cm, 13.4 * cm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA7BD")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF3FB"))]))
    return [P(f"Prompt sheet {pr.id}", H2), t, P("<b>Full system prompt</b>", H3), code_block(pr.system),
            P("<b>Full user prompt template</b>", H3), code_block(pr.user)] + sample


def build_m2(path: Path, shots: list[Path], repo_shot: Path | None):
    W, Hh = A4
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                          bottomMargin=1.6 * cm, title=f"Milestone 2 - {TEAM['project_title']}")

    def foot(c, d):
        c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
        c.drawString(2 * cm, 0.9 * cm, f"SCSE4041 Milestone 2 - {clean(TEAM['team_name'])} - {clean(TEAM['project_title'])}")
        c.drawRightString(W - 2 * cm, 0.9 * cm, f"Page {d.page}"); c.restoreState()

    def foot_l(c, d):
        c.saveState(); c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
        c.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.6 * cm, f"Page {d.page}"); c.restoreState()

    doc.addPageTemplates([
        PageTemplate("portrait", [Frame(2 * cm, 1.6 * cm, W - 4 * cm, Hh - 3.4 * cm, id="p")], onPage=foot),
        PageTemplate("landscape", [Frame(1.2 * cm, 1.0 * cm, landscape(A4)[0] - 2.4 * cm, landscape(A4)[1] - 2 * cm, id="l")],
                     pagesize=landscape(A4), onPage=foot_l)])
    S: list = []
    full = W - 4 * cm
    mem = TEAM["members"]

    # 1 Cover page
    S += [P("1. Cover page", H1), Spacer(1, 6), P("SCSE4041 Prompt Engineering - Mini Project - Milestone 2", H2),
          P(escape(clean(TEAM["project_title"])), TITLE)]
    info = [hdr("Item", "Details"),
            ["Team ID", ph(TEAM["team_id"], "Team ID")], ["Team name", ph(TEAM["team_name"])],
            ["Project title", ph(TEAM["project_title"])], ["Batch", ph(TEAM["batch"], "batch")],
            ["Faculty name", ph(TEAM["faculty"], "faculty name")]]
    S += [grid(info, [4 * cm, full - 4 * cm]), Spacer(1, 8), P("Team members", H3),
          grid([hdr("Name", "Enrollment no.", "Official email")] +
               [[escape(m["name"]), m["enrollment"], m["enrollment"].lower() + "@bennett.edu.in"] for m in mem],
               [6 * cm, 4 * cm, full - 10 * cm]), Spacer(1, 8), P("Links", H3),
          grid([hdr("Link", "URL")] + [["Prototype", ph(TEAM["links"]["prototype"], "prototype link")],
                                       ["Repository / folder", ph(TEAM["links"]["repo"], "repository link")],
                                       ["Reel", ph(TEAM["links"]["reel"], "reel link")]], [4 * cm, full - 4 * cm]),
          PageBreak()]

    # 2 Prompt and solution design
    S += [P("2. Prompt and solution design", H1), P("2(a) Design summary", H2)]
    S += [P("<b>Problem and users.</b> Students and junior developers lose time because compiler and runtime error messages are "
            "hard to read and the fix is not obvious. BugBuddy AI takes a programming language, a code snippet and an error message "
            "(or a description of wrong behaviour) and returns the cause, a corrected program, a beginner-friendly explanation, "
            "short debugging steps and one prevention tip."),
          P("<b>Input and output.</b> Input: language, code, error text. Output: a structured result (status, error type, root cause, "
            "location, fixed code, explanation, steps, tip). When the input is incomplete or is not code, BugBuddy says exactly what is "
            "missing and writes no fix instead of guessing."),
          P("<b>Number of prompts and why.</b> Two prompts in a fixed sequence. P1 checks the input and diagnoses the problem "
            "(including extra hidden bugs and secrets). P2 writes the fix and the explanation using the P1 diagnosis. Splitting the job "
            "gives each prompt one task, lets the pipeline stop after P1 for unusable input, and lets us test the diagnosis and the fix separately."),
          P(f"<b>Tool and model.</b> A Streamlit web app written in Python calls an LLM through an API adapter. Model used in all tests: "
            f"{ph(MODEL, 'model name (appears after the test run)')}. We use one model for all prompt versions so differences in the test results "
            "come from the prompts, not from the model."),
          P("<b>What changed since Milestone 1.</b> Milestone 1 had one free-text baseline prompt and a plan to compare several models. "
            "Now the baseline is saved as v1 and improved through v2 (JSON output), v3 (rules, 2 examples, temperature 0.2) and v4 "
            "(two-prompt workflow with an input guard). We narrowed the plan to one model and compared prompt versions instead, because that "
            "gave a controlled experiment. A working app, 14 automated tests and a test runner that executes the model's fixed code were added.")]
    S += [P("2(b) Diagrams", H2)]
    for fn, cap in [("1_prompt_workflow.png", "Figure 1. Prompt workflow"), ("2_task_decomposition.png", "Figure 2. Task decomposition"),
                    ("3_input_output_flow.png", "Figure 3. Input-output flow"), ("4_system_architecture.png", "Figure 4. System architecture (app with code)")]:
        im = Image(str(DOCS / "diagrams" / fn))
        iw, ih = im.imageWidth, im.imageHeight
        maxh = 9.2 * cm if "workflow" in fn else 6.2 * cm
        sc = min(full / iw, maxh / ih)
        im.drawWidth, im.drawHeight = iw * sc, ih * sc
        S += [KeepTogether([im, P(f"<i>{cap}</i>", SMALL)]), Spacer(1, 4)]
    S += [P("No agent loop or retrieval (RAG) is used, so those diagrams are not included.", SMALL), P("2(c) Prompt sheets", H2)]
    for f in VERSIONS["v4"]:
        S += prompt_sheet(f) + [PageBreak()]

    # 3 Implementation
    S += [P("3. Implementation", H1), P("3(a) What is built", H2),
          P("A working Streamlit web app (code/app.py). The user picks a language, pastes code and the error, and presses the button. "
            "The app runs P1, stops with a clear request for more information if the input is unusable, otherwise runs P2 and shows the cause, "
            "fixed code, explanation, debugging steps and tip. Prompts are plain text files in prompts/ and are loaded by the code, so the "
            "files in the repository are exactly what the app uses. API keys are read from environment variables or Streamlit secrets and are "
            "never stored in the repository."), P("3(b) Module status", H2)]
    S += [grid([hdr("Module", "What it does", "Status", "Notes")] +
               [[escape(m["name"]), escape(m["does"]), f"<b>{escape(m['status'])}</b>", escape(m["notes"])] for m in module_status()],
               [3.6 * cm, 6.4 * cm, 2.4 * cm, full - 12.4 * cm])]
    S += [P("3(c) Prompt iteration log", H2)]
    log = [
        ("v1", "First prompt from Milestone 1: a role, three tasks (cause, corrected code, simple explanation) and 'say what is missing instead of guessing'. Free-text answer. Default settings.",
         "Starting point (Milestone 1 baseline)."),
        ("v2", "Added a fixed JSON format (status, error_type, root_cause, fixed_code, explanation, steps, tip, missing_info) and status values for missing or non-code input.",
         "The app needs separate fields to display and the checker needs the fixed code on its own; free text cannot be read reliably by a program."),
        ("v3", "Added 2 worked examples (one fix, one 'needs_more_info'), rules (smallest change, fix every bug, diagnose from code when no error is given, never repeat secrets) and temperature 0.2.",
         "To make behaviour and format more consistent and to cover the edge cases in our test set (several bugs, no error message, secrets)."),
        ("v4 (final)", "Split into two prompts. P1 (temperature 0.0, 3 examples) checks the input and diagnoses; P2 (temperature 0.2, 1 example) writes the fix using the P1 diagnosis. The pipeline stops after P1 for unusable input.",
         "One job per prompt; a guard step so no fix is invented for missing or non-code input; P1 passes hidden extra bugs and secret warnings to P2."),
    ]
    rows, prev = [hdr("Version", "What changed", "Why it was changed", "Result after the change (from our test runs)")], None
    for v, what, why in log:
        key = v.split()[0]
        txt = metrics_text(key)
        m = RESULTS.get("versions", {}).get(key)
        if txt and prev is not None and m:
            d = m["pass_total"] - prev["pass_total"]
            txt += f" Change in overall passes versus the previous version: {d:+d}."
        if not txt:
            WARN.append(f"results for {key}")
            txt = f'<font color="{RED}"><b>[TO FILL: run tests]</b></font>'
        prev = m or prev
        rows.append([f"<b>{escape(v)}</b>", escape(what), escape(why), txt])
    S += [grid(rows, [1.6 * cm, 5.6 * cm, 4.2 * cm, full - 11.4 * cm])]
    vs = RESULTS.get("versions", {})
    if vs and "v4" in vs:
        best = max(vs.values(), key=lambda x: x["pass_total"])["pass_total"]
        if vs["v4"]["pass_total"] < best:
            lead = [k for k, x in vs.items() if x["pass_total"] == best]
            S += [P(f"<b>Note:</b> the final workflow (v4) scored {vs['v4']['pass_total']}/{vs['v4']['runs']}, "
                    f"lower than {', '.join(lead)} ({best}). We report this as measured.", BODY)]
    obs = (DOCS / "observations.md").read_text(encoding="utf-8").strip() if (DOCS / "observations.md").exists() else ""
    obs = "\n".join(l for l in obs.splitlines() if not l.startswith("(Optional)") and not l.startswith("(for example") and
                    not l.startswith("Delete this") and not l.startswith("files"))
    if obs.strip():
        S += [P("<b>Team observations</b>", H3), P(escape(clean(obs)).replace("\n", "<br/>"))]
    S += [P("Full text of each version", H2)]
    for v in ("v1", "v2", "v3"):
        pr = load_version(v)[0]
        S += [P(f"{v} (temperature {pr.settings.get('temperature')}, {pr.settings.get('examples')} examples)", H3),
              P("System prompt:", SMALL), code_block(pr.system), P("User prompt template:", SMALL), code_block(pr.user)]
    S += [P("v4 (final): the full text of P1 and P2 is in the prompt sheets in Section 2(c).", BODY), PageBreak()]

    # 4 Demonstration and testing
    S += [P("4. Demonstration and testing", H1), P("4(a) Test table (final workflow v4)", H2)]
    rows = [hdr("Test", "Input (short)", "Type", "Expected output", "Actual output (short)", "Pass / Fail")]
    for t in TESTS:
        v = verdict("v4", t["id"])
        pf = "-" if not v else ("<b>Pass</b>" if v["pass"] else f'<font color="{RED}"><b>Fail</b></font>')
        rows.append([str(t["id"]), escape(clean(t["short"])), t["type"], escape(t["expected"]), escape(short_actual(t["id"])), pf])
    S += [grid(rows, [1.0 * cm, 4.6 * cm, 1.5 * cm, 3.9 * cm, 4.4 * cm, full - 15.4 * cm])]
    if not HAS_V4:
        S += [pending("test results: run python code/run_tests.py run, then evaluate")]
    S += [P("Pass/Fail is decided automatically by code/checker.py: for fix tests the model's fixed code is executed and must run and print the "
            "expected text; for invalid inputs the model must ask for more information and give no fix. Each cell is one run of the saved prompt.", SMALL),
          P("4(b) All prompt versions on the same 14 tests", H2)]
    rows = [hdr("Version", "Overall", "Fix verified", "Invalid declined", "Valid JSON", "Avg time (s)")]
    for v in ("v1", "v2", "v3", "v4"):
        m = vs.get(v)
        if m:
            rows.append([v, f"{m['pass_total']}/{m['runs']}", f"{m['fix_pass']}/{m['fix_total']}", f"{m['decline_pass']}/{m['decline_total']}",
                         f"{m['json_valid']}/{m['json_total']}" if m["json_total"] else "n/a (free text)", str(m["avg_latency_s"])])
    S += [grid(rows, [2 * cm, 2.6 * cm, 3 * cm, 3.4 * cm, 3.4 * cm, full - 14.4 * cm]) if len(rows) > 1 else pending("version comparison table"),
          P("4(c) Screenshots of real runs", H2)]
    if shots:
        for sp in shots[:3]:
            n = re.search(r"(\d+)", sp.stem)
            im = Image(str(sp)); sc = min(full / im.imageWidth, 7.4 * cm / im.imageHeight)
            im.drawWidth, im.drawHeight = im.imageWidth * sc, im.imageHeight * sc
            S += [KeepTogether([im, P(f"<i>Screenshot of test {int(n.group(1)) if n else '?'}</i>", SMALL)])]
    else:
        S += [pending("add 2-3 real screenshots: save them as docs/screenshots/test01.png, test09.png ... (number = test no.)")]
    fails = [t for t in TESTS if verdict("v4", t["id"]) and not verdict("v4", t["id"])["pass"]]
    S += [P("4(d) Known limitations and next steps", H2)]
    lim = ["<b>Pass/Fail checks that the fix runs, not that the explanation is good.</b> Next: add a short rubric (clear, correct, beginner-friendly) scored by teammates on a sample of answers.",
           "<b>Small test set, one run per test.</b> Model replies can differ between runs. Next: run each test 3 times and report how often the result changes.",
           "<b>Only Python and JavaScript are checked automatically.</b> Java, C and C++ are accepted by the app but not tested. Next: add compile-and-run checks for them.",
           "<b>One attempt only.</b> If the fix does not run, the app does not notice. Next: try the fix, and on failure send the new error back to P2 (a small agent loop)."]
    if fails:
        lim.insert(0, "<b>Failed tests with the final workflow:</b> " + "; ".join(f"test {t['id']} ({escape(verdict('v4', t['id'])['reason'])})" for t in fails) +
                   ". Next: study these outputs and change the prompt rules for them.")
    S += [P("<br/>".join(f"{i + 1}. {x}" for i, x in enumerate(lim[:5])))]
    S += [PageBreak()]

    # 5 Repository
    S += [P("5. Repository", H1)]
    if repo_shot:
        im = Image(str(repo_shot)); sc = min(full / im.imageWidth, 8 * cm / im.imageHeight)
        im.drawWidth, im.drawHeight = im.imageWidth * sc, im.imageHeight * sc
        S += [im, P("<i>Screenshot of the repository</i>", SMALL)]
    else:
        S += [pending("add a screenshot of your repository as docs/screenshots/repo.png")]
    S += [P(f"Link: {ph(TEAM['links']['repo'], 'repository link')}"), P("What changed since Milestone 1:", H3)]
    ch = [l[2:] for l in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")][:5]
    S += [P("<br/>".join(f"- {escape(c)}" for c in ch)), P("Full dated list: CHANGELOG.md in the repository.", SMALL), NextPageTemplate("landscape"), PageBreak()]

    # 6 Supporting document (landscape page)
    S += [P("6. Supporting document: Business Model Canvas (BMC)", ParagraphStyle("h6", parent=H1, fontSize=12, spaceAfter=2)),
          P("The same one-page document is uploaded separately as " + escape(TEAM["team_file_name"]) + "_BMC.pdf.", SMALL)]
    S += bmc_flowables(landscape(A4)[0] - 2.4 * cm) + [NextPageTemplate("portrait"), PageBreak()]

    # 7 Team contribution
    S += [P("7. Team contribution", H1)]
    rows = [hdr("Member name", "Enrollment no.", "Role", "Tasks done in Milestone 2", "Evidence", "Contribution (%)")]
    for m in mem:
        rows.append([escape(m["name"]), m["enrollment"], escape(m["role"]), escape(m["tasks"]), escape(m["evidence"]), str(m["pct"])])
    S += [grid(rows, [2.6 * cm, 2.3 * cm, 2.4 * cm, 4.2 * cm, 3.9 * cm, full - 15.4 * cm])]
    tot = sum(m["pct"] for m in mem)
    if tot != 100:
        S += [pending(f"percentages add up to {tot}, must be 100")]
    if not TEAM.get("contribution_confirmed"):
        S += [pending("contribution table not confirmed by all members (set contribution_confirmed to true in team.json)")]
    S += [P("Every member owns at least one specific task and can explain it to the faculty.", SMALL)]
    doc.build(S)


def form_answers(m2_name, bmc_name):
    mods = [m for m in module_status() if m["status"] == "Working"]
    allw = all(m["status"] == "Working" for m in module_status())
    n_prompts = len(VERSIONS["v4"])
    L = TEAM["links"]
    ans = [
        ("1. Team ID", TEAM["team_id"]), ("2. Team name", TEAM["team_name"]), ("3. Project title", TEAM["project_title"]),
        ("4. Team leader name", mem0 := TEAM["members"][0]["name"]), ("5. Team leader enrollment no.", TEAM["members"][0]["enrollment"]),
        ("6. Group (batch)", TEAM["batch"]),
        ("7. Enrollment numbers (one per line)", "\n".join(m["enrollment"] for m in TEAM["members"])),
        ("8. Project type (max 2)", "App with code"),
        ("9. Main AI tool and model", f"{MODEL} in a custom Streamlit app (Python)" if HAS_V4 else "TO_FILL (after the test run: <provider> / <model> in a custom Streamlit app)"),
        ("10. Number of prompts", str(n_prompts) + "  (P1 and P2)"),
        ("11. Prototype link", L["prototype"]), ("12. Repository link", L["repo"]), ("13. Reel link", L["reel"]),
        ("14. Reel length (seconds, 90-150)", TEAM["reel_seconds"]),
        ("15. Supporting document type", "Business Model Canvas (BMC)"),
        ("16. Upload", f"docs/{bmc_name}"),
        ("17. Number of test inputs", str(len(TESTS))),
        ("18. Number of prompt versions", str(len(VERSIONS)) + "  (v1, v2, v3, v4/final)"),
        ("19. Prototype status", "All modules working" if allw else "Some modules working"),
        ("20. Working modules (one per line)", "\n".join(f"{i + 1}. {m['name']}" for i, m in enumerate(mods))),
        ("21. Upload Milestone 2 PDF", f"docs/{m2_name}"),
        ("22. Main task of each member", "\n".join(f"{m['enrollment']} - {m['name']} - {m['role']}: {m['tasks']}" for m in TEAM["members"])),
        ("23. Anything the evaluator should know", "The app needs no login. Pick a sample bug in the sidebar, press 'Debug my code'. "
                                                   "Tests can be re-run with: python code/run_tests.py run && python code/run_tests.py evaluate"),
        ("24. Confirmation", "Tick only after all three members have agreed to the contribution table"),
    ]
    out = ["# Form answers for Milestone 2 (copy into the Microsoft Form)", "",
           "Anything shown as TO_FILL is still missing. These answers are generated from the same data as the PDF so the numbers match.", ""]
    for q, a in ans:
        if "TO_FILL" in str(a):
            WARN.append(f"form answer {q}")
        out += [f"**{q}**", "```", str(a), "```", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    DOCS.mkdir(exist_ok=True)
    shots = sorted((DOCS / "screenshots").glob("test*.png"))
    repo_shot = DOCS / "screenshots/repo.png"
    repo_shot = repo_shot if repo_shot.exists() else None
    tid = TEAM["team_id"] if TEAM["team_id"] != "TO_FILL" else "TEAMID"
    m2 = f"M2_{tid}_{TEAM['project_short']}.pdf"
    bmc = f"{TEAM['team_file_name']}_BMC.pdf"
    build_bmc(DOCS / bmc)
    build_m2(DOCS / m2, shots, repo_shot)
    (DOCS / "FORM_ANSWERS.md").write_text(form_answers(m2, bmc), encoding="utf-8")
    items = sorted(set(WARN))
    print(f"Built docs/{m2}, docs/{bmc}, docs/FORM_ANSWERS.md")
    if items:
        print(f"\n{len(items)} item(s) still to fill:")
        for w in items:
            print("  -", w)
        if a.final:
            sys.exit("FINAL build refused: fix the items above first.")
    else:
        print("Nothing left to fill. Ready to submit.")


if __name__ == "__main__":
    main()
