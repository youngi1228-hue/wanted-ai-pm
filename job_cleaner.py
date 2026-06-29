import csv
import re
from pathlib import Path

INPUT_FILE = "wanted_jobs_clean.csv"
OUTPUT_FILE = "wanted_jobs_refined.csv"


def clean_markdown(text):
    text = str(text)

    # \[회사명\], \[AISURFER\] 같은 이스케이프 문자 제거
    text = text.replace("\\", "")

    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*#>`_~|]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_first(text, patterns, default="비공개"):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return default


def detect_region(text):
    regions = [
        "서울", "강남", "서초", "송파", "마포", "성동", "영등포", "구로",
        "경기", "성남", "판교", "분당", "하남", "수원", "용인", "과천",
        "인천", "부산", "대전", "대구", "광주", "울산", "세종"
    ]
    found = [r for r in regions if r in text]
    return ", ".join(dict.fromkeys(found)) if found else "비공개"


def detect_career(text):
    return find_first(text, [
        r"(\d+\s*년\s*이상)",
        r"(\d+\s*년\s*차)",
        r"(신입)",
        r"(경력무관|경력 무관)"
    ])


def detect_salary(text):
    return find_first(text, [
        r"(연봉\s*[0-9,]+\s*만원\s*이상)",
        r"(연봉\s*[0-9,]+\s*만원)",
        r"([0-9,]+\s*만원\s*이상)",
        r"(면접\s*후\s*협의)",
        r"(회사내규에\s*따름)",
        r"(협의)"
    ])


def detect_work_type(text):
    if "정규직" in text:
        return "정규직"
    if "계약직" in text:
        return "계약직"
    if "인턴" in text:
        return "인턴"
    if "프리랜서" in text:
        return "프리랜서"
    return "비공개"


def yes_no_contains(text, words):
    return "예" if any(word.lower() in text.lower() for word in words) else "아니오"


def detect_keywords(text):
    keywords = [
        "AI", "PM", "Product Manager", "프로덕트", "서비스 기획",
        "LLM", "RAG", "Python", "SQL", "데이터", "머신러닝",
        "Machine Learning", "Agile", "Jira", "Figma", "API",
        "UX", "기획", "PO", "Product Owner"
    ]

    found = []
    lower = text.lower()

    for keyword in keywords:
        if keyword.lower() in lower:
            found.append(keyword)

    return ", ".join(dict.fromkeys(found)) if found else "비공개"


def extract_section(text, start_words, end_words):
    start_pos = -1

    for word in start_words:
        pos = text.find(word)
        if pos != -1:
            start_pos = pos
            break

    if start_pos == -1:
        return "비공개"

    sub = text[start_pos:]

    end_positions = []

    for word in end_words:
        pos = sub.find(word)
        if pos > 20:
            end_positions.append(pos)

    if end_positions:
        sub = sub[:min(end_positions)]

    return sub[:500].strip()


def refine_title(row, text):
    current = clean_markdown(row.get("제목", ""))

    bad_titles = ["# 포지션 상세", "포지션 상세", "", "nan", "비공개"]

    if current not in bad_titles and len(current) >= 4:
        return current

    source_text = row.get("원문", row.get("내용", text))
    lines = str(source_text).splitlines()

    for line in lines:
        line = clean_markdown(line)

        if not line:
            continue
        if "포지션 상세" in line:
            continue
        if "합격보상" in line:
            continue
        if "지원자" in line:
            continue
        if "회사소개" in line:
            continue

        if "소개합니다" in line:
            continue

        if "소개" in line:
            continue

        if "기업입니다" in line:
            continue

        if "설립" in line:
            continue

        if "성장" in line:
            continue

        if "주요업무" in line:
            continue

        if 4 <= len(line) <= 80:
            return line

    return "비공개"


def is_valid_company_name(value):
    value = clean_markdown(value)

    blocked_words = [
        "합격보상",
        "지원자",
        "추천인",
        "현금",
        "포지션 상세",
        "주요업무",
        "자격요건",
        "우대사항",
        "회사소개",
        "지원하기",
        "채용절차",
        "복지",
        "혜택"
    ]

    if not value or value.lower() in ["nan", "비공개"]:
        return False

    if any(word in value for word in blocked_words):
        return False

    if len(value) < 2 or len(value) > 50:
        return False

    return True


def refine_company(row, text, title):
    # 기존 회사명이 정상적이면 그대로 사용
    current = clean_markdown(row.get("회사명", ""))

    if is_valid_company_name(current):
        return current

    source_text = row.get("원문") or row.get("내용") or text
    source_text = clean_markdown(source_text)
    title = clean_markdown(title)

    region_pattern = (
        r"서울(?:특별시)?|경기(?:도)?|인천(?:광역시)?|"
        r"부산(?:광역시)?|대전(?:광역시)?|대구(?:광역시)?|"
        r"광주(?:광역시)?|울산(?:광역시)?|세종(?:특별자치시)?|"
        r"제주(?:특별자치도)?"
    )

    # 제목 바로 다음에 나오는 회사명 추출
    if title and title != "비공개" and title in source_text:
        after_title = source_text.split(title, 1)[1].strip()

        match = re.search(
            rf"^(.{{2,60}}?)\s*·\s*(?:{region_pattern})",
            after_title
        )

        if match:
            candidate = clean_markdown(match.group(1))

            if is_valid_company_name(candidate):
                return candidate

    # 공고 전체에서 '회사명 · 지역 · 경력' 구조 탐색
    matches = re.finditer(
        rf"(.{{2,80}}?)\s*·\s*(?:{region_pattern})",
        source_text
    )

    for match in matches:
        candidate = clean_markdown(match.group(1))

        # 후보에 공고 제목까지 포함된 경우 제목 부분 제거
        if title and title in candidate:
            candidate = candidate.split(title, 1)[-1].strip()

        # 포지션 상세 문구 제거
        candidate = re.sub(
            r"^.*?포지션\s*상세\s*",
            "",
            candidate
        ).strip()

        if is_valid_company_name(candidate):
            return candidate

    return "비공개"

def make_summary(new_row):
    return (
        f"{new_row['정제회사명']}의 {new_row['정제제목']} 공고입니다. "
        f"지역은 {new_row['정제지역']}, 경력 조건은 {new_row['정제경력']}, "
        f"주요 키워드는 {new_row['정제키워드']}입니다."
    )


def main():
    if not Path(INPUT_FILE).exists():
        print(f"{INPUT_FILE} 파일이 없습니다.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        original_fields = reader.fieldnames or []

    refined_rows = []

    for row in rows:
        raw_text = " ".join(str(v) for v in row.values())
        clean_text = clean_markdown(raw_text)

        new_row = dict(row)

        new_row["정제제목"] = refine_title(row, clean_text)
        new_row["정제회사명"] = refine_company(
    row,
    clean_text,
    new_row["정제제목"]
)
        original_region = clean_markdown(row.get("지역", ""))
        original_career = clean_markdown(row.get("경력", ""))

        new_row["정제지역"] = (
            original_region
            if original_region not in ["", "nan", "비공개"]
            else detect_region(clean_text)
        )

        new_row["정제경력"] = (
            original_career
            if original_career not in ["", "nan", "비공개"]
            else detect_career(clean_text)
        )
        new_row["정제연봉"] = detect_salary(clean_text)
        new_row["정제근무형태"] = detect_work_type(clean_text)
        new_row["재택근무"] = yes_no_contains(clean_text, ["재택", "remote", "하이브리드"])
        new_row["교대근무"] = yes_no_contains(clean_text, ["교대", "교대근무", "주야간", "3교대", "2교대"])
        new_row["정제키워드"] = detect_keywords(clean_text)

        new_row["정제주요업무"] = extract_section(
            clean_text,
            ["주요업무", "담당업무", "하는 일"],
            ["자격요건", "지원자격", "우대사항", "혜택", "복지"]
        )

        new_row["정제자격요건"] = extract_section(
            clean_text,
            ["자격요건", "지원자격", "필수요건"],
            ["우대사항", "혜택", "복지", "채용절차"]
        )

        new_row["정제우대사항"] = extract_section(
            clean_text,
            ["우대사항", "우대조건"],
            ["혜택", "복지", "채용절차"]
        )

        new_row["정제요약"] = make_summary(new_row)

        refined_rows.append(new_row)

    preferred_fields = [
        "정제제목",
        "정제회사명",
        "정제지역",
        "정제경력",
        "정제연봉",
        "정제근무형태",
        "재택근무",
        "교대근무",
        "정제키워드",
        "정제요약",
        "정제주요업무",
        "정제자격요건",
        "정제우대사항",
        "URL",
        "수집일시"
    ]

    fieldnames = preferred_fields + [
        field for field in original_fields if field not in preferred_fields
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(refined_rows)

    print(f"정제 완료: {OUTPUT_FILE}")
    print(f"총 공고 수: {len(refined_rows)}")


if __name__ == "__main__":
    main()