from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CNA API", version="0.1.0")


class IntakeRequest(BaseModel):
    engagement_id: str
    source_type: str
    artifact_uri: str | None = None


class PublishRequest(BaseModel):
    engagement_id: str
    artifact_path: str
    target_path: str


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


@app.post("/publish")
def publish(request: PublishRequest) -> dict:
    publish_root = Path("/tmp/cna-publish")
    publish_root.mkdir(parents=True, exist_ok=True)
    target = publish_root / request.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"published artifact placeholder for {request.engagement_id}\n")
    return {
        "status": "published",
        "engagement_id": request.engagement_id,
        "target_path": str(target),
    }
