from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import barriers, chat, comparison, countries, gaps, overview

app = FastAPI(
    title="Hallyu Potential Tourist Dashboard API",
    description=(
        "CSV(data/processed/) 기반 서비스 데이터 레이어. "
        "final_analysis_framework.md / dashboard_data_dictionary.md에 정의된 값을 "
        "그대로 조회/조합해 제공하며, 새로운 통계를 계산하지 않는다."
    ),
    version="0.1.0",
)

# 향후 Next.js 대시보드(dev 서버) 연동을 위한 개방적 CORS 설정.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(overview.router)
app.include_router(countries.router)
app.include_router(gaps.router)
app.include_router(barriers.router)
app.include_router(comparison.router)
app.include_router(chat.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
