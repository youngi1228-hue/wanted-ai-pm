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
    return re.sub(r"\s+", " ", text).strip()


def extract_field(text, patterns, default="비공개"):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return clean_text(match.group(1))
    return default


def extract_job_info(url, markdown):
    text = markdown or ""

    title = extract_field(text, [
        r"#\s*(.+)",
        r"포지션 상세\s*\n+(.+)"
    ])

    company = extract_field(text, [
        r"회사명[:\s]+(.+)",
        r"##\s*회사 소개\s*\n+(.+)",
        r"\*\*(.+?)\*\*"
    ])

    location = extract_field(text, [
        r"근무지역[:\s]+(.+)",
        r"지역[:\s]+(.+)",
        r"위치[:\s]+(.+)",
        r"주소[:\s]+(.+)"
    ])

    experience = extract_field(text, [
        r"경력[:\s]+(.+)",
        r"경력\s*사항[:\s]+(.+)",
        r"(\d+년\s*이상)",
        r"(신입|경력무관|무관)"
    ])

    education = extract_field(text, [
        r"학력[:\s]+(.+)",
        r"(학력무관|대졸|초대졸|고졸)"
    ])

    salary = extract_field(text, [
        r"연봉[:\s]+(.+)",
        r"급여[:\s]+(.+)",
        r"보상[:\s]+(.+)"
    ])

    skills = []
    skill_keywords = [
        "AI", "PM", "Product Manager", "프로덕트", "Python", "SQL",
        "LLM", "RAG", "머신러닝", "Machine Learning", "데이터", "기획",
        "서비스 기획", "Agile", "Jira", "Figma"
    ]

    for keyword in skill_keywords:
        if keyword.lower() in text.lower():
            skills.append(keyword)

    return {
        "제목": title,
        "회사명": company,
        "지역": location,
        "경력": experience,
        "학력": education,
        "연봉": salary,
        "키워드": ", ".join(skills) if skills else "비공개",
        "URL": url,
        "수집일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "내용": text
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
            formats=["markdown"]
        )

        job = extract_job_info(url, detail.markdown)
        jobs.append(job)

        print("수집 완료:", job["제목"])

    except Exception as e:
        print("수집 실패:", url)
        print("오류:", e)

df = pd.DataFrame(jobs)

df.to_csv(
    "wanted_jobs.csv",
    index=False,
    encoding="utf-8-sig"
)

print("CSV 저장 완료: wanted_jobs.csv")
print("총 수집:", len(df))