from fastapi import FastAPI, HTTPException
from pathlib import Path
import subprocess
import sys
import csv
import json


app = FastAPI(
    title="Wanted AI PM API",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent

SCRAPER_FILE = BASE_DIR / "scraper.py"
CLEANER_FILE = BASE_DIR / "job_cleaner.py"
JOBS_FILE = BASE_DIR / "wanted_jobs_refined.csv"
RESUME_FILE = BASE_DIR / "resume.json"


def load_jobs():
    """정제된 채용공고 CSV를 읽습니다."""

    if not JOBS_FILE.exists():
        return []

    with open(
        JOBS_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        return list(csv.DictReader(file))


def load_resume():
    """저장된 이력서 JSON을 읽습니다."""

    if not RESUME_FILE.exists():
        return {}

    with open(
        RESUME_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def clean_value(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() in ["nan", "none"]:
        return ""

    return value


def split_keywords(value):
    if isinstance(value, list):
        return [
            clean_value(item)
            for item in value
            if clean_value(item)
        ]

    value = clean_value(value)

    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def calculate_score(job, resume):
    """이력서와 공고를 비교해 간단한 매칭 점수를 계산합니다."""

    job_text = " ".join(
        clean_value(value)
        for value in job.values()
    ).lower()

    resume_keywords = [
        clean_value(resume.get("희망직무")),
        clean_value(resume.get("희망지역")),
        *split_keywords(resume.get("보유자격증", [])),
        *split_keywords(resume.get("보유역량", []))
    ]

    score = 0
    matched_keywords = []

    for keyword in resume_keywords:
        if keyword and keyword.lower() in job_text:
            score += 10
            matched_keywords.append(keyword)

    score = min(score, 100)

    return score, list(dict.fromkeys(matched_keywords))


@app.get("/health")
def health_check():
    """API 서버가 정상적으로 실행 중인지 확인합니다."""

    return {
        "status": "ok",
        "message": "Python API 서버가 정상 실행 중입니다."
    }


@app.post("/jobs/refresh")
def refresh_jobs():
    """scraper.py와 job_cleaner.py를 순서대로 실행합니다."""

    if not SCRAPER_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="scraper.py 파일이 없습니다."
        )

    if not CLEANER_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="job_cleaner.py 파일이 없습니다."
        )

    try:
        subprocess.run(
            [sys.executable, str(SCRAPER_FILE)],
            cwd=BASE_DIR,
            check=True,
            timeout=600
        )

        subprocess.run(
            [sys.executable, str(CLEANER_FILE)],
            cwd=BASE_DIR,
            check=True,
            timeout=600
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="채용공고 수집 시간이 초과되었습니다."
        )

    except subprocess.CalledProcessError as error:
        raise HTTPException(
            status_code=500,
            detail=f"채용공고 갱신 중 오류가 발생했습니다: {error}"
        )

    jobs = load_jobs()

    return {
        "status": "success",
        "message": "채용공고 수집 및 정제가 완료되었습니다.",
        "job_count": len(jobs)
    }


@app.get("/jobs")
def get_jobs():
    """정제된 전체 채용공고를 반환합니다."""

    if not JOBS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "wanted_jobs_refined.csv 파일이 없습니다. "
                "/jobs/refresh를 먼저 실행하세요."
            )
        )

    jobs = load_jobs()

    return {
        "job_count": len(jobs),
        "jobs": jobs
    }


@app.post("/jobs/recommend")
def recommend_jobs():
    """resume.json을 기준으로 추천 공고를 반환합니다."""

    if not RESUME_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="resume.json 파일이 없습니다."
        )

    if not JOBS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="wanted_jobs_refined.csv 파일이 없습니다."
        )

    resume = load_resume()
    jobs = load_jobs()

    recommendations = []

    for job in jobs:
        score, matched_keywords = calculate_score(
            job,
            resume
        )

        result = {
            "매칭점수": score,
            "매칭키워드": matched_keywords,
            "제목": (
                clean_value(job.get("정제제목"))
                or clean_value(job.get("제목"))
                or "비공개"
            ),
            "회사명": (
                clean_value(job.get("정제회사명"))
                or clean_value(job.get("회사명"))
                or "비공개"
            ),
            "지역": (
                clean_value(job.get("정제지역"))
                or clean_value(job.get("지역"))
                or "비공개"
            ),
            "경력": (
                clean_value(job.get("정제경력"))
                or clean_value(job.get("경력"))
                or "비공개"
            ),
            "URL": clean_value(job.get("URL"))
        }

        recommendations.append(result)

    recommendations.sort(
        key=lambda item: item["매칭점수"],
        reverse=True
    )

    return {
        "recommendation_count": len(recommendations),
        "top_5": recommendations[:5],
        "recommendations": recommendations
    }