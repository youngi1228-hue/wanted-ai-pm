import json
import html
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import streamlit as st
from dotenv import load_dotenv


st.set_page_config(
    page_title="커리어 에이전트",
    layout="wide",
)

ENV_FILE = ".env"

load_dotenv(ENV_FILE)


def normalize_url(value):
    url = str(value or "").strip()

    if not url or url.lower() in ["nan", "none"]:
        return ""

    if url.startswith("www."):
        url = "https://" + url

    if not url.startswith(("http://", "https://")):
        return ""

    return url


def get_secret(name, default=""):
    value = os.getenv(name)
    if value:
        return value

    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(email or "").strip()))


def display_value(job, field):
    value = clean_text(job.get(field, ""))
    return value or DISPLAY_DEFAULTS.get(field, "")


def build_jobs_email_html(jobs, conditions, search_time):
    desired_job = clean_text(conditions.get("desired_job", "")) or "입력 없음"
    desired_location = clean_text(conditions.get("desired_location", "")) or "입력 없음"
    minimum_salary = clean_text(conditions.get("minimum_salary", "")) or "입력 없음"

    cards = []
    for index, job in enumerate(jobs, start=1):
        url = normalize_url(job["url"])
        reason = " ".join(job.get("reasons", []))
        summary = clean_text(job.get("summary", ""))
        escaped_url = html.escape(url)

        cards.append(
            f"""
            <div style="border:1px solid #e5e7eb;border-radius:8px;padding:18px;margin:0 0 16px;background:#ffffff;">
                <div style="font-size:13px;color:#6b7280;margin-bottom:6px;">추천 {index}</div>
                <h2 style="font-size:20px;line-height:1.35;margin:0 0 12px;color:#111827;">
                    {html.escape(display_value(job, "title"))}
                </h2>
                <table style="width:100%;border-collapse:collapse;font-size:14px;color:#374151;">
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">회사명</td><td>{html.escape(display_value(job, "company"))}</td></tr>
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">지역</td><td>{html.escape(display_value(job, "location"))}</td></tr>
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">경력</td><td>{html.escape(display_value(job, "career"))}</td></tr>
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">연봉</td><td>{html.escape(display_value(job, "salary"))}</td></tr>
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">근무형태</td><td>{html.escape(display_value(job, "employment_type"))}</td></tr>
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">추천 이유</td><td>{html.escape(reason)}</td></tr>
                    <tr><td style="width:90px;padding:4px 0;color:#6b7280;">공고 설명</td><td>{html.escape(summary)}</td></tr>
                </table>
                <div style="margin-top:14px;">
                    <a href="{escaped_url}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:6px;font-size:14px;">
                        원티드에서 공고 보기
                    </a>
                </div>
            </div>
            """
        )

    return f"""
    <!doctype html>
    <html lang="ko">
    <body style="margin:0;padding:24px;background:#f9fafb;font-family:Arial,'Malgun Gothic',sans-serif;">
        <div style="max-width:720px;margin:0 auto;">
            <h1 style="font-size:24px;line-height:1.35;margin:0 0 18px;color:#111827;">
                맞춤 공고 추천 결과
            </h1>
            <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:0 0 18px;background:#ffffff;color:#374151;font-size:14px;">
                <div style="margin-bottom:6px;"><strong>희망 직무</strong>: {html.escape(desired_job)}</div>
                <div style="margin-bottom:6px;"><strong>희망 지역</strong>: {html.escape(desired_location)}</div>
                <div style="margin-bottom:6px;"><strong>최소 희망연봉</strong>: {html.escape(minimum_salary)}</div>
                <div style="margin-bottom:6px;"><strong>검색 일시</strong>: {html.escape(search_time or "확인 필요")}</div>
                <div style="color:#6b7280;">Wanted 실시간 검색 결과를 기준으로 추천된 채용공고입니다.</div>
            </div>
            {''.join(cards)}
        </div>
    </body>
    </html>
    """


def send_jobs_email(recipient_email, jobs, conditions, search_time):
    sender_email = get_secret("SMTP_EMAIL").strip()
    smtp_app_password = get_secret("SMTP_APP_PASSWORD").replace(" ", "")
    app_password = re.sub(r"\s+", "", smtp_app_password)

    if not sender_email or not app_password:
        raise ValueError("이메일 발송 설정이 완료되지 않았습니다.")

    desired_job = clean_text(conditions.get("desired_job", "")) or "희망 직무"

    message = MIMEMultipart("alternative")
    message["Subject"] = f"[맞춤 공고 추천] {desired_job} 채용공고 결과"
    message["From"] = sender_email
    message["To"] = recipient_email
    message.attach(MIMEText("맞춤 채용공고 추천 결과를 HTML 이메일로 확인해주세요.", "plain", "utf-8"))
    message.attach(MIMEText(build_jobs_email_html(jobs, conditions, search_time), "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender_email, app_password)
        smtp.sendmail(sender_email, [recipient_email], message.as_string())


def send_to_activepieces(webhook_url, resume_pdf, conditions):
    files = None
    if resume_pdf is not None:
        files = {
            "resume_pdf": (
                resume_pdf.name,
                resume_pdf.getvalue(),
                "application/pdf",
            )
        }

    data = {
        "conditions": json.dumps(conditions, ensure_ascii=False),
    }

    for key, value in conditions.items():
        data[key] = str(value)

    response = requests.post(
        webhook_url,
        data=data,
        files=files,
        timeout=40,
    )
    response.raise_for_status()

    return {
        "status_code": response.status_code,
        "json": response.json(),
    }


def get_response_body(response_json):
    if not isinstance(response_json, dict):
        return {}

    body = response_json.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {}

    return body if isinstance(body, dict) else {}


def get_raw_jobs(response_json):
    if not isinstance(response_json, dict):
        return []

    body = get_response_body(response_json)
    jobs = body.get("jobs")

    if jobs is None:
        jobs = response_json.get("jobs")

    return jobs if isinstance(jobs, list) else []


JOB_FIELDS = [
    "title",
    "company",
    "location",
    "career",
    "salary",
    "employment_type",
    "keywords",
    "summary",
    "duties",
    "requirements",
    "preferred",
    "url",
]

DISPLAY_DEFAULTS = {
    "company": "회사명 상세 확인 필요",
    "location": "지역 상세 확인 필요",
    "career": "경력 상세 확인 필요",
    "salary": "확인 필요",
    "employment_type": "근무형태 상세 확인 필요",
}


def clean_text(value):
    text = str(value or "").strip()
    return "" if text.lower() in ["nan", "none", "null"] else text


def normalize_flat_job(raw_job):
    job = {}
    for field in JOB_FIELDS:
        value = clean_text(raw_job.get(field, ""))
        job[field] = DISPLAY_DEFAULTS.get(field, "") if not value else value

    return job


def extract_jobs(response_json):
    raw_jobs = get_raw_jobs(response_json)
    jobs = [
        normalize_flat_job(raw_job)
        for raw_job in raw_jobs
        if isinstance(raw_job, dict)
    ]
    return raw_jobs, jobs


def split_job_keywords(desired_job):
    keywords = [
        keyword.strip().lower()
        for keyword in str(desired_job).split(",")
        if keyword.strip()
    ]

    expanded_keywords = []
    for keyword in keywords:
        expanded_keywords.append(keyword)
        normalized = keyword.replace(" ", "")
        if normalized in ["aipm", "ai프로덕트매니저", "ai서비스기획"]:
            expanded_keywords.extend([
                "ai",
                "pm",
                "서비스 기획",
                "서비스기획",
                "프로덕트 매니저",
                "프로덕트매니저",
                "product manager",
                "productmanager",
            ])

    return list(dict.fromkeys(expanded_keywords))


def parse_minimum_salary(minimum_salary):
    numbers = re.findall(r"\d+", str(minimum_salary).replace(",", ""))
    if not numbers:
        return None
    return int(numbers[0])


def parse_salary_to_manwon(salary):
    text = str(salary or "").replace(",", "").strip().lower()

    if not text or "비공개" in text:
        return None

    cheon_match = re.search(r"(\d+(?:\.\d+)?)\s*천\s*만\s*원?", text)
    if cheon_match:
        return int(float(cheon_match.group(1)) * 1000)

    won_match = re.search(r"(\d{7,})\s*원", text)
    if won_match:
        return int(int(won_match.group(1)) / 10000)

    number_match = re.search(r"\d+", text)
    if not number_match:
        return None

    number = int(number_match.group())
    if number >= 100000:
        return int(number / 10000)
    return number


def contains_any_keyword(text, keywords):
    text_value = str(text or "").lower()
    compact_text_value = text_value.replace(" ", "")
    return [
        keyword
        for keyword in keywords
        if keyword in text_value or keyword.replace(" ", "") in compact_text_value
    ]


def matches_desired_job(job, keywords):
    if not keywords:
        return True, {}

    fields = {
        "title": "제목",
        "summary": "설명",
    }
    matches = {}
    for field, label in fields.items():
        field_matches = contains_any_keyword(job[field], keywords)
        if field_matches:
            matches[label] = field_matches

    return bool(matches), matches


def matches_desired_location(job, desired_location):
    location = str(desired_location or "").strip().lower()
    if not location:
        return True

    job_location = str(job["location"] or "").lower()
    if not job_location or job_location == DISPLAY_DEFAULTS["location"].lower():
        return True

    compact_location = location.replace(" ", "")
    compact_job_location = job_location.replace(" ", "")
    return location in job_location or compact_location in compact_job_location


def meets_minimum_salary(job, minimum_salary):
    minimum_salary_value = parse_minimum_salary(minimum_salary)
    if minimum_salary_value is None:
        return True, False

    job_salary_value = parse_salary_to_manwon(job["salary"])
    if job_salary_value is None:
        return True, True

    return job_salary_value >= minimum_salary_value, False


def has_required_display_fields(job):
    return bool(job["title"] and normalize_url(job["url"]))


def score_job(job, desired_job, desired_location, minimum_salary):
    if not has_required_display_fields(job):
        return None

    keywords = split_job_keywords(desired_job)
    score = 0
    reasons = []

    job_matched, job_matches = matches_desired_job(job, keywords)
    location_matched = matches_desired_location(job, desired_location)
    salary_matched, _ = meets_minimum_salary(job, minimum_salary)

    if not job_matched or not location_matched or not salary_matched:
        return None

    if "제목" in job_matches:
        score += 70
        reasons.append("공고 제목에서 희망 직무 키워드가 확인되었습니다.")

    if "설명" in job_matches:
        score += 30
        reasons.append("공고 설명에서 희망 직무 키워드가 확인되었습니다.")

    if score <= 0:
        return None

    return {
        **job,
        "score": score,
        "reasons": reasons,
    }


def rank_jobs(jobs, desired_job, desired_location, minimum_salary):
    scored_jobs = []
    for job in jobs:
        scored_job = score_job(job, desired_job, desired_location, minimum_salary)
        if scored_job is not None:
            scored_jobs.append(scored_job)

    scored_jobs.sort(key=lambda job: job["score"], reverse=True)
    return scored_jobs[:5]


def render_debug_expander(status_code, response_json, raw_count, job_count):
    with st.expander("Activepieces 응답 확인"):
        st.write("HTTP 상태코드:", status_code if status_code is not None else "")
        st.write("추출된 jobs 개수:", raw_count)
        st.write("정규화 후 실제 공고 개수:", job_count)
        st.json(response_json if response_json is not None else {})


def render_job_results(response_json, desired_job, desired_location, minimum_salary):
    raw_jobs, jobs = extract_jobs(response_json)

    if not jobs:
        st.error("채용공고 데이터를 불러오지 못했습니다. Activepieces 응답을 확인해주세요.")
        st.session_state["displayed_jobs"] = []
        return raw_jobs, jobs

    ranked_jobs = rank_jobs(jobs, desired_job, desired_location, minimum_salary)
    st.session_state["displayed_jobs"] = ranked_jobs

    st.subheader("입력 조건에 맞는 채용공고")

    if not ranked_jobs:
        st.info("입력한 조건에 맞는 채용공고가 없습니다.")
        return raw_jobs, jobs

    for index, job in enumerate(ranked_jobs, start=1):
        with st.container(border=True):
            st.markdown(f"#### {index}. {job['title']}")
            st.write("회사명:", job["company"])
            st.write("지역:", job["location"])
            st.write("경력:", job["career"])
            st.write("연봉:", job["salary"])
            st.write("근무형태:", job["employment_type"])
            st.write("추천 점수:", f"{job['score']}점")
            st.write("추천 이유:", " ".join(job["reasons"]))

            url = normalize_url(job["url"])
            if url:
                st.link_button("공고 보기", url, use_container_width=True)

    return raw_jobs, jobs


st.title("커리어 에이전트")
st.header("맞춤 공고 추천")

webhook_default = get_secret("ACTIVEPIECES_WEBHOOK_URL")

if "activepieces_response_json" not in st.session_state:
    st.session_state["activepieces_response_json"] = None

if "activepieces_status_code" not in st.session_state:
    st.session_state["activepieces_status_code"] = None

if "activepieces_conditions" not in st.session_state:
    st.session_state["activepieces_conditions"] = {
        "desired_job": "",
        "desired_location": "",
        "minimum_salary": "",
    }

if "activepieces_search_time" not in st.session_state:
    st.session_state["activepieces_search_time"] = ""

if "displayed_jobs" not in st.session_state:
    st.session_state["displayed_jobs"] = []

if "email_sending" not in st.session_state:
    st.session_state["email_sending"] = False

if not webhook_default:
    st.warning(".env에 ACTIVEPIECES_WEBHOOK_URL을 설정해주세요.")

resume_pdf = st.file_uploader(
    "이력서 PDF",
    type=["pdf"],
    key="activepieces_resume_pdf",
)
recipient_email = st.text_input(
    "결과를 받을 이메일",
    value="",
    placeholder="예: name@example.com",
    key="recipient_email",
)
st.caption("현재 추천은 희망 조건과 채용공고를 기준으로 제공됩니다. 이력서 분석 기능은 추후 연결됩니다.")

with st.form("activepieces_webhook_form"):
    desired_job = st.text_input(
        "희망 직무",
        value="",
        placeholder="예: AI PM, 서비스 기획, Product Manager",
        key="activepieces_desired_job",
    )
    desired_location = st.text_input(
        "희망 지역",
        value="",
        placeholder="예: 서울",
        key="activepieces_desired_location",
    )
    minimum_salary = st.text_input(
        "최소 희망연봉(만원)",
        value="",
        placeholder="예: 4000",
        key="activepieces_minimum_salary",
    )

    submit_activepieces = st.form_submit_button(
        "조건에 맞는 공고 5건 찾기",
        use_container_width=True,
    )

if submit_activepieces:
    if not webhook_default.strip():
        st.error(".env에 ACTIVEPIECES_WEBHOOK_URL을 설정해주세요.")
    else:
        conditions = {
            "desired_job": desired_job.strip(),
            "desired_location": desired_location.strip(),
            "minimum_salary": minimum_salary.strip(),
        }

        with st.spinner("Activepieces Webhook으로 조회 조건을 전송 중입니다..."):
            try:
                response_payload = send_to_activepieces(
                    webhook_default.strip(),
                    resume_pdf,
                    conditions,
                )
                response_json = response_payload["json"]
                st.session_state["activepieces_status_code"] = response_payload["status_code"]
                st.session_state["activepieces_response_json"] = response_json
                st.session_state["activepieces_conditions"] = conditions
                st.session_state["activepieces_search_time"] = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                _, jobs = extract_jobs(response_json)
                if jobs:
                    st.success("채용공고 데이터를 불러왔습니다.")
            except requests.Timeout as exc:
                st.session_state["activepieces_status_code"] = None
                st.session_state["activepieces_response_json"] = None
                st.error(f"Activepieces 요청 시간이 초과되었습니다: {exc}")
            except requests.HTTPError as exc:
                st.session_state["activepieces_response_json"] = None
                response = exc.response
                status_code = response.status_code if response is not None else "알 수 없음"
                st.session_state["activepieces_status_code"] = status_code
                response_text = response.text if response is not None else ""
                st.error(f"Activepieces HTTP 오류가 발생했습니다. 상태 코드: {status_code}")
                if response_text:
                    st.code(response_text)
            except ValueError as exc:
                st.session_state["activepieces_status_code"] = None
                st.session_state["activepieces_response_json"] = None
                st.error(f"Activepieces 응답을 JSON으로 해석하지 못했습니다: {exc}")
            except requests.RequestException as exc:
                st.session_state["activepieces_status_code"] = None
                st.session_state["activepieces_response_json"] = None
                st.error(f"Activepieces 요청에 실패했습니다: {exc}")

response_json = st.session_state["activepieces_response_json"]
if response_json is not None:
    saved_conditions = st.session_state["activepieces_conditions"]
    raw_jobs, jobs = render_job_results(
        response_json,
        saved_conditions["desired_job"],
        saved_conditions["desired_location"],
        saved_conditions["minimum_salary"],
    )
    render_debug_expander(
        st.session_state["activepieces_status_code"],
        response_json,
        len(raw_jobs),
        len(jobs),
    )

displayed_jobs = st.session_state.get("displayed_jobs", [])
if displayed_jobs:
    if st.button(
        "검색 결과 이메일로 받기",
        use_container_width=True,
        disabled=st.session_state.get("email_sending", False),
    ):
        email_to = st.session_state.get("recipient_email", "").strip()
        smtp_email = get_secret("SMTP_EMAIL").strip()
        smtp_app_password = get_secret("SMTP_APP_PASSWORD").replace(" ", "")
        smtp_password = re.sub(r"\s+", "", smtp_app_password)

        if not is_valid_email(email_to):
            st.warning("올바른 이메일 주소를 입력해주세요.")
        elif not smtp_email or not smtp_password:
            st.error("이메일 발송 설정이 완료되지 않았습니다.")
        else:
            st.session_state["email_sending"] = True
            try:
                with st.spinner("채용공고 이메일을 발송하고 있습니다..."):
                    send_jobs_email(
                        email_to,
                        displayed_jobs[:5],
                        st.session_state["activepieces_conditions"],
                        st.session_state["activepieces_search_time"],
                    )
                st.success("입력한 이메일로 채용공고를 발송했습니다.")
            except Exception as exc:
                st.error("이메일 발송 중 오류가 발생했습니다.")
                with st.expander("오류 내용"):
                    st.exception(exc)
            finally:
                st.session_state["email_sending"] = False
