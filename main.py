from nicegui import ui
import csv
import json
from datetime import datetime
from pathlib import Path


RESUME_FILE = Path("resume.json")
JOBS_FILE = Path("wanted_jobs_refined.csv")


# --------------------------------------------------
# 공통 함수
# --------------------------------------------------

def clean_text(value):
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in ["nan", "none"]:
        return ""

    # Markdown 이스케이프 문자 제거
    return text.replace("\\", "")


def normalize_url(value):
    url = clean_text(value)

    if url.startswith("www."):
        url = "https://" + url

    if url.startswith(("http://", "https://")):
        return url

    return ""


def split_values(value):
    if isinstance(value, list):
        return [
            clean_text(item)
            for item in value
            if clean_text(item)
        ]

    text = clean_text(value)

    if not text:
        return []

    return [
        item.strip()
        for item in text.split(",")
        if item.strip()
    ]


def load_resume():
    if not RESUME_FILE.exists():
        return {}

    try:
        with open(RESUME_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError):
        return {}


def save_resume(data):
    with open(RESUME_FILE, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_jobs():
    if not JOBS_FILE.exists():
        return []

    with open(
        JOBS_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        reader = csv.DictReader(file)
        return list(reader)


def get_job_value(job, refined_key, original_key):
    refined_value = clean_text(job.get(refined_key))
    original_value = clean_text(job.get(original_key))

    return refined_value or original_value or "비공개"


def make_display_row(job):
    return {
        "제목": get_job_value(
            job,
            "정제제목",
            "제목"
        ),
        "회사명": get_job_value(
            job,
            "정제회사명",
            "회사명"
        ),
        "지역": get_job_value(
            job,
            "정제지역",
            "지역"
        ),
        "경력": get_job_value(
            job,
            "정제경력",
            "경력"
        ),
        "연봉": get_job_value(
            job,
            "정제연봉",
            "연봉"
        ),
        "근무형태": get_job_value(
            job,
            "정제근무형태",
            "근무형태"
        ),
        "재택근무": clean_text(
            job.get("재택근무")
        ) or "비공개",
        "교대근무": clean_text(
            job.get("교대근무")
        ) or "비공개",
        "키워드": get_job_value(
            job,
            "정제키워드",
            "키워드"
        ),
        "URL": normalize_url(
            job.get("URL")
        )
    }


def calculate_score(
    job,
    resume,
    preferred_region,
    keyword_filter,
    exclude_shift,
    prefer_remote
):
    job_text = " ".join(
        clean_text(value)
        for value in job.values()
    ).lower()

    score = 0
    matched = []

    resume_keywords = [
        resume.get("희망직무", ""),
        resume.get("희망지역", ""),
        *split_values(
            resume.get("보유자격증", [])
        ),
        *split_values(
            resume.get("보유역량", [])
        )
    ]

    for keyword in resume_keywords:
        keyword = clean_text(keyword)

        if keyword and keyword.lower() in job_text:
            score += 10
            matched.append(keyword)

    for region in split_values(preferred_region):
        if region.lower() in job_text:
            score += 20
            matched.append(f"지역:{region}")

    for keyword in split_values(keyword_filter):
        if keyword.lower() in job_text:
            score += 15
            matched.append(f"키워드:{keyword}")

    shift_value = clean_text(
        job.get("교대근무")
    ).lower()

    if exclude_shift and (
        shift_value == "예"
        or "2교대" in job_text
        or "3교대" in job_text
        or "주야간" in job_text
    ):
        score -= 50
        matched.append("교대근무 제외")

    remote_value = clean_text(
        job.get("재택근무")
    ).lower()

    if prefer_remote and (
        remote_value == "예"
        or "재택" in job_text
        or "remote" in job_text
        or "하이브리드" in job_text
    ):
        score += 10
        matched.append("재택근무")

    score = max(0, min(100, score))
    matched = list(dict.fromkeys(matched))

    return score, matched


def show_job_table(rows, include_score=False):
    table_rows = []

    for index, row in enumerate(rows):
        new_row = dict(row)
        new_row["_row_id"] = index
        table_rows.append(new_row)

    fields = []

    if include_score:
        fields.extend([
            "매칭점수",
            "매칭키워드"
        ])

    fields.extend([
        "제목",
        "회사명",
        "지역",
        "경력",
        "연봉",
        "근무형태",
        "재택근무",
        "교대근무",
        "키워드",
        "URL"
    ])

    columns = []

    for field in fields:
        columns.append({
            "name": field,
            "label": (
                "공고 링크"
                if field == "URL"
                else field
            ),
            "field": field,
            "align": "left",
            "sortable": field != "URL"
        })

    table = ui.table(
        columns=columns,
        rows=table_rows,
        row_key="_row_id"
    ).classes("w-full")

    table.props(
        "flat bordered wrap-cells"
    )

    # URL을 클릭 가능한 링크로 표시
    table.add_slot(
        "body-cell-URL",
        """
        <q-td :props="props">
            <a
                v-if="props.value"
                :href="props.value"
                target="_blank"
                rel="noopener noreferrer"
                class="text-primary text-weight-medium"
            >
                공고 보기
            </a>

            <span v-else>
                링크 없음
            </span>
        </q-td>
        """
    )


# --------------------------------------------------
# 앱 화면
# --------------------------------------------------

saved_resume = load_resume()

ui.label(
    "커리어 에이전트 MVP"
).classes(
    "text-3xl font-bold"
)

ui.label(
    "이력서 작성부터 채용공고 조회와 맞춤 추천까지 제공합니다."
).classes(
    "text-gray-600"
)


with ui.tabs().classes("w-full") as tabs:
    resume_tab = ui.tab(
        "1. 이력서 작성"
    )

    jobs_tab = ui.tab(
        "2. 채용공고 조회"
    )

    recommend_tab = ui.tab(
        "3. 맞춤 공고 추천"
    )


with ui.tab_panels(
    tabs,
    value=resume_tab
).classes("w-full"):

    # --------------------------------------------------
    # 1. 이력서 작성
    # --------------------------------------------------

    with ui.tab_panel(resume_tab):
        ui.label(
            "이력서 작성"
        ).classes(
            "text-2xl font-semibold"
        )

        with ui.card().classes("w-full"):
            name_input = ui.input(
                "이름",
                value=clean_text(
                    saved_resume.get("이름")
                )
            ).classes("w-full")

            target_job_input = ui.input(
                "희망 직무",
                value=clean_text(
                    saved_resume.get("희망직무")
                )
            ).classes("w-full")

            location_input = ui.input(
                "희망 지역",
                value=clean_text(
                    saved_resume.get("희망지역")
                )
            ).classes("w-full")

            career_input = ui.textarea(
                "경력 사항",
                value=clean_text(
                    saved_resume.get("경력사항")
                )
            ).classes("w-full")

            certificates_input = ui.input(
                "보유 자격증",
                value=", ".join(
                    split_values(
                        saved_resume.get(
                            "보유자격증",
                            []
                        )
                    )
                ),
                placeholder="예: 정보처리기사, SQLD"
            ).classes("w-full")

            skills_input = ui.input(
                "보유 역량/기술",
                value=", ".join(
                    split_values(
                        saved_resume.get(
                            "보유역량",
                            []
                        )
                    )
                ),
                placeholder="예: 기획, 데이터 분석, 커뮤니케이션"
            ).classes("w-full")

            introduction_input = ui.textarea(
                "자기소개",
                value=clean_text(
                    saved_resume.get("자기소개")
                )
            ).classes("w-full")

        resume_preview = ui.column().classes(
            "w-full"
        )

        def render_resume_preview():
            resume_preview.clear()

            with resume_preview:
                data = load_resume()

                if not data:
                    ui.label(
                        "저장된 이력서가 없습니다."
                    ).classes(
                        "text-gray-500"
                    )
                    return

                ui.label(
                    "저장된 이력서"
                ).classes(
                    "text-xl font-semibold"
                )

                ui.markdown(
                    "```json\n"
                    + json.dumps(
                        data,
                        ensure_ascii=False,
                        indent=2
                    )
                    + "\n```"
                ).classes("w-full")

        def handle_save_resume():
            data = {
                "이름": clean_text(
                    name_input.value
                ),
                "희망직무": clean_text(
                    target_job_input.value
                ),
                "희망지역": clean_text(
                    location_input.value
                ),
                "경력사항": clean_text(
                    career_input.value
                ),
                "보유자격증": split_values(
                    certificates_input.value
                ),
                "보유역량": split_values(
                    skills_input.value
                ),
                "자기소개": clean_text(
                    introduction_input.value
                ),
                "저장일시": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

            save_resume(data)

            preferred_region_input.value = (
                data["희망지역"]
            )

            keyword_filter_input.value = (
                data["희망직무"]
            )

            render_resume_preview()

            ui.notify(
                "이력서를 저장했습니다.",
                type="positive"
            )

        ui.button(
            "이력서 저장",
            on_click=handle_save_resume,
            icon="save"
        )

        render_resume_preview()

    # --------------------------------------------------
    # 2. 채용공고 조회
    # --------------------------------------------------

    with ui.tab_panel(jobs_tab):
        ui.label(
            "채용공고 조회"
        ).classes(
            "text-2xl font-semibold"
        )

        with ui.row().classes(
            "w-full items-end"
        ):
            search_input = ui.input(
                "공고 검색어",
                placeholder=(
                    "제목, 회사명, 지역, "
                    "기술 등을 검색"
                )
            ).classes("grow")

            search_button = ui.button(
                "검색",
                icon="search"
            )

        jobs_area = ui.column().classes(
            "w-full"
        )

        def render_jobs():
            jobs_area.clear()

            jobs = load_jobs()
            keyword = clean_text(
                search_input.value
            ).lower()

            if keyword:
                jobs = [
                    job
                    for job in jobs
                    if keyword in " ".join(
                        clean_text(value)
                        for value in job.values()
                    ).lower()
                ]

            with jobs_area:
                if not JOBS_FILE.exists():
                    ui.label(
                        "wanted_jobs_refined.csv "
                        "파일이 없습니다."
                    ).classes(
                        "text-negative"
                    )
                    return

                ui.label(
                    f"검색 결과: {len(jobs)}개"
                ).classes(
                    "text-lg font-medium"
                )

                show_job_table([
                    make_display_row(job)
                    for job in jobs
                ])

        search_button.on(
            "click",
            render_jobs
        )

        search_input.on(
            "keydown.enter",
            render_jobs
        )

        render_jobs()

    # --------------------------------------------------
    # 3. 맞춤 공고 추천
    # --------------------------------------------------

    with ui.tab_panel(recommend_tab):
        ui.label(
            "맞춤 공고 추천"
        ).classes(
            "text-2xl font-semibold"
        )

        with ui.card().classes("w-full"):
            preferred_region_input = ui.input(
                "희망 지역",
                value=clean_text(
                    saved_resume.get("희망지역")
                ),
                placeholder="예: 서울, 경기"
            ).classes("w-full")

            keyword_filter_input = ui.input(
                "포함할 키워드",
                value=clean_text(
                    saved_resume.get("희망직무")
                ),
                placeholder="예: AI PM, 서비스 기획"
            ).classes("w-full")

            exclude_shift_input = ui.checkbox(
                "교대근무 제외",
                value=True
            )

            prefer_remote_input = ui.checkbox(
                "재택근무 선호",
                value=False
            )

            minimum_score_input = ui.number(
                "최소 매칭 점수",
                value=10,
                min=0,
                max=100,
                step=10
            )

            recommend_button = ui.button(
                "추천 결과 보기",
                icon="recommend"
            )

        recommendation_area = ui.column().classes(
            "w-full"
        )

        def render_recommendations():
            recommendation_area.clear()

            resume = load_resume()
            jobs = load_jobs()

            with recommendation_area:
                if not resume:
                    ui.label(
                        "먼저 1번 탭에서 "
                        "이력서를 저장하세요."
                    ).classes(
                        "text-negative"
                    )
                    return

                minimum_score = int(
                    minimum_score_input.value or 0
                )

                results = []

                for job in jobs:
                    score, matched = calculate_score(
                        job,
                        resume,
                        preferred_region_input.value,
                        keyword_filter_input.value,
                        exclude_shift_input.value,
                        prefer_remote_input.value
                    )

                    if score < minimum_score:
                        continue

                    row = make_display_row(job)

                    row["매칭점수"] = score
                    row["매칭키워드"] = ", ".join(
                        matched
                    )
                    row["_원본"] = job

                    results.append(row)

                results.sort(
                    key=lambda row: row["매칭점수"],
                    reverse=True
                )

                ui.label(
                    f"추천 공고 수: {len(results)}개"
                ).classes(
                    "text-lg font-medium"
                )

                table_rows = [
                    {
                        key: value
                        for key, value in row.items()
                        if key != "_원본"
                    }
                    for row in results
                ]

                show_job_table(
                    table_rows,
                    include_score=True
                )

                ui.separator()

                ui.label(
                    "추천 공고 TOP 5"
                ).classes(
                    "text-xl font-semibold"
                )

                for row in results[:5]:
                    original = row["_원본"]

                    with ui.expansion(
                        (
                            f"{row['매칭점수']}점 | "
                            f"{row['제목']}"
                        ),
                        icon="work"
                    ).classes("w-full"):

                        ui.label(
                            f"회사명: {row['회사명']}"
                        )
                        ui.label(
                            f"지역: {row['지역']}"
                        )
                        ui.label(
                            f"경력: {row['경력']}"
                        )
                        ui.label(
                            f"연봉: {row['연봉']}"
                        )
                        ui.label(
                            f"근무형태: {row['근무형태']}"
                        )
                        ui.label(
                            f"재택근무: {row['재택근무']}"
                        )
                        ui.label(
                            f"교대근무: {row['교대근무']}"
                        )
                        ui.label(
                            "매칭키워드: "
                            + row["매칭키워드"]
                        )

                        if row["URL"]:
                            ui.link(
                                "원티드 공고 열기",
                                row["URL"],
                                new_tab=True
                            ).classes(
                                "text-primary font-medium"
                            )

                        ui.label(
                            "주요업무"
                        ).classes(
                            "text-lg font-semibold"
                        )

                        ui.label(
                            get_job_value(
                                original,
                                "정제주요업무",
                                "주요업무"
                            )
                        ).classes(
                            "whitespace-pre-wrap"
                        )

                        ui.label(
                            "자격요건"
                        ).classes(
                            "text-lg font-semibold"
                        )

                        ui.label(
                            get_job_value(
                                original,
                                "정제자격요건",
                                "자격요건"
                            )
                        ).classes(
                            "whitespace-pre-wrap"
                        )

                        ui.label(
                            "우대사항"
                        ).classes(
                            "text-lg font-semibold"
                        )

                        ui.label(
                            get_job_value(
                                original,
                                "정제우대사항",
                                "우대사항"
                            )
                        ).classes(
                            "whitespace-pre-wrap"
                        )

        recommend_button.on(
            "click",
            render_recommendations
        )

        render_recommendations()


ui.run(
    title="커리어 에이전트 MVP",
    port=8080,
    reload=False
)