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

# ================= PAGE CONFIGURATION =================
st.set_page_config(
    page_title="Karnataka College Finder",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================= CUSTOM DESIGN =================
st.markdown("""
<style>
/* Main page */
.stApp {
    background: linear-gradient(135deg, #f5f7fb, #e8eef5);
    color: #111827;
}

/* Make normal text black */
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp p,
.stApp label,
.stApp li,
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] strong,
.stApp [data-testid="stCaptionContainer"] {
    color: #111827 !important;
}

/* Header banner */
.hero {
    padding: 25px;
    border-radius: 18px;
    background: linear-gradient(120deg, #10243a, #245b78);
    color: white;
    margin-bottom: 20px;
}

.hero h1 {
    color: #ffffff !important;
    margin: 0;
    font-size: 2rem;
}

.hero p {
    color: #e0edf5 !important;
    margin-top: 8px;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: #ffffff;
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

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #ffffff;
}

section[data-testid="stSidebar"] * {
    color: #111827;
}

/* Text inputs and dropdowns */
.stTextInput input,
.stTextArea textarea,
div[data-baseweb="select"] * {
    color: #111827 !important;
    background-color: #ffffff;
}

/* Links */
.stApp a {
    color: #0969da !important;
}

/* Buttons */
div.stButton > button {
    border-radius: 10px;
    min-height: 2.6rem;
    font-weight: 600;
}

/* Cards and tables */
div[data-testid="stDataFrame"] {
    background-color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🎓 Karnataka College Finder</h1>
    <p>
        Explore engineering colleges, departments, intake,
        establishment year, placements and campus locations.
    </p>
</div>
""", unsafe_allow_html=True)


# ================= SETTINGS =================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 12
MAX_PAGES_TO_SCAN = 8
MAX_PDF_BYTES = 12 * 1024 * 1024


# ================= EXCEL HELPERS =================
def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower().strip())


def find_column(df, aliases):
    normalized = {normalize(c): c for c in df.columns}

    for alias in aliases:
        if normalize(alias) in normalized:
            return normalized[normalize(alias)]

    for col in df.columns:
        for alias in aliases:
            if normalize(alias) in normalize(col):
                return col

    return None


def cell(row, col):
    if not col:
        return ""

    value = row.get(col, "")

    if pd.isna(value):
        return ""

    return str(value).strip()


def valid_url(url):
    return (
        isinstance(url, str)
        and url.strip().lower().startswith(("http://", "https://"))
    )


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def google_maps_url(name, address=""):
    query = clean_text(f"{name} {address}")
    return (
        "https://www.google.com/maps/search/?api=1&query="
        + quote_plus(query)
    )


# ================= WEBSITE READER =================
def safe_get(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response
    except requests.RequestException:
        return None


def same_domain(base, link):
    try:
        base_domain = (
            urlparse(base).netloc.lower().replace("www.", "")
        )
        link_domain = (
            urlparse(link).netloc.lower().replace("www.", "")
        )
        return base_domain == link_domain
    except Exception:
        return False


def page_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"].strip())
        label = clean_text(
            anchor.get_text(" ", strip=True)
        )

        if valid_url(href):
            links.append((label, href))

    return links


def fetch_page_text(url):
    response = safe_get(url)

    if response is None:
        return None, "", []

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    # Read PDF files
    if "pdf" in content_type or url.lower().endswith(".pdf"):

        if pdfplumber is None:
            return (
                response.url,
                "PDF found, but pdfplumber is not installed.",
                []
            )

        if len(response.content) > MAX_PDF_BYTES:
            return (
                response.url,
                "PDF exceeds the 12 MB limit.",
                []
            )

        try:
            pieces = []

            with pdfplumber.open(
                io.BytesIO(response.content)
            ) as pdf:
                for page in pdf.pages[:35]:
                    pieces.append(page.extract_text() or "")

            return (
                response.url,
                clean_text(" ".join(pieces)),
                []
            )

        except Exception:
            return response.url, "", []

    # Read HTML pages
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup([
        "script", "style", "nav", "footer",
        "header", "noscript", "svg"
    ]):
        tag.decompose()

    text = clean_text(soup.get_text(" ", strip=True))
    links = page_links(response.url, response.text)

    return response.url, text, links


# ================= TOPIC SEARCH =================
TOPIC_WORDS = {
    "About Us": [
        "about", "history", "profile", "vision",
        "mission", "inception"
    ],
    "Departments": [
        "department", "academics", "courses",
        "programmes", "programs", "branch"
    ],
    "Intake": [
        "intake", "admission", "admissions",
        "seat", "sanctioned", "course"
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
        "about", "history", "established", "founded",
        "mission", "vision", "institute", "college"
    ],
    "Departments": [
        "department", "computer science",
        "information science", "mechanical",
        "civil", "electrical", "electronics",
        "artificial intelligence", "data science"
    ],
    "Intake": [
        "intake", "sanctioned", "seats",
        "admission", "students", "approved"
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
        "salary", "students", "highest",
        "average", "2024", "2025", "2026"
    ],
    "Hiring Companies": [
        "recruiter", "recruiters", "company",
        "companies", "hiring", "infosys",
        "tcs", "wipro", "accenture"
    ]
}


def score_link(label, url, keywords):
    combined = (
        label + " " + url
    ).lower().replace("-", " ").replace("_", " ")

    return sum(
        1 for word in keywords
        if word.lower() in combined
    )


def scrape_college_site(website, topics):
    if not valid_url(website):
        return [], ["No valid official website URL was supplied."]

    found = []
    warnings = []
    visited = set()

    queue = [(website, "Official website homepage")]

    keywords = []

    for topic in topics:
        keywords.extend(TOPIC_WORDS.get(topic, []))

    keywords = list(dict.fromkeys(keywords))

    while queue and len(visited) < MAX_PAGES_TO_SCAN:
        url, reason = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        final_url, text, links = fetch_page_text(url)

        if text:
            found.append({
                "url": final_url or url,
                "reason": reason,
                "text": text
            })
        else:
            warnings.append(f"Could not read: {url}")

        candidates = []

        for label, link in links:
            if link in visited:
                continue

            if not same_domain(website, link):
                continue

            score = score_link(label, link, keywords)

            if score > 0:
                candidates.append((score, label, link))

        candidates.sort(reverse=True)

        for score, label, link in candidates:
            if link not in visited and all(
                item[0] != link for item in queue
            ):
                queue.append((
                    link,
                    f"Relevant page: {label or link}"
                ))

        queue.sort(
            key=lambda item: score_link(
                item[1], item[0], keywords
            ),
            reverse=True
        )

    return found, warnings


# ================= DISPLAY EXTRACTED TEXT =================
def extract_snippets(pages, keywords, limit=8):
    results = []

    for page in pages:
        sentences = re.split(
            r"(?<=[.!?])\s+|(?<=\|)\s*",
            page["text"]
        )

        matched = []

        for sentence in sentences:
            sentence = clean_text(sentence)

            if len(sentence) < 25:
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


def render_snippets(pages, keywords):
    snippets = extract_snippets(pages, keywords)

    if not snippets:
        st.info(
            "No matching details were detected automatically. "
            "Open the official source pages to check manually."
        )

    for url, lines in snippets:
        with st.container(border=True):
            st.markdown(f"[🔗 Open official source]({url})")

            for line in lines:
                st.write("• " + line[:800])


# ================= READ EXCEL =================
def read_excel(uploaded_file):
    try:
        excel = pd.ExcelFile(uploaded_file)

        sheet = (
            "Engineering Colleges"
            if "Engineering Colleges" in excel.sheet_names
            else excel.sheet_names[0]
        )

        df = pd.read_excel(
            uploaded_file,
            sheet_name=sheet
        )

        return df.dropna(how="all"), sheet

    except Exception as error:
        st.error(f"Could not read Excel file: {error}")
        return None, None


# ================= UPLOAD EXCEL =================
uploaded = st.file_uploader(
    "📂 Upload your engineering colleges Excel file",
    type=["xlsx", "xls"]
)

if uploaded is None:
    st.info("Upload your Excel workbook to begin.")

    st.markdown("""
    ### How to use the app

    1. Upload your Excel workbook.
    2. Filter colleges by district.
    3. Select a college.
    4. Open its website or Google Maps.
    5. Fetch information about departments, intake,
       establishment year, placements and recruiters.
    """)

    st.stop()


df, sheet_name = read_excel(uploaded)

if df is None or df.empty:
    st.error("The Excel file is empty or could not be read.")
    st.stop()


# ================= FIND EXCEL COLUMNS =================
district_col = find_column(df, ["District"])

name_col = find_column(df, [
    "College Name", "Institution Name",
    "Name of College", "College"
])

website_col = find_column(df, [
    "Official Website URL", "Official Website",
    "Website URL", "Website"
])

address_col = find_column(df, [
    "Exact Location / Address", "Address", "Location"
])

maps_col = find_column(df, [
    "Google Maps Link", "Maps Link", "Google Maps"
])

taluk_col = find_column(df, [
    "Taluk / Location", "Taluk"
])

wiki_col = find_column(df, [
    "Wikipedia URL / Search", "Wikipedia URL", "Wikipedia"
])

email_col = find_column(df, [
    "Principal Email", "Email", "Contact Email"
])

phone_col = find_column(df, [
    "Principal Phone", "Phone", "Contact Phone"
])

if not name_col:
    st.error("Could not find a College Name column.")
    st.write("Available columns:", list(df.columns))
    st.stop()

df = df.copy()
df[name_col] = df[name_col].fillna("").astype(str).str.strip()
df = df[df[name_col] != ""]

districts = (
    sorted(df[district_col].dropna().astype(str).unique())
    if district_col else []
)


# ================= SIDEBAR FILTERS =================
with st.sidebar:
    st.header("🔍 Find a College")

    selected_district = st.selectbox(
        "Select District",
        ["All districts"] + districts
    )

    if selected_district != "All districts" and district_col:
        filtered = df[
            df[district_col].astype(str) == selected_district
        ]
    else:
        filtered = df

    search = st.text_input("Search college name")

    if search:
        filtered = filtered[
            filtered[name_col].str.contains(
                search, case=False, na=False
            )
        ]

    options = filtered[name_col].tolist()

    if not options:
        st.warning("No colleges match your filters.")
        st.stop()

    selected_name = st.selectbox(
        "Choose College",
        options
    )

    st.caption(f"Excel sheet: {sheet_name}")


# ================= COLLEGE DETAILS =================
row = df[df[name_col] == selected_name].iloc[0]

district = cell(row, district_col) or "Not listed"
website = cell(row, website_col)
address = cell(row, address_col)
taluk = cell(row, taluk_col)
email = cell(row, email_col)
phone = cell(row, phone_col)
wiki_url = cell(row, wiki_col)

maps_url = (
    cell(row, maps_col)
    or google_maps_url(selected_name, address)
)

st.subheader(f"🎓 {selected_name}")

st.caption(" • ".join(
    value for value in [district, taluk] if value
))


# ================= DASHBOARD METRICS =================
m1, m2, m3 = st.columns(3)

m1.metric("Colleges in workbook", len(df))
m2.metric("Districts in workbook", len(districts))
m3.metric(
    "Official website",
    "Available" if valid_url(website) else "Not listed"
)


# ================= DIRECTORY INFORMATION =================
left, right = st.columns([2, 1])

with left:
    st.markdown("### College Directory Details")

    st.write("**District:**", district)
    st.write("**Address:**", address or "Not listed in Excel")
    st.write("**Principal Email:**", email or "Not listed in Excel")
    st.write("**Principal Phone:**", phone or "Not listed in Excel")

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
            "📚 Wikipedia / Search",
            wiki_url,
            use_container_width=True
        )

with right:
    st.markdown("### Quick Links")

    if valid_url(website):
        st.markdown(f"[College Website]({website})")

    st.markdown(f"[Google Maps]({maps_url})")

    if valid_url(wiki_url):
        st.markdown(f"[Wikipedia]({wiki_url})")


# ================= INFORMATION TOPICS =================
st.divider()
st.markdown("## 📚 Explore College Information")

topics = [
    "About Us",
    "Departments",
    "Intake",
    "University Type",
    "Establishment Year",
    "Placement Overview",
    "Hiring Companies"
]

columns = st.columns(4)

for index, topic in enumerate(topics):
    if columns[index % 4].button(
        topic,
        key=f"topic_{topic}",
        use_container_width=True
    ):
        st.session_state["active_topic"] = topic

active_topic = st.session_state.get(
    "active_topic", "About Us"
)

st.markdown(f"### {active_topic}")

st.caption(
    "Information is extracted automatically from the college website. "
    "Verify results using the original source links."
)


# ================= FETCH WEBSITE INFORMATION =================
if not valid_url(website):
    st.warning(
        "No valid official website URL is available for this college. "
        "Add the website URL to your Excel file."
    )

else:
    if st.button(
        f"🔎 Fetch {active_topic} from College Website",
        type="primary"
    ):
        with st.spinner("Reading the official website..."):
            pages, warnings = scrape_college_site(
                website, [active_topic]
            )

        st.session_state["scraped_pages"] = pages
        st.session_state["scraped_warnings"] = warnings
        st.session_state["scraped_college"] = selected_name
        st.session_state["scraped_topic"] = active_topic

    if (
        st.session_state.get("scraped_college") == selected_name
        and st.session_state.get("scraped_topic") == active_topic
    ):
        pages = st.session_state.get("scraped_pages", [])
        warnings = st.session_state.get("scraped_warnings", [])

        if not pages:
            st.error(
                "The website could not be read automatically. "
                "It may block automated requests or require JavaScript."
            )

            st.markdown(f"[Open official website]({website})")

        else:
            st.success(f"Read {len(pages)} page(s).")

            if active_topic == "Placement Overview":
                st.info(
                    "Only information found on the fetched pages is shown. "
                    "Missing placement figures are not invented."
                )

            render_snippets(
                pages,
                RESULT_KEYWORDS.get(active_topic, [])
            )

            # Establishment-year references
            if active_topic == "Establishment Year":
                combined_text = " ".join(
                    page["text"] for page in pages
                )

                years = sorted(set(re.findall(
                    r"\b(?:19\d{2}|20[0-2]\d)\b",
                    combined_text
                )))

                if years:
                    st.markdown(
                        "**Year references found on the fetched pages:**"
                    )
                    st.write(", ".join(years))

                    st.caption(
                        "These are year references, not necessarily "
                        "the establishment year. Verify the source."
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

                years = sorted(set(re.findall(
                    r"\b(?:20\d{2}\s*[-–/]\s*(?:20)?\d{2}|20\d{2})\b",
                    combined_text
                )))

                if years:
                    st.markdown("**Placement year references detected:**")
                    st.write(", ".join(years[-12:]))

            with st.expander("View all source pages"):
                for page in pages:
                    st.markdown(
                        f"- [{page['reason']}]({page['url']})"
                    )

            if warnings:
                with st.expander("Pages that could not be read"):
                    for warning in warnings:
                        st.write("•", warning)


# ================= EXCEL DATA TABLE =================
st.divider()
st.markdown("## 📊 College Data")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

csv_data = df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ Download College Data as CSV",
    data=csv_data,
    file_name="college_data.csv",
    mime="text/csv"
)
