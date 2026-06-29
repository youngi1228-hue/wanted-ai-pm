from firecrawl import FirecrawlApp
from dotenv import load_dotenv
import os
import re
import pandas as pd
from datetime import datetime

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")

if not api_key:
    raise ValueError(".env 파일에 FIRECRAWL_API_KEY가 없습니다.")

app = FirecrawlApp(api_key=api_key)

SEARCH_URL = "https://www.wanted.co.kr/search?query=AI%20PM"


def clean_text(text):
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"#+", "", text)
    text = re.sub(r"-{3,}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def metadata_to_dict(metadata):
    if metadata is None:
        return {}

    if isinstance(metadata, dict):
        return metadata

    if hasattr(metadata, "model_dump"):
        return metadata.model_dump()

    if hasattr(metadata, "dict"):
        return metadata.dict()

    try:
        return vars(metadata)
    except TypeError:
        return {}


def parse_wanted_header(markdown, metadata):
    title = "비공개"
    company = "비공개"
    location = "비공개"
    career = "비공개"

    text = markdown or ""
    meta = metadata_to_dict(metadata)

    meta_title = (
        meta.get("title")
        or meta.get("ogTitle")
        or meta.get("og:title")
        or ""
    )

    # Wanted SEO 제목 예시:
    # [에이엑스지(axz)] AI 검색 서비스 기획자 채용 공고
    meta_match = re.search(
        r"^\[(.+?)\]\s*(.+?)\s*채용\s*공고",
        meta_title
    )

    if meta_match:
        company = clean_text(meta_match.group(1))
        title = clean_text(meta_match.group(2))

    # Wanted 본문 제목: # AI 검색 서비스 기획자
    for match in re.finditer(
        r"^\s*#\s+(.+?)\s*$",
        text,
        re.MULTILINE
    ):
        candidate = clean_text(match.group(1))

        blocked_titles = [
            "포지션 상세",
            "주요업무",
            "자격요건",
            "우대사항",
            "기술 스택",
            "태그",
            "마감일",
            "근무지역"
        ]

        if not any(word in candidate for word in blocked_titles):
            title = candidate
            break

    # Wanted 상단 정보:
    # 회사명∙지역∙경력
    header_match = re.search(
        r"^\s*([^∙\n]{2,60})\s*∙\s*"
        r"([^∙\n]{2,60})\s*∙\s*"
        r"([^\n]{2,60})\s*$",
        text,
        re.MULTILINE
    )

    if header_match:
        candidate_company = clean_text(header_match.group(1))
        candidate_location = clean_text(header_match.group(2))
        candidate_career = clean_text(header_match.group(3))

        blocked_company_words = [
            "응답률",
            "합격보상",
            "지원자",
            "추천인",
            "포지션 상세"
        ]

        if not any(word in candidate_company for word in blocked_company_words):
            company = candidate_company

        location = candidate_location
        career = candidate_career

    # 근무지역 섹션을 보조적으로 사용
    if location == "비공개":
        location_match = re.search(
            r"##\s*근무지역\s*\n+\s*([^\n]+)",
            text
        )

        if location_match:
            location = clean_text(location_match.group(1))

    return title, company, location, career


def get_section(text, start_keyword, end_keywords):
    if start_keyword not in text:
        return "비공개"

    start = text.find(start_keyword)
    sub_text = text[start:]

    end_positions = []
    for keyword in end_keywords:
        pos = sub_text.find(keyword)
        if pos > 0:
            end_positions.append(pos)

    if end_positions:
        sub_text = sub_text[:min(end_positions)]

    return clean_text(sub_text)[:800]


def extract_title(text):
    lines = text.splitlines()

    for line in lines:
        line = clean_text(line)
        if not line:
            continue
        if "포지션 상세" in line:
            continue
        if "합격보상" in line:
            continue
        if "지원자" in line:
            continue
        if len(line) > 5:
            return line

    return "비공개"


def extract_company(text):
    lines = text.splitlines()

    for line in lines:
        line = clean_text(line)
        if not line:
            continue
        if "원티드" in line:
            continue
        if "포지션 상세" in line:
            continue
        if "주요업무" in line:
            break
        if len(line) >= 2 and len(line) <= 30:
            return line

    return "비공개"


def extract_keywords(text):
    keywords = [
        "AI", "PM", "Product Manager", "프로덕트", "서비스 기획",
        "LLM", "RAG", "Python", "SQL", "데이터", "머신러닝",
        "Machine Learning", "Agile", "Jira", "Figma", "API"
    ]

    found = []
    lower_text = text.lower()

    for keyword in keywords:
        if keyword.lower() in lower_text:
            found.append(keyword)

    return ", ".join(found) if found else "비공개"


def extract_job_info(url, markdown):
    text = markdown or ""
    clean = clean_text(text)

def extract_job_info(url, markdown, metadata=None):
    text = markdown or ""
    clean = clean_text(text)

    title, company, location, career = parse_wanted_header(
        text,
        metadata
    )

    main_task = get_section(
        text,
        "주요업무",
        ["자격요건", "우대사항", "혜택", "복지", "채용절차"]
    )

    requirements = get_section(
        text,
        "자격요건",
        ["우대사항", "혜택", "복지", "채용절차"]
    )

    preference = get_section(
        text,
        "우대사항",
        ["혜택", "복지", "채용절차"]
    )

    return {
        "제목": title,
        "회사명": company,
        "지역": location,
        "경력": career,
        "주요업무": main_task,
        "자격요건": requirements,
        "우대사항": preference,
        "키워드": extract_keywords(clean),
        "URL": url,
        "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "원문": text[:10000]
    }

    main_task = get_section(
        text,
        "주요업무",
        ["자격요건", "우대사항", "혜택", "복지", "채용절차"]
    )

    requirements = get_section(
        text,
        "자격요건",
        ["우대사항", "혜택", "복지", "채용절차"]
    )

    preference = get_section(
        text,
        "우대사항",
        ["혜택", "복지", "채용절차"]
    )



    return {
        "제목": title,
        "회사명": company,
        "지역": location,
        "경력": career,
        "주요업무": main_task,
        "자격요건": requirements,
        "우대사항": preference,
        "키워드": extract_keywords(clean),
        "URL": url,
        "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "원문": clean[:3000]
    }


print("Wanted 검색 페이지 수집 중...")

result = app.scrape_url(
    SEARCH_URL,
    formats=["markdown"]
)

urls = re.findall(
    r"https://www\.wanted\.co\.kr/wd/\d+",
    result.markdown
)

urls = list(set(urls))

print("찾은 URL 수:", len(urls))

jobs = []

for index, url in enumerate(urls, start=1):
    print(f"[{index}/{len(urls)}] 상세 수집 중: {url}")

    try:
        detail = app.scrape_url(
            url,
            formats=["markdown"],
            only_main_content=False,
            wait_for=2000)

        job = extract_job_info(
            url,
            detail.markdown,
            getattr(detail, "metadata", None)
        )
        jobs.append(job)

        print("수집 완료:", job["제목"])

    except Exception as e:
        print("수집 실패:", url)
        print("오류:", e)

df = pd.DataFrame(jobs)

df.to_csv(
    "wanted_jobs_clean.csv",
    index=False,
    encoding="utf-8-sig"
)

print("CSV 저장 완료: wanted_jobs_clean.csv")
print("총 수집:", len(df))