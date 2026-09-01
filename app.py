import io
import re
import zipfile

import pandas as pd
import pdfplumber
from flask import Flask, render_template, request, send_file

app = Flask(__name__)

# The report has appeared in the wild in at least two distinct generations
# (different title wording, different column layout, different grouping
# style) even within 2024-2026 -- e.g. July/Aug 2024 vs Mar/Jun/Jul 2026.
# Each table maps to an ORDERED LIST of format profiles; for a given PDF we
# try each profile's marker_re in turn and use the first one that actually
# finds matching pages. If a future report doesn't match any known profile,
# extraction returns empty (fails closed) rather than guessing -- run
# debug_pdf.py against it and add a new profile below.

DATE_RE = re.compile(r"(\d{1,2}/\d{4})")

MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}
MONTH_YEAR_RE = re.compile(
    # Opening "(" is sometimes missing from a PDF's extracted text (a
    # rendering quirk, seen in December 2024's report) -- only require the
    # closing ")" so the header still matches.
    r"\(?(" + "|".join(MONTHS) + r")\s+(\d{4})\)", re.IGNORECASE
)
# Portal-format reports state the month as "...as of March 2026" (no parens).
MONTH_YEAR_ASOF_RE = re.compile(
    r"as of\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", re.IGNORECASE
)
# Legacy-format reports' cover uses a 3-letter abbreviation and a Unicode
# hyphen (U+2010, not ASCII "-") as the separator, e.g. "APR‐2024" --
# \W? tolerates that (and a plain "-" or space) without hardcoding the glyph.
MONTH_ABBR = {name[:3]: num for name, num in MONTHS.items()}
MONTH_ABBR_YEAR_RE = re.compile(
    r"\b(" + "|".join(MONTH_ABBR) + r")\W?(\d{4})", re.IGNORECASE
)


def extract_dates(cell):
    """All MM/YYYY dates found in a cell, in reading order."""
    if not cell:
        return []
    return DATE_RE.findall(cell)


def extract_numbers(cell):
    """All decimal numbers found in a cell (costs/expenditure), in reading order."""
    if not cell:
        return []
    tokens = cell.replace("(", " (").replace("{", " {").replace("[", " [").replace(",", "").split()
    nums = []
    for tok in tokens:
        bare = tok.strip("(){}[]")
        try:
            nums.append(float(bare))
        except ValueError:
            pass
    return nums


PROJECT_CODE_RE = re.compile(r"\d{4,}")
LEGACY_OCMS_CODE_RE = re.compile(r"N\d+", re.IGNORECASE)


def parse_project_cell(cell):
    """Split a "Project Name" cell into its name plus whatever trailing
    parenthetical segments follow it. Those segments hold different things
    depending on table/format: Agency always; a numeric Project Code (portal
    format only); an N-prefixed Legacy OCMS Code (both formats -- this is the
    one durable identifier across eras, since the numeric Project Code only
    exists post-portal). A trailing State segment (seen in some dated-format
    tables) is intentionally not captured here -- State is already its own
    column everywhere it matters.

    Returns {"project_name", "agency", "project_code", "legacy_ocms_code"},
    each None if `cell` is empty or that segment isn't present."""
    empty = {"project_name": None, "agency": None, "project_code": None, "legacy_ocms_code": None}
    if not cell:
        return empty

    lines = cell.split("\n")
    name_lines = []
    trailer_start = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("(") or re.match(r"^\d{5,}$", line):
            trailer_start = i
            break
        name_lines.append(line)

    agency = project_code = legacy_ocms_code = None
    for line in lines[trailer_start:]:
        token = line.strip().strip("()").strip()
        if not token:
            continue
        if LEGACY_OCMS_CODE_RE.fullmatch(token):
            legacy_ocms_code = token
        elif PROJECT_CODE_RE.fullmatch(token):
            project_code = token
        elif agency is None:
            agency = token

    return {
        "project_name": " ".join(name_lines).strip() or None,
        "agency": agency,
        "project_code": project_code,
        "legacy_ocms_code": legacy_ocms_code,
    }


def clean_label(cell):
    """State/Sector cells: collapse internal line-wraps into one string."""
    if not cell:
        return None
    return cell.replace("\n", " ").strip()


def parse_row_dated(cells, table_key, _state=None):
    """Format profile: "dated-title" reports (verified on Jul/Aug 2024) --
    table titles embed the month ("...as of 31st July 2024", "...during
    July 2024"), State/Sector are per-row columns whose ruling can vanish,
    no Ministry grouping. `_state` is unused; kept for a uniform call
    signature with the stateful portal-format parsers below.

    Returns a record dict, or None if `cells` isn't a real data row
    (header row / blank separator row / unrecognized width)."""

    if table_key == "ongoing":
        # The State/Sector columns' ruling lines vanish on pages where those
        # cells are blank for long stretches (pdfplumber's line-based table
        # extraction needs ink to find a boundary), so row width varies: 9
        # (full grid), 8 (State gone), or 7 (State+Sector both gone). Anchor
        # from the right since the last 6 fields are always present, and infer
        # how many of [state, sector, sl_no] survived from what's left.
        if len(cells) not in (7, 8, 9):
            return None
        leading, trailing = cells[:-6], cells[-6:]
        sl_no = leading[-1]
        if not re.fullmatch(r"\d+", sl_no):
            return None  # header row or blank separator row
        state = leading[0] if len(leading) == 3 else None
        sector = leading[-2] if len(leading) >= 2 else None
        project_name_raw, approval_raw, doc_raw, cost_raw, expenditure_raw, physical_raw = trailing

        record = {
            "state": clean_label(state),
            "sector": clean_label(sector),
            "sl_no": sl_no,
            **parse_project_cell(project_name_raw),
        }
        approval_dates = extract_dates(approval_raw)
        record["approval_date"] = approval_dates[0] if approval_dates else None

        # ponytail: doc_raw packs Original/(Revised)/{Anticipated} in order,
        # but a revised value sometimes prints as "Mon-YY" text (e.g. "Jul-26")
        # instead of MM/YYYY, which DATE_RE won't catch -- that can shift
        # revised/anticipated by one slot. Upgrade: match "Mon-YY" too if this
        # turns out common across the archive.
        doc_dates = extract_dates(doc_raw)
        record["original_doc"] = doc_dates[0] if doc_dates else None
        record["revised_doc"] = doc_dates[1] if len(doc_dates) > 1 else None
        record["anticipated_doc"] = doc_dates[2] if len(doc_dates) > 2 else None

        costs = extract_numbers(cost_raw)
        record["original_cost"] = costs[0] if costs else None
        record["revised_cost"] = costs[1] if len(costs) > 1 else None
        record["anticipated_cost"] = costs[2] if len(costs) > 2 else None

        expenditure = extract_numbers(expenditure_raw)
        record["expenditure"] = expenditure[0] if expenditure else None
        record["physical_progress"] = physical_raw
        return record

    if table_key == "completed":
        if len(cells) != 6 or not re.fullmatch(r"\d+", cells[1]):
            return None
        record = {
            "sector": clean_label(cells[0]),
            "sl_no": cells[1],
            **parse_project_cell(cells[2]),
        }
        costs = extract_numbers(cells[3])
        record["original_cost"] = costs[0] if costs else None
        dates = extract_dates(cells[4])
        record["commissioning_date"] = dates[0] if dates else None
        expenditure = extract_numbers(cells[5])
        record["expenditure"] = expenditure[0] if expenditure else None
        return record

    if table_key == "newly_added":
        if len(cells) != 6 or not re.fullmatch(r"\d+", cells[1]):
            return None
        record = {
            "sector": clean_label(cells[0]),
            "sl_no": cells[1],
            **parse_project_cell(cells[2]),
        }
        approval_dates = extract_dates(cells[3])
        record["approval_date"] = approval_dates[0] if approval_dates else None

        costs = extract_numbers(cells[4])
        record["original_cost"] = costs[0] if costs else None
        record["revised_cost"] = costs[1] if len(costs) > 1 else None
        record["anticipated_cost"] = costs[2] if len(costs) > 2 else None

        doc_dates = extract_dates(cells[5])
        record["target_doc"] = doc_dates[0] if doc_dates else None
        record["revised_doc"] = doc_dates[1] if len(doc_dates) > 1 else None
        record["anticipated_doc"] = doc_dates[2] if len(doc_dates) > 2 else None
        return record

    raise ValueError(f"unknown table_key {table_key!r}")


def dated_postprocess(df):
    # Sector prints once per group and blanks on the following rows (a merged
    # cell in the source table); carry the value forward. State is NOT a merge
    # group -- it's blank for most (national/multi-state) projects and only
    # rarely holds a real one-off value, so filling it would mislabel every
    # unrelated row until the next value. Leave it as extracted.
    if "sector" in df.columns:
        df["sector"] = df["sector"].replace("", pd.NA).ffill()
    return df


GROUP_HEADING_RE = re.compile(r"^(Ministry|Department) of", re.IGNORECASE)


def is_group_row(cells):
    """Portal-format grouping: a standalone row with only the label column
    filled (e.g. "Ministry of Civil Aviation", then "Aviation & Aviation
    Infrastructure") announces the Ministry/Sector for every data row until
    the next such row -- it doesn't repeat per page, so state must persist
    across the whole table. A "Total (n)" subtotal row looks the same shape
    but isn't a group heading."""
    if cells[0] or any(cells[2:]):
        return False
    label = cells[1].strip()
    return bool(label) and not label.lower().startswith("total")


def update_group_state(cells, state):
    label = clean_label(cells[1])
    if GROUP_HEADING_RE.match(label):
        state["ministry"] = label
    else:
        state["sector"] = label


def parse_row_portal_ongoing(cells, state):
    """Format profile: "portal" reports (verified on Mar/Jun/Jul 2026) --
    generated by the PAIMANA portal (ipm.mospi.gov.in). State is a real
    per-row column (not blank/merged); Ministry/Sector come from standalone
    group-heading rows tracked in `state`, not from columns."""
    if len(cells) != 8:
        return None
    if is_group_row(cells):
        update_group_state(cells, state)
        return None
    sl_no = cells[0]
    if not re.fullmatch(r"\d+", sl_no):
        return None  # header row

    approval = extract_dates(cells[3])
    doc = extract_dates(cells[4])
    cost = extract_numbers(cells[5])
    expenditure = extract_numbers(cells[6])
    return {
        "ministry": state.get("ministry"),
        "sector": state.get("sector"),
        "sl_no": sl_no,
        **parse_project_cell(cells[1]),
        "state": clean_label(cells[2]),
        "approval_date": approval[0] if approval else None,
        "start_date": approval[1] if len(approval) > 1 else None,
        "target_doc": doc[0] if doc else None,
        "revised_doc": doc[1] if len(doc) > 1 else None,
        "original_cost": cost[0] if cost else None,
        "revised_cost": cost[1] if len(cost) > 1 else None,
        "expenditure": expenditure[0] if expenditure else None,
        "physical_progress": cells[7],
    }


def parse_row_portal_completed(cells, state):
    if len(cells) != 7:
        return None
    if is_group_row(cells):
        update_group_state(cells, state)
        return None
    sl_no = cells[0]
    if not re.fullmatch(r"\d+", sl_no):
        return None

    approval = extract_dates(cells[3])
    # ponytail: this cell is Actual/(Target)/(Revised) DoC, but the actual
    # date is often literal "NA" (not yet completed) instead of a real date,
    # which extract_dates() silently skips -- shifting target/revised left by
    # one slot. Upgrade: detect "NA" as an explicit placeholder token instead
    # of relying on positional counting, if this proves common.
    completion = extract_dates(cells[4])
    cost = extract_numbers(cells[5])
    expenditure = extract_numbers(cells[6])
    return {
        "ministry": state.get("ministry"),
        "sector": state.get("sector"),
        "sl_no": sl_no,
        **parse_project_cell(cells[1]),
        "state": clean_label(cells[2]),
        "approval_date": approval[0] if approval else None,
        "start_date": approval[1] if len(approval) > 1 else None,
        "actual_completion": completion[0] if completion else None,
        "target_doc": completion[1] if len(completion) > 1 else None,
        "revised_doc": completion[2] if len(completion) > 2 else None,
        "original_cost": cost[0] if cost else None,
        "revised_cost": cost[1] if len(cost) > 1 else None,
        "expenditure": expenditure[0] if expenditure else None,
    }


def parse_row_portal_newly_added(cells, state):
    if len(cells) != 6:
        return None
    if is_group_row(cells):
        update_group_state(cells, state)
        return None
    sl_no = cells[0]
    if not re.fullmatch(r"\d+", sl_no):
        return None

    approval = extract_dates(cells[3])
    doc = extract_dates(cells[4])
    cost = extract_numbers(cells[5])
    return {
        "ministry": state.get("ministry"),
        "sector": state.get("sector"),
        "sl_no": sl_no,
        **parse_project_cell(cells[1]),
        "state": clean_label(cells[2]),
        "approval_date": approval[0] if approval else None,
        "start_date": approval[1] if len(approval) > 1 else None,
        "target_doc": doc[0] if doc else None,
        "revised_doc": doc[1] if len(doc) > 1 else None,
        "original_cost": cost[0] if cost else None,
        "revised_cost": cost[1] if len(cost) > 1 else None,
    }


MONTH_COMMA_YEAR_RE = re.compile(r"^[A-Za-z]+,\s*\d{4}$")
LEGACY_AGENCY_CODE_RE = re.compile(r"\(([^()]+)\)\s*-\s*\[([^\]]+)\]\s*$", re.DOTALL)


def parse_project_cell_legacy(cell):
    """Legacy-format project cells pack Agency+Code onto the cell's tail as
    "(Agency) - [Code]" on one line, rather than one segment per line like
    the other two formats (see parse_project_cell). A stray label sometimes
    glues onto the agency's opening paren with no space -- a source-PDF
    text-wrap artifact (e.g. "...Central Sector Projects(AGENCY)...") -- left
    in the name as-is rather than denylisting known stray phrases."""
    empty = {"project_name": None, "agency": None, "project_code": None, "legacy_ocms_code": None}
    if not cell:
        return empty
    joined = " ".join(line.strip() for line in cell.split("\n") if line.strip())
    m = LEGACY_AGENCY_CODE_RE.search(joined)
    if not m:
        return {**empty, "project_name": joined or None}
    code = m.group(2).strip()
    return {
        "project_name": joined[: m.start()].strip() or None,
        "agency": m.group(1).strip() or None,
        "project_code": code if PROJECT_CODE_RE.fullmatch(code) else None,
        "legacy_ocms_code": code if LEGACY_OCMS_CODE_RE.fullmatch(code) else None,
    }


def parse_row_legacy_ongoing(cells, state):
    """Format profile: "legacy OCMS" reports (verified on Apr/May 2024) --
    a whole-FISCAL-YEAR cumulative report, not a monthly snapshot, generated
    by the pre-portal OCMS system. Its title does NOT repeat per page (see
    extract_table's `continues_to_end`), and it already carries MoSPI's own
    Cost/Time overrun figures in the last column -- useful as ground truth
    or a cross-check for whatever overrun labels get derived from the panel."""
    if len(cells) != 6:
        return None
    if is_group_row(cells):
        label = clean_label(cells[1])
        # State is printed ALL CAPS, Sector in Title Case -- the one
        # reliable distinguishing signal here (no "Ministry of" prefix
        # style like the portal format).
        if label.isupper():
            state["state"] = label
        else:
            state["sector"] = label
        return None
    sl_no = cells[0]
    if not re.fullmatch(r"\d+", sl_no):
        return None  # header row

    approval = extract_dates(cells[2])
    # ponytail: doc/cost/expenditure cells use a literal "-" placeholder for
    # a missing Revised value (unlike other formats, which just omit it), so
    # extract_dates/extract_numbers silently skip it -- shifting Anticipated
    # into the Revised slot whenever Revised is "-". Upgrade: detect literal
    # "-" tokens explicitly instead of relying on positional counting.
    doc = extract_dates(cells[3])
    cost = extract_numbers(cells[4])
    # This column packs three DIFFERENT metrics, not original/revised/
    # anticipated: plain = Cumulative Expenditure, (paren) = Cost Overrun in
    # Rs crore, [bracket] = Time Overrun in months.
    overrun = extract_numbers(cells[5])
    return {
        "state": state.get("state"),
        "sector": state.get("sector"),
        "sl_no": sl_no,
        **parse_project_cell_legacy(cells[1]),
        "approval_date": approval[0] if approval else None,
        "target_doc": doc[0] if doc else None,
        "revised_doc": doc[1] if len(doc) > 1 else None,
        "anticipated_doc": doc[2] if len(doc) > 2 else None,
        "original_cost": cost[0] if cost else None,
        "revised_cost": cost[1] if len(cost) > 1 else None,
        "anticipated_cost": cost[2] if len(cost) > 2 else None,
        "expenditure": overrun[0] if overrun else None,
        "cost_overrun": overrun[1] if len(overrun) > 1 else None,
        "time_overrun_months": overrun[2] if len(overrun) > 2 else None,
    }


def parse_row_legacy_completed(cells, state):
    """Table-2: "Month wise List of Completed Projects" -- one table
    accumulates the WHOLE fiscal year, broken into per-calendar-month
    sections (e.g. a standalone "April,2024" row) inside it. That sub-header
    is the true completion month for the rows under it -- more precise than
    the report's own filename/cover month."""
    if len(cells) != 5:
        return None
    if is_group_row(cells):
        label = clean_label(cells[1])
        if MONTH_COMMA_YEAR_RE.match(label):
            state["completion_month"] = label
        else:
            state["sector"] = label
        return None
    sl_no = cells[0]
    if not re.fullmatch(r"\d+", sl_no):
        return None

    cost = extract_numbers(cells[2])
    dates = extract_dates(cells[3])
    expenditure = extract_numbers(cells[4])
    return {
        "sector": state.get("sector"),
        "completion_month": state.get("completion_month"),
        "sl_no": sl_no,
        **parse_project_cell_legacy(cells[1]),
        "original_cost": cost[0] if cost else None,
        "commissioning_date": dates[0] if dates else None,
        "expenditure": expenditure[0] if expenditure else None,
    }


def parse_row_legacy_added(cells, state):
    """Table-14: "List of projects added" -- unlike Table-2, this one is
    single-month only (no per-month sub-sections). No Agency/Code trailer is
    printed in this table's Project cell at all, so those fields stay None."""
    if len(cells) != 7:
        return None
    if is_group_row(cells):
        state["sector"] = clean_label(cells[1])
        return None
    sl_no = cells[0]
    if not re.fullmatch(r"\d+", sl_no):
        return None

    doa = extract_dates(cells[2])
    original_cost = extract_numbers(cells[3])
    original_doc = extract_dates(cells[4])
    anticipated_cost = extract_numbers(cells[5])
    anticipated_doc = extract_dates(cells[6])
    name = " ".join(line.strip() for line in cells[1].split("\n") if line.strip())
    return {
        "sector": state.get("sector"),
        "sl_no": sl_no,
        "project_name": name or None,
        "approval_date": doa[0] if doa else None,
        "original_cost": original_cost[0] if original_cost else None,
        "target_doc": original_doc[0] if original_doc else None,
        "anticipated_cost": anticipated_cost[0] if anticipated_cost else None,
        "anticipated_doc": anticipated_doc[0] if anticipated_doc else None,
    }


# Ordered per table: tried in order, first profile whose marker_re finds any
# matching page in the PDF wins. "as of"/"during" phrasing only appears in
# the dated-2024 titles, "All Ongoing Projects"/"Newly Added Projects" only
# in the portal-2026 titles, and "On-going" (hyphenated)/"Month wise
# List"/"List of projects added" only in the legacy-OCMS titles, so there's
# no cross-format collision risk.
TABLE_FORMATS = {
    "ongoing": [
        {
            "marker_re": re.compile(r"Ongoing Projects as of"),
            "parse_row": lambda cells, state: parse_row_dated(cells, "ongoing"),
            "postprocess": dated_postprocess,
        },
        {
            "marker_re": re.compile(r"All Ongoing Projects"),
            "parse_row": parse_row_portal_ongoing,
            "postprocess": None,
        },
        {
            # Hyphenated -- distinguishes the real ongoing-projects annexure
            # from "...Ongoing Projects having Cost/Time Overruns..." and
            # "...Ongoing Projects Under -Public Private Partnership Mode"
            # annexures, which also contain "Ongoing Projects" as a substring
            # -- the real title always sits alone on its own line, the others
            # continue with a qualifier on the same line, so requiring a
            # newline (or end of text) right after "Projects" disambiguates.
            # Hyphenation ("On-going" vs "Ongoing") also varies by edition.
            "marker_re": re.compile(r"Details of On-?going Projects\s*(?:\n|$)"),
            "parse_row": parse_row_legacy_ongoing,
            "postprocess": None,
            "continues_to_end": True,
        },
    ],
    "completed": [
        {
            "marker_re": re.compile(r"Project List:\s*Completed during"),
            "parse_row": lambda cells, state: parse_row_dated(cells, "completed"),
            "postprocess": None,
        },
        {
            "marker_re": re.compile(r"Completed Projects"),
            "parse_row": parse_row_portal_completed,
            "postprocess": None,
        },
        {
            # This report duplicates every table at two cost thresholds
            # (Rs.150cr and Rs.1000cr) under near-identical titles -- require
            # "150" so we don't also scrape the Rs.1000cr duplicate table.
            "marker_re": re.compile(r"Month wise List of Completed Projects Costing Rs\.?\s*150"),
            "parse_row": parse_row_legacy_completed,
            "postprocess": None,
        },
    ],
    "newly_added": [
        {
            "marker_re": re.compile(r"Project List:\s*Added during"),
            "parse_row": lambda cells, state: parse_row_dated(cells, "newly_added"),
            "postprocess": None,
        },
        {
            "marker_re": re.compile(r"Newly Added Projects"),
            "parse_row": parse_row_portal_newly_added,
            "postprocess": None,
        },
        {
            # Same Rs.150cr/Rs.1000cr duplicate-table risk as above.
            "marker_re": re.compile(r"List of projects added Rs\.?\s*150"),
            "parse_row": parse_row_legacy_added,
            "postprocess": None,
        },
    ],
}


def extract_table(pdf, table_key):
    settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

    for profile in TABLE_FORMATS[table_key]:
        if profile.get("continues_to_end"):
            # This format's table title only prints on its first page (no
            # repeat per page like the other two formats), so collect every
            # page from the first match to the end of the document instead
            # of filtering by marker on each page.
            start = next(
                (i for i, p in enumerate(pdf.pages) if profile["marker_re"].search(p.extract_text() or "")),
                None,
            )
            pages = pdf.pages[start:] if start is not None else []
        else:
            pages = [p for p in pdf.pages if profile["marker_re"].search(p.extract_text() or "")]
        if not pages:
            continue  # this format's title doesn't appear in this PDF at all

        state = {}
        rows = []
        for page in pages:
            raw_table = page.extract_table(settings)
            if not raw_table:
                continue
            for row in raw_table:
                cells = [(c or "").strip() for c in row]
                record = profile["parse_row"](cells, state)
                if record is not None:
                    rows.append(record)

        df = pd.DataFrame(rows)
        if df.empty:
            continue  # title matched but nothing parsed -- try the next format
        if profile["postprocess"]:
            df = profile["postprocess"](df)
        return df

    return pd.DataFrame()


def report_month_from_pdf(pdf, filename):
    for page in pdf.pages[:3]:
        text = page.extract_text() or ""
        m = MONTH_YEAR_RE.search(text) or MONTH_YEAR_ASOF_RE.search(text)
        if m:
            return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
        m = MONTH_ABBR_YEAR_RE.search(text)
        if m:
            return f"{m.group(2)}-{MONTH_ABBR[m.group(1).lower()]:02d}"

    lower = filename.lower()
    year_match = re.search(r"20\d{2}", filename)
    if year_match:
        for name, num in MONTHS.items():
            if name in lower:
                return f"{year_match.group(0)}-{num:02d}"
    return filename


def process_uploads(files):
    """files: list of (filename, file-like). Returns {table_key: DataFrame}."""
    combined = {key: [] for key in TABLE_FORMATS}
    for filename, filelike in files:
        with pdfplumber.open(filelike) as pdf:
            report_month = report_month_from_pdf(pdf, filename)
            for key in TABLE_FORMATS:
                df = extract_table(pdf, key)
                if not df.empty:
                    df["report_month"] = report_month
                    df["source_file"] = filename
                    combined[key].append(df)
    return {
        key: (pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame())
        for key, dfs in combined.items()
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/extract", methods=["POST"])
def extract():
    uploaded = request.files.getlist("pdfs")
    if not uploaded:
        return "No files uploaded", 400

    files = [(f.filename, f.stream) for f in uploaded]
    results = process_uploads(files)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, df in results.items():
            zf.writestr(f"{key}.csv", df.to_csv(index=False))
    buf.seek(0)

    first_stem = re.sub(r"\.pdf$", "", uploaded[0].filename, flags=re.IGNORECASE)
    first_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", first_stem).strip("_") or "report"
    suffix = f"_and_{len(uploaded) - 1}_more" if len(uploaded) > 1 else ""
    zip_name = f"{first_stem}{suffix}_extracted.zip"

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )


def _selfcheck():
    assert extract_dates("03/2026\n(01/2024)") == ["03/2026", "01/2024"]
    assert extract_numbers("265.91\n(240.00)\n{270.00}") == [265.91, 240.00, 270.00]
    # dated-format: (Agency)(Legacy OCMS code) -- no numeric project_code
    cell = parse_project_cell("Bridge Project\n(NHAI)\n(N04000073)")
    assert cell["project_name"] == "Bridge Project"
    assert cell["agency"] == "NHAI"
    assert cell["legacy_ocms_code"] == "N04000073"
    assert cell["project_code"] is None

    # dated-format completed/newly_added: trailing (State) is ignored, not misread as agency
    cell = parse_project_cell("Scheme XVII\n(PGCIL)\n(N18000244)\n(MULTI STATE)")
    assert cell["agency"] == "PGCIL" and cell["legacy_ocms_code"] == "N18000244"

    # portal-format: (Agency)(numeric Project Code)(Legacy OCMS code)
    cell = parse_project_cell("Terminal Building\n(Airport Authority of India [AAI])\n(612786)\n(N04000106)")
    assert cell["agency"] == "Airport Authority of India [AAI]"
    assert cell["project_code"] == "612786"
    assert cell["legacy_ocms_code"] == "N04000106"

    # portal-format completed table: bare numeric code, no parens
    cell = parse_project_cell("Uncovered Villages Scheme\n(Department of Telecommunications [DoT])\n701600")
    assert cell["agency"] == "Department of Telecommunications [DoT]"
    assert cell["project_code"] == "701600"

    # --- dated-2024 format ---

    # Full 9-col row (State + Sector ruling both present)
    row = parse_row_dated(
        ["MAHARASHTRA", "RAILWAYS", "1", "Bridge\n(NHAI)", "01/2020",
         "03/2026\n(01/2024)\n{02/2025}", "265.91\n(240.00)\n{250.00}",
         "100.00", "80"],
        "ongoing",
    )
    assert row["project_name"] == "Bridge"
    assert row["state"] == "MAHARASHTRA"
    assert row["revised_doc"] == "01/2024"
    assert row["anticipated_cost"] == 250.00

    # 8-col row (State ruling gone, Sector survives)
    row = parse_row_dated(
        ["RAILWAYS", "2", "Dam\n(NHPC)", "03/2019", "03/2026\n{02/2025}",
         "265.91\n{250.00}", "100.00", "80"],
        "ongoing",
    )
    assert row["state"] is None and row["sector"] == "RAILWAYS" and row["sl_no"] == "2"

    # 7-col row (both State and Sector ruling gone)
    row = parse_row_dated(
        ["3", "Dam\n(NHPC)", "03/2019", "03/2026", "265.91", "100.00", "80"],
        "ongoing",
    )
    assert row["state"] is None and row["sector"] is None and row["sl_no"] == "3"

    assert parse_row_dated(["State", "Sector", "Sl No", "", "", "", "", "", ""], "ongoing") is None

    row = parse_row_dated(
        ["POWER", "2", "Dam\n(NHPC)\n(N123)", "150.00", "06/2019", "90.00"],
        "completed",
    )
    assert row["sl_no"] == "2" and row["commissioning_date"] == "06/2019"

    # --- portal-2026 format ---

    state = {}
    assert parse_row_portal_ongoing(
        ["", "Ministry of Civil Aviation", "", "", "", "", "", ""], state
    ) is None
    assert state["ministry"] == "Ministry of Civil Aviation"
    assert parse_row_portal_ongoing(
        ["", "Aviation & Aviation Infrastructure", "", "", "", "", "", ""], state
    ) is None
    assert state["sector"] == "Aviation & Aviation Infrastructure"
    row = parse_row_portal_ongoing(
        ["1", "Bridge\n(NHAI)\n(612786)", "Andhra Pradesh", "03/2023\n(01/2024)",
         "01/2026\n(05/2026)", "265.91\n(265.91)", "120.19", "60"],
        state,
    )
    assert row["ministry"] == "Ministry of Civil Aviation"
    assert row["sector"] == "Aviation & Aviation Infrastructure"
    assert row["state"] == "Andhra Pradesh"
    assert row["start_date"] == "01/2024" and row["revised_doc"] == "05/2026"
    # "Total (n)" subtotal rows look like group rows but must be ignored
    assert not is_group_row(["", "Total (1)", "", "336.89", "246.04", "", ""])

    # --- legacy-OCMS format ---

    cell = parse_project_cell_legacy(
        "NORTH TISRA AND SOUTH TISRA EXPANSION OCP (6MTY)\n(BHARAT COKING COAL LIMITED) - [N06000106]"
    )
    assert cell["project_name"] == "NORTH TISRA AND SOUTH TISRA EXPANSION OCP (6MTY)"
    assert cell["agency"] == "BHARAT COKING COAL LIMITED"
    assert cell["legacy_ocms_code"] == "N06000106"
    # stray text glued onto the agency's opening paren (a source-PDF wrap artifact) stays in the name
    cell = parse_project_cell_legacy(
        "JAYANT EXPANSION\nCentral Sector Projects(NORTHERN COAL FIELDS LIMITED) -\n[N06000159]"
    )
    assert cell["agency"] == "NORTHERN COAL FIELDS LIMITED" and cell["legacy_ocms_code"] == "N06000159"
    assert "Central Sector Projects" in cell["project_name"]
    # bare numeric code (no N prefix) classifies as project_code, not legacy_ocms_code
    cell = parse_project_cell_legacy("BRIDGE WORK\n(SOUTH CENTRAL RAILWAY) - [220100205]")
    assert cell["project_code"] == "220100205" and cell["legacy_ocms_code"] is None

    state = {}
    assert parse_row_legacy_ongoing(["", "ANDAMAN AND NICOBAR ISLANDS", "", "", "", ""], state) is None
    assert state["state"] == "ANDAMAN AND NICOBAR ISLANDS"
    assert parse_row_legacy_ongoing(["", "Civil Aviation", "", "", "", ""], state) is None
    assert state["sector"] == "Civil Aviation"
    row = parse_row_legacy_ongoing(
        ["1", "Terminal\n(AAI) - [N04000073]", "10/2013",
         "9/2018\n(5/2023)\n[6/2023]", "417.23\n(707.73)\n[707.73]", "697.52\n(290.50)\n[12]"],
        state,
    )
    assert row["state"] == "ANDAMAN AND NICOBAR ISLANDS" and row["sector"] == "Civil Aviation"
    assert row["agency"] == "AAI" and row["legacy_ocms_code"] == "N04000073"
    assert row["revised_doc"] == "5/2023" and row["anticipated_cost"] == 707.73
    assert row["cost_overrun"] == 290.50 and row["time_overrun_months"] == 12.0

    state = {}
    assert parse_row_legacy_completed(["", "April,2024", "", "", ""], state) is None
    assert state["completion_month"] == "April,2024"
    assert parse_row_legacy_completed(["", "COAL", "", "", ""], state) is None
    assert state["sector"] == "COAL"
    row = parse_row_legacy_completed(
        ["1", "Mine\n(BCCL) - [N06000106]", "555.52", "03/2021", "291.95"], state
    )
    assert row["sector"] == "COAL" and row["completion_month"] == "April,2024"
    assert row["original_cost"] == 555.52 and row["commissioning_date"] == "03/2021"

    state = {}
    assert parse_row_legacy_added(["", "CIVIL AVIATION", "", "", "", "", ""], state) is None
    row = parse_row_legacy_added(
        ["1", "Airport Strip Widening", "11/2023", "323.26", "6/2026", "323.26", "6/2026"], state
    )
    assert row["sector"] == "CIVIL AVIATION" and row["project_name"] == "Airport Strip Widening"
    assert row["original_cost"] == 323.26 and row["anticipated_doc"] == "6/2026"

    print("selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
    app.run(debug=True)
