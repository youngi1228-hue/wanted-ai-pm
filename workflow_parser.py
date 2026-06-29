from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

sample_text = """
애자일소다

AI 프로젝트 매니저

주요업무
- AI 서비스 기획
- 개발자 협업

자격요건
- PM 경력 3년 이상

우대사항
- LLM 경험
"""

prompt = f"""
다음 채용공고를 JSON으로 변환해라.

필드:
회사명
직무명
주요업무
자격요건
우대사항

채용공고:
{sample_text}
"""

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ],
    response_format={"type": "json_object"}
)

print(response.choices[0].message.content)