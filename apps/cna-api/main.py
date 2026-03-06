from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CNA API", version="0.1.0")


class IntakeRequest(BaseModel):
    engagement_id: str
    source_type: str
    artifact_uri: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "cna-api"}


@app.post("/intake")
def intake(request: IntakeRequest) -> dict:
    return {
        "status": "accepted",
        "engagement_id": request.engagement_id,
        "source_type": request.source_type,
        "artifact_uri": request.artifact_uri,
    }
