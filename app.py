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

# ---------------- PAGE CONFIGURATION ----------------
st.set_page_config(
    page_title="Karnataka College Finder",
    page_icon="🎓",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #f5f7fb, #edf2f8);
}
.hero {
    padding: 25px;
    border-radius: 18px;
    background: linear-gradient(120deg, #10243a, #245b78);
    color: white;
    margin-bottom: 20px;
}
.hero h1 { color: white; }
div[data-testid="stMetric"] {
    background: white;
    padding: 12px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🎓 Karnataka College Finder</h1>
<p>Explore engineering colleges, departments, intake,
establishment year, placements and hiring companies.</p>
</div>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36"
}

TIMEOUT = 12
MAX_PAGES = 8
MAX_PDF_BYTES = 12 * 1024 * 1024


# ---------------- HELPER FUNCTIONS ----------------
def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower().strip())


def find_column(df, aliases):
    columns = {normalize(c): c for c in df.columns}

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
    return "" if pd.isna(value) else str(value).strip()


def valid_url(url):
    return isinstance(url, str) and url.strip().lower().startswith(
        ("http://", "https://")
    )


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


def same_domain(base, link):
    try:
        base_domain = urlparse(base).netloc.lower().replace("www.", "")
        link_domain = urlparse(link).netloc.lower().replace("www.", "")
        return base_domain == link_domain
    except Exception:
        return False


def google_maps_url(name, address=""):
    query = quote_plus(clean_text(f"{name} {address}"))
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def source_link(label, url):
    if valid_url(url):
        st.markdown(f"[{label}]({url})")


# ---------------- WEBSITE READER ----------------
def fetch_page_text(url):
    response = safe_get(url)

    if response is None:
        return url, "", []

    content_type = response.headers.get("Content-Type", "").lower()

    # Extract text from PDFs
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        if not pdfplumber:
            return response.url, "PDF found. Install pdfplumber to read it.", []

        if len(response.content) > MAX_PDF_BYTES:
            return response.url, "PDF exceeds the 12 MB limit.", []

        try:
            text_parts = []

            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                for page in pdf.pages[:35]:
                    text_parts.append(page.extract_text() or "")

            return response.url, clean_text(" ".join(text_parts)), []

        except Exception:
            return response.url, "", []

    # Extract text and links from webpages
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup([
        "script", "style", "nav", "footer",
        "header", "noscript", "svg"
    ]):
        tag.decompose()

    page_text = clean_text(soup.get_text(" ", strip=True))
    links = []

    for anchor in soup.find_all("a", href=True):
        href = urljoin(response.url, anchor["href"].strip())
        label = clean_text(anchor.get_text(" ", strip=True))

        if valid_url(href):
            links.append((label, href))

    return response.url, page_text, links


# ---------------- TOPIC EXTRACTION ----------------
TOPIC_KEYWORDS = {
    "About Us": [
        "about", "history", "profile", "vision",
        "mission", "established", "founded"
    ],
    "Departments": [
        "department", "computer science", "information science",
        "mechanical", "civil", "electrical", "electronics",
        "artificial intelligence", "data science", "academics"
    ],
    "Intake": [
        "intake", "sanctioned", "seats", "admission",
        "approved intake", "students"
    ],
    "University Type": [
        "autonomous", "affiliated", "affiliation",
        "university", "VTU", "Visvesvaraya"
    ],
    "Establishment Year": [
        "established", "establishment", "founded",
        "inception", "since", "started in"
    ],
    "Placement Overview": [
        "placement", "placed", "placement percentage",
        "package", "salary", "highest", "average",
        "recruitment", "2024", "2025", "2026"
    ],
    "Hiring Companies": [
        "recruiter", "recruiters", "company", "companies",
        "hiring", "placement", "Infosys", "TCS",
        "Wipro", "Accenture"
    ]
}


def scrape_college_site(website, topic):
    if not valid_url(website):
        return [], ["No valid official website URL is available."]

    visited = set()
    queue = [(website, "Official website homepage")]
    pages = []
    warnings = []

    keywords = TOPIC_KEYWORDS[topic]

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
            warnings.append(f"Could not read: {url}")

        candidates = []

        for label, link in links:
            if link in visited or not same_domain(website, link):
                continue

            combined = (label + " " + link).lower()
            score = sum(1 for word in keywords if word.lower() in combined)

            if score > 0:
                candidates.append((score, label, link))

        candidates.sort(reverse=True)

        for score, label, link in candidates:
            if link not in visited:
                if all(item[0] != link for item in queue):
                    queue.append((
                        link,
                        f"Relevant page: {label or link}"
                    ))

        queue.sort(
            key=lambda item: sum(
                1 for word in keywords
                if word.lower() in (item[0] + item[1]).lower()
            ),
            reverse=True
        )

    return pages, warnings


def extract_snippets(pages, keywords):
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

            if any(word.lower() in sentence.lower() for word in keywords):
                if sentence not in matched:
                    matched.append(sentence)

        if matched:
            results.append((page["url"], matched[:8]))

    return results


def show_topic_results(pages, topic):
    snippets = extract_snippets(
        pages,
        TOPIC_KEYWORDS[topic]
    )

    if not snippets:
        st.warning(
            "No matching information was detected automatically. "
            "Open the source links to check the website manually."
        )

    for url, sentences in snippets:
        with st.container(border=True):
            source_link("🔗 Open official source", url)

            for sentence in sentences:
                st.write("• " + sentence[:800])


# ---------------- EXCEL UPLOAD ----------------
uploaded_file = st.file_uploader(
    "📂 Upload your engineering colleges Excel file",
    type=["xlsx", "xls"]
)

if uploaded_file is None:
    st.info("Upload your Excel workbook to begin.")
    st.markdown("""
    **How to use**
    1. Upload your Excel workbook.
    2. Filter colleges by district.
    3. Select a college.
    4. Choose a topic.
    5. Fetch information from the official website.
    """)
    st.stop()

try:
    excel = pd.ExcelFile(uploaded_file)

    sheet = (
        "Engineering Colleges"
        if "Engineering Colleges" in excel.sheet_names
        else excel.sheet_names[0]
    )

    df = pd.read_excel(uploaded_file, sheet_name=sheet)
    df = df.dropna(how="all")

except Exception as error:
    st.error(f"Could not read the Excel file: {error}")
    st.stop()


# ---------------- DETECT EXCEL COLUMNS ----------------
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
    st.error("The Excel file must contain a College Name column.")
    st.write("Available columns:", list(df.columns))
    st.stop()

df[name_col] = df[name_col].fillna("").astype(str).str.strip()
df = df[df[name_col] != ""]


# ---------------- SIDEBAR FILTERS ----------------
districts = (
    sorted(df[district_col].dropna().astype(str).unique().tolist())
    if district_col else []
)

with st.sidebar:
    st.header("🔍 Find a College")

    selected_district = st.selectbox(
        "Select District",
        ["All districts"] + districts
    )

    if selected_district != "All districts" and district_col:
        filtered_df = df[
            df[district_col].astype(str) == selected_district
        ]
    else:
        filtered_df = df

    search_text = st.text_input("Search college name")

    if search_text:
        filtered_df = filtered_df[
            filtered_df[name_col].str.contains(
                search_text,
                case=False,
                na=False
            )
        ]

    if filtered_df.empty:
        st.warning("No colleges match your search.")
        st.stop()

    selected_college = st.selectbox(
        "Choose College",
        filtered_df[name_col].tolist()
    )

    st.caption(f"Excel sheet: {sheet}")


# ---------------- SELECTED COLLEGE DETAILS ----------------
row = df[df[name_col] == selected_college].iloc[0]

district = cell(row, district_col) or "Not listed"
website = cell(row, website_col)
address = cell(row, address_col)
taluk = cell(row, taluk_col)
email = cell(row, email_col)
phone = cell(row, phone_col)

maps_url = cell(row, maps_col) or google_maps_url(
    selected_college,
    address
)

wiki_url = cell(row, wiki_col)

st.subheader(f"🎓 {selected_college}")
st.caption(" • ".join(
    value for value in [district, taluk] if value
))

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Colleges in workbook", len(df))
metric2.metric("Districts in workbook", len(districts))
metric3.metric(
    "Official website",
    "Available" if valid_url(website) else "Not listed"
)

left, right = st.columns([2, 1])

with left:
    st.markdown("### College Directory Details")
    st.write("**District:**", district)
    st.write("**Address:**", address or "Not listed in Excel")
    st.write("**Principal Email:**", email or "Not listed in Excel")
    st.write("**Principal Phone:**", phone or "Not listed in Excel")

    if valid_url(website):
        st.link_button("🌐 Open Official Website", website)

    st.link_button("📍 Open Google Maps", maps_url)

    if valid_url(wiki_url):
        st.link_button("📚 Wikipedia / Search", wiki_url)

with right:
    st.markdown("### Quick Links")

    if valid_url(website):
        st.markdown(f"[College Website]({website})")

    st.markdown(f"[Google Maps]({maps_url})")

    if valid_url(wiki_url):
        st.markdown(f"[Wikipedia]({wiki_url})")


# ---------------- TOPIC SELECTION ----------------
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

if "active_topic" not in st.session_state:
    st.session_state.active_topic = "About Us"

columns = st.columns(4)

for index, topic in enumerate(topics):
    if columns[index % 4].button(
        topic,
        key=f"button_{topic}",
        use_container_width=True
    ):
        st.session_state.active_topic = topic

active_topic = st.session_state.active_topic

st.markdown(f"### {active_topic}")

st.caption(
    "Information is extracted automatically from the college website. "
    "Check the source links to verify details."
)

if not valid_url(website):
    st.warning(
        "No valid official website URL was found. "
        "Add the official website to your Excel file."
    )
else:
    if st.button(
        f"🔎 Fetch {active_topic} from College Website",
        type="primary"
    ):
        with st.spinner("Reading the college website..."):
            pages, warnings = scrape_college_site(
                website,
                active_topic
            )

        st.session_state.scraped_pages = pages
        st.session_state.scrape_warnings = warnings
        st.session_state.scraped_college = selected_college
        st.session_state.scraped_topic = active_topic

    if (
        st.session_state.get("scraped_college") == selected_college
        and st.session_state.get("scraped_topic") == active_topic
    ):
        pages = st.session_state.get("scraped_pages", [])
        warnings = st.session_state.get("scrape_warnings", [])

        if not pages:
            st.error(
                "The website could not be read automatically. "
                "It may block requests or require JavaScript."
            )
            st.markdown(f"[Open official website]({website})")
        else:
            st.success(f"Read {len(pages)} page(s).")

            if active_topic == "Placement Overview":
                st.info(
                    "Only information found on the fetched pages is shown. "
                    "Missing figures are not assumed to be zero."
                )

            show_topic_results(pages, active_topic)

            if active_topic == "Establishment Year":
                combined_text = " ".join(
                    page["text"] for page in pages
                )

                year_pattern = (
                    r"\b(?:19\d{2}|20[0-2]\d)\b"
                )

                years = sorted(set(
                    re.findall(year_pattern, combined_text)
                ))

                if years:
                    st.markdown("**Year references found on fetched pages**")
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
                    st.markdown("**Year references detected**")
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


# ---------------- SHOW EXCEL DATA ----------------
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
