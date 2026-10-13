import re
import io
from urllib.parse import urljoin, urlparse, quote_plus

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Karnataka College Finder",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================
# CSS DESIGN - FIXED TEXT COLORS
# =====================================================

st.markdown("""
<style>

/* Main page background */
.stApp {
    background: linear-gradient(135deg, #f5f7fb, #e8eef5);
    color: #111827 !important;
}

/* Main page headings */
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {
    color: #111827 !important;
}

/* Normal text */
.stApp p,
.stApp label,
.stApp li,
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stCaptionContainer"] {
    color: #111827 !important;
}

/* Header banner */
.stApp .hero {
    padding: 28px;
    border-radius: 18px;
    background: linear-gradient(120deg, #10243a, #245b78);
    margin-bottom: 24px;
}

.stApp .hero h1 {
    color: #ffffff !important;
    margin: 0;
    font-size: 2.2rem;
}

.stApp .hero p {
    color: #ffffff !important;
    margin-top: 10px;
    font-size: 1rem;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: #111827 !important;
}

/* Sidebar text input */
section[data-testid="stSidebar"] input {
    background-color: #ffffff !important;
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
    border: 1px solid #cbd5e1 !important;
}

/* Sidebar dropdown */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
}

section[data-testid="stSidebar"] [data-baseweb="select"] *,
section[data-testid="stSidebar"] [data-baseweb="select"] input {
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
}

/* Dropdown options */
div[data-baseweb="popover"],
div[data-baseweb="menu"],
div[role="listbox"],
div[role="option"] {
    background-color: #ffffff !important;
    color: #111827 !important;
}

div[role="option"] *,
div[role="listbox"] * {
    color: #111827 !important;
}

/* Main-page text inputs */
.stTextInput input,
.stTextArea textarea {
    background-color: #ffffff !important;
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
    border: 1px solid #cbd5e1 !important;
}

/* All standard buttons */
.stButton > button {
    background-color: #ffffff !important;
    color: #111827 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 10px !important;
    min-height: 2.8rem;
    font-weight: 600 !important;
}

/* Force button labels to be visible */
.stButton > button p,
.stButton > button span,
.stButton > button div {
    color: #111827 !important;
    -webkit-text-fill-color: #111827 !important;
}

/* Button hover */
.stButton > button:hover {
    background-color: #dbeafe !important;
    border-color: #2563eb !important;
}

/* Primary fetch button */
.stButton > button[kind="primary"] {
    background-color: #174ea6 !important;
    border-color: #174ea6 !important;
}

.stButton > button[kind="primary"] *,
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span,
.stButton > button[kind="primary"] div {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Website and Google Maps link buttons */
.stLinkButton a {
    background-color: #174ea6 !important;
    color: #ffffff !important;
    border: 1px solid #174ea6 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}

.stLinkButton a *,
.stLinkButton a span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Download button */
.stDownloadButton > button {
    background-color: #174ea6 !important;
    color: #ffffff !important;
    border: 1px solid #174ea6 !important;
    border-radius: 10px !important;
}

.stDownloadButton > button *,
.stDownloadButton > button span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background-color: #ffffff !important;
    padding: 16px;
    border-radius: 14px;
    border: 1px solid #d7e0ea;
}

div[data-testid="stMetric"] label,
div[data-testid="stMetric"] label *,
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] * {
    color: #111827 !important;
}

/* Data table */
div[data-testid="stDataFrame"] {
    background-color: #ffffff !important;
}

/* Regular links */
.stApp a {
    color: #0969da !important;
}

/* Alerts */
div[data-testid="stAlert"] p {
    color: #111827 !important;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# HEADER
# =====================================================

st.markdown("""
<div class="hero">
    <h1>🎓 Karnataka College Finder</h1>
    <p>
        Discover engineering colleges, departments, intake,
        establishment year, placements and hiring companies.
    </p>
</div>
""", unsafe_allow_html=True)


# =====================================================
# SETTINGS
# =====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
    )
}

TIMEOUT = 12
MAX_PAGES = 8
MAX_PDF_BYTES = 12 * 1024 * 1024


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def normalize(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).lower().strip()
    )


def find_column(df, aliases):
    columns = {
        normalize(col): col
        for col in df.columns
    }

    for alias in aliases:
        if normalize(alias) in columns:
            return columns[normalize(alias)]

    for col in df.columns:
        for alias in aliases:
            if normalize(alias) in normalize(col):
                return col

    return None


def cell(row, column):
    if not column:
        return ""

    value = row.get(column, "")

    if pd.isna(value):
        return ""

    return str(value).strip()


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def valid_url(url):
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
            and "." in parsed.netloc
        )
    except Exception:
        return False


# =====================================================
# GOOGLE MAPS - CORRECT LINK HANDLING
# =====================================================

def google_maps_url(college_name, address=""):
    """
    Generate a real Google Maps search URL.
    """

    query = clean_text(
        f"{college_name} {address}"
    )

    return (
        "https://www.google.com/maps/search/?api=1&query="
        + quote_plus(query)
    )


def is_google_maps_url(url):
    if not valid_url(url):
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    return (
        domain.endswith("google.com")
        or domain.endswith("google.co.in")
        or domain == "maps.app.goo.gl"
        or domain == "goo.gl"
    ) and (
        "maps" in url.lower()
        or domain in ("maps.app.goo.gl", "goo.gl")
    )


def get_maps_url(row, maps_col, college_name, address):
    """
    Use the Excel link only if it is a real Google Maps URL.
    Ignore placeholder text such as 'Open in Google Maps'.
    """

    excel_url = cell(row, maps_col)

    if is_google_maps_url(excel_url):
        return excel_url

    return google_maps_url(
        college_name,
        address
    )


# =====================================================
# WEBSITE READER
# =====================================================

def safe_get(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        return response

    except requests.RequestException:
        return None


def same_domain(base_url, link):
    try:
        base = (
            urlparse(base_url)
            .netloc.lower()
            .replace("www.", "")
        )

        target = (
            urlparse(link)
            .netloc.lower()
            .replace("www.", "")
        )

        return base == target

    except Exception:
        return False


def fetch_page_text(url):
    response = safe_get(url)

    if response is None:
        return None, "", []

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    # PDF extraction
    if "pdf" in content_type or url.lower().endswith(".pdf"):

        if pdfplumber is None:
            return (
                response.url,
                "PDF found. Install pdfplumber to read it.",
                []
            )

        if len(response.content) > MAX_PDF_BYTES:
            return (
                response.url,
                "PDF exceeds the 12 MB limit.",
                []
            )

        try:
            page_texts = []

            with pdfplumber.open(
                io.BytesIO(response.content)
            ) as pdf:

                for page in pdf.pages[:35]:
                    page_texts.append(
                        page.extract_text() or ""
                    )

            return (
                response.url,
                clean_text(" ".join(page_texts)),
                []
            )

        except Exception:
            return response.url, "", []

    # HTML extraction
    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    links = []

    for anchor in soup.find_all("a", href=True):

        link = urljoin(
            response.url,
            anchor["href"].strip()
        )

        label = clean_text(
            anchor.get_text(" ", strip=True)
        )

        if valid_url(link):
            links.append((label, link))

    for tag in soup([
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "noscript",
        "svg"
    ]):
        tag.decompose()

    page_text = clean_text(
        soup.get_text(" ", strip=True)
    )

    return response.url, page_text, links


# =====================================================
# INFORMATION TOPICS
# =====================================================

TOPIC_KEYWORDS = {
    "About Us": [
        "about", "history", "profile",
        "vision", "mission", "inception"
    ],

    "Departments": [
        "department", "academics", "courses",
        "programmes", "programs", "branch"
    ],

    "Intake": [
        "intake", "admission", "admissions",
        "seat", "sanctioned", "approved intake"
    ],

    "University Type": [
        "autonomous", "affiliation", "affiliated",
        "university", "vtu", "accreditation"
    ],

    "Establishment Year": [
        "about", "history", "established",
        "inception", "milestone", "founded"
    ],

    "Placement Overview": [
        "placement", "training", "career",
        "recruiter", "placement statistics",
        "placement report", "annual report"
    ],

    "Hiring Companies": [
        "placement", "recruiter", "company",
        "companies", "career", "training"
    ]
}


RESULT_KEYWORDS = {
    "About Us": [
        "about", "history", "established",
        "founded", "mission", "vision",
        "college", "institute"
    ],

    "Departments": [
        "department", "computer science",
        "information science", "mechanical",
        "civil", "electrical", "electronics",
        "artificial intelligence", "data science"
    ],

    "Intake": [
        "intake", "sanctioned", "seats",
        "admission", "approved", "students"
    ],

    "University Type": [
        "autonomous", "affiliated", "affiliation",
        "university", "vtu", "visvesvaraya", "deemed"
    ],

    "Establishment Year": [
        "established", "establishment", "founded",
        "inception", "since", "started in"
    ],

    "Placement Overview": [
        "placement", "placed", "package",
        "salary", "highest", "average",
        "students", "recruitment"
    ],

    "Hiring Companies": [
        "recruiter", "recruiters", "company",
        "companies", "hiring", "infosys",
        "wipro", "accenture", "tcs"
    ]
}


# =====================================================
# WEBSITE CRAWLER
# =====================================================

def score_link(label, url, keywords):
    combined = (
        label + " " + url
    ).lower().replace("-", " ").replace("_", " ")

    return sum(
        1 for keyword in keywords
        if keyword.lower() in combined
    )


def scrape_college_site(website, topic):
    if not valid_url(website):
        return [], ["Invalid official website URL."]

    visited = set()
    queue = [
        (website, "Official website homepage")
    ]

    pages = []
    warnings = []

    keywords = TOPIC_KEYWORDS.get(topic, [])

    while queue and len(visited) < MAX_PAGES:

        url, reason = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        final_url, text, links = fetch_page_text(url)

        if text:
            pages.append({
                "url": final_url or url,
                "reason": reason,
                "text": text
            })
        else:
            warnings.append(
                f"Could not read: {url}"
            )

        candidates = []

        for label, link in links:

            if link in visited:
                continue

            if not same_domain(website, link):
                continue

            score = score_link(
                label,
                link,
                keywords
            )

            if score > 0:
                candidates.append(
                    (score, label, link)
                )

        candidates.sort(reverse=True)

        for score, label, link in candidates:

            if link in visited:
                continue

            if not any(
                item[0] == link
                for item in queue
            ):
                queue.append((
                    link,
                    f"Relevant page: {label or link}"
                ))

        queue.sort(
            key=lambda item: score_link(
                item[1],
                item[0],
                keywords
            ),
            reverse=True
        )

    return pages, warnings


# =====================================================
# EXTRACT RELEVANT SENTENCES
# =====================================================

def extract_snippets(pages, keywords, limit=8):
    results = []

    for page in pages:

        sentences = re.split(
            r"(?<=[.!?])\s+",
            page["text"]
        )

        matched = []

        for sentence in sentences:

            sentence = clean_text(sentence)

            if len(sentence) < 20:
                continue

            if any(
                keyword.lower() in sentence.lower()
                for keyword in keywords
            ):

                if sentence not in matched:
                    matched.append(sentence)

        if matched:
            results.append((
                page["url"],
                matched[:limit]
            ))

    return results


def render_results(pages, topic):
    snippets = extract_snippets(
        pages,
        RESULT_KEYWORDS.get(topic, [])
    )

    if not snippets:
        st.info(
            "No matching information was detected automatically. "
            "Open the source pages to check manually."
        )

    for url, sentences in snippets:

        with st.container(border=True):

            st.markdown(
                f"**Source:** [{url}]({url})"
            )

            for sentence in sentences:
                st.write("• " + sentence[:800])


# =====================================================
# EXCEL UPLOAD
# =====================================================

uploaded_file = st.file_uploader(
    "📂 Upload your engineering colleges Excel file",
    type=["xlsx", "xls"]
)

if uploaded_file is None:

    st.info(
        "Upload your Excel workbook to begin."
    )

    st.markdown("""
    ### How to use this application

    1. Upload your Excel workbook.
    2. Filter colleges by district.
    3. Search and select a college.
    4. Open its official website or Google Maps.
    5. Fetch information about departments, intake,
       establishment year, placements and recruiters.
    """)

    st.stop()


# =====================================================
# READ EXCEL
# =====================================================

try:
    excel = pd.ExcelFile(uploaded_file)

    sheet_name = (
        "Engineering Colleges"
        if "Engineering Colleges" in excel.sheet_names
        else excel.sheet_names[0]
    )

    df = pd.read_excel(
        uploaded_file,
        sheet_name=sheet_name
    )

    df = df.dropna(how="all").copy()

except Exception as error:
    st.error(
        f"Could not read the Excel file: {error}"
    )
    st.stop()


# =====================================================
# DETECT EXCEL COLUMNS
# =====================================================

district_col = find_column(
    df, ["District"]
)

name_col = find_column(
    df,
    [
        "College Name",
        "Institution Name",
        "Name of College",
        "College"
    ]
)

website_col = find_column(
    df,
    [
        "Official Website URL",
        "Official Website",
        "Website URL",
        "Website"
    ]
)

address_col = find_column(
    df,
    [
        "Exact Location / Address",
        "Address",
        "Location"
    ]
)

maps_col = find_column(
    df,
    [
        "Google Maps Link",
        "Maps Link",
        "Google Maps"
    ]
)

taluk_col = find_column(
    df,
    [
        "Taluk / Location",
        "Taluk"
    ]
)

wiki_col = find_column(
    df,
    [
        "Wikipedia URL / Search",
        "Wikipedia URL",
        "Wikipedia"
    ]
)

email_col = find_column(
    df,
    [
        "Principal Email",
        "Email",
        "Contact Email"
    ]
)

phone_col = find_column(
    df,
    [
        "Principal Phone",
        "Phone",
        "Contact Phone"
    ]
)

if not name_col:
    st.error(
        "Could not find a College Name column in your workbook."
    )

    st.write("Available columns:", list(df.columns))
    st.stop()

df[name_col] = (
    df[name_col]
    .fillna("")
    .astype(str)
    .str.strip()
)

df = df[df[name_col] != ""]

if df.empty:
    st.error("No college records were found.")
    st.stop()


# =====================================================
# SIDEBAR FILTERS
# =====================================================

districts = (
    sorted(
        df[district_col]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    if district_col else []
)

with st.sidebar:

    st.header("🔎 Find a College")

    selected_district = st.selectbox(
        "Select District",
        ["All districts"] + districts
    )

    if (
        selected_district != "All districts"
        and district_col
    ):

        filtered_df = df[
            df[district_col].astype(str)
            == selected_district
        ]

    else:
        filtered_df = df

    search_text = st.text_input(
        "Search college name"
    )

    if search_text:

        filtered_df = filtered_df[
            filtered_df[name_col].str.contains(
                search_text,
                case=False,
                na=False
            )
        ]

    college_options = filtered_df[name_col].tolist()

    if not college_options:
        st.warning("No colleges match your filters.")
        st.stop()

    selected_college = st.selectbox(
        "Choose College",
        college_options
    )

    st.divider()

    st.caption(
        f"Excel sheet: {sheet_name}"
    )


# =====================================================
# SELECTED COLLEGE INFORMATION
# =====================================================

row = df[
    df[name_col] == selected_college
].iloc[0]

district = cell(row, district_col) or "Not listed"
address = cell(row, address_col)
taluk = cell(row, taluk_col)
website = cell(row, website_col)
email = cell(row, email_col)
phone = cell(row, phone_col)
wiki_url = cell(row, wiki_col)

# FIXED MAPS URL: Never use placeholder text as a URL.
maps_url = get_maps_url(
    row,
    maps_col,
    selected_college,
    address
)


# =====================================================
# COLLEGE TITLE
# =====================================================

st.subheader(
    f"🎓 {selected_college}"
)

st.caption(
    " • ".join(
        value for value in [district, taluk]
        if value
    )
)


# =====================================================
# DASHBOARD METRICS
# =====================================================

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "Colleges in workbook",
    len(df)
)

metric2.metric(
    "Districts in workbook",
    len(districts) if districts else "—"
)

metric3.metric(
    "Official website",
    "Available" if valid_url(website)
    else "Not listed"
)


# =====================================================
# DIRECTORY DETAILS AND QUICK LINKS
# =====================================================

left, right = st.columns([2, 1])

with left:

    st.markdown("### College Directory Details")

    st.write("**District:**", district)

    st.write(
        "**Address:**",
        address or "Not listed in Excel"
    )

    st.write(
        "**Principal Email:**",
        email or "Not listed in Excel"
    )

    st.write(
        "**Principal Phone:**",
        phone or "Not listed in Excel"
    )

    if valid_url(website):

        st.link_button(
            "🌐 Open Official Website",
            website,
            use_container_width=True
        )

    st.link_button(
        "📍 Open Google Maps",
        maps_url,
        use_container_width=True
    )

    if valid_url(wiki_url):

        st.link_button(
            "📚 Open Wikipedia",
            wiki_url,
            use_container_width=True
        )


with right:

    st.markdown("### Quick Links")

    if valid_url(website):

        st.link_button(
            "🌐 College Website",
            website,
            use_container_width=True
        )

    st.link_button(
        "📍 Google Maps",
        maps_url,
        use_container_width=True
    )

    if valid_url(wiki_url):

        st.link_button(
            "📚 Wikipedia",
            wiki_url,
            use_container_width=True
        )


# =====================================================
# EXPLORE COLLEGE INFORMATION
# =====================================================

st.divider()

st.markdown(
    "## 📚 Explore College Information"
)

topics = [
    "About Us",
    "Departments",
    "Intake",
    "University Type",
    "Establishment Year",
    "Placement Overview",
    "Hiring Companies"
]

if "active_topic" not in st.session_state:
    st.session_state.active_topic = "About Us"

topic_columns = st.columns(4)

for index, topic in enumerate(topics):

    with topic_columns[index % 4]:

        if st.button(
            topic,
            key=f"topic_{topic}",
            use_container_width=True
        ):

            st.session_state.active_topic = topic

            # Clear results from the previous topic/college.
            for key in [
                "scraped_pages",
                "scraped_warnings",
                "scraped_college",
                "scraped_topic"
            ]:
                st.session_state.pop(key, None)


active_topic = st.session_state.active_topic

st.markdown(
    f"### {active_topic}"
)

st.caption(
    "The app searches accessible pages on the selected college's "
    "official website. Verify the extracted details using the sources."
)


# =====================================================
# FETCH COLLEGE WEBSITE INFORMATION
# =====================================================

if not valid_url(website):

    st.warning(
        "No valid official website URL is available for this college. "
        "Add its official website to the Excel file."
    )

else:

    if st.button(
        f"🔎 Fetch {active_topic} from College Website",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Reading the college website and relevant pages..."
        ):

            pages, warnings = scrape_college_site(
                website,
                active_topic
            )

        st.session_state.scraped_pages = pages
        st.session_state.scraped_warnings = warnings
        st.session_state.scraped_college = selected_college
        st.session_state.scraped_topic = active_topic

    if (
        st.session_state.get("scraped_college")
        == selected_college
        and st.session_state.get("scraped_topic")
        == active_topic
    ):

        pages = st.session_state.get(
            "scraped_pages", []
        )

        warnings = st.session_state.get(
            "scraped_warnings", []
        )

        if not pages:

            st.error(
                "The website could not be read automatically. "
                "It may block requests or require JavaScript."
            )

            st.markdown(
                f"[Open official website]({website})"
            )

        else:

            st.success(
                f"Read {len(pages)} page(s)."
            )

            render_results(
                pages,
                active_topic
            )

            # Establishment year references
            if active_topic == "Establishment Year":

                combined_text = " ".join(
                    page["text"] for page in pages
                )

                years = sorted(set(
                    re.findall(
                        r"\b(?:19\d{2}|20[0-2]\d)\b",
                        combined_text
                    )
                ))

                if years:

                    st.markdown(
                        "**Year references found on fetched pages:**"
                    )

                    st.write(", ".join(years))

                    st.caption(
                        "These are year references, not confirmed "
                        "establishment years. Verify the official history."
                    )

                else:

                    st.info(
                        "No year was detected. Check the college's "
                        "About Us or History page."
                    )

            # Placement year references
            if active_topic == "Placement Overview":

                combined_text = " ".join(
                    page["text"] for page in pages
                )

                years = sorted(set(
                    re.findall(
                        r"\b(?:20\d{2}\s*[-–/]\s*(?:20)?\d{2}|20\d{2})\b",
                        combined_text
                    )
                ))

                if years:

                    st.markdown(
                        "**Placement year references detected:**"
                    )

                    st.write(
                        ", ".join(years[-12:])
                    )

                st.caption(
                    "Placement figures and recruiter lists should "
                    "be verified using official placement reports."
                )

            # Source pages
            with st.expander("🔗 View all source pages"):

                for page in pages:

                    st.markdown(
                        f"- [{page['reason']}]({page['url']})"
                    )

            # Failed pages
            if warnings:

                with st.expander("⚠️ Pages that could not be read"):

                    for warning in warnings:
                        st.write("•", warning)


# =====================================================
# COMPLETE COLLEGE DATA
# =====================================================

st.divider()

st.markdown(
    "## 📊 Complete College Data"
)

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

csv_data = df.to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    "⬇️ Download College Data as CSV",
    data=csv_data,
    file_name="karnataka_college_data.csv",
    mime="text/csv",
    use_container_width=True
)

st.caption(
    "Directory details come from the uploaded Excel file. "
    "Website extraction may miss information when sites block "
    "automated requests or require JavaScript."
)
