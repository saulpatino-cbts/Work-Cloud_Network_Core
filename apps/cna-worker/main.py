from pathlib import Path
from shutil import copyfile
import os


def bootstrap_workspace(base: Path) -> dict:
    directories = {
        "raw": base / "raw-artifacts",
        "normalized": base / "normalized-artifacts",
        "deliverables": base / "deliverables",
        "static_site": base / "static-site",
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return {key: str(value) for key, value in directories.items()}


def publish_placeholder(deliverables_dir: Path, static_site_dir: Path, engagement_id: str) -> Path:
    source = deliverables_dir / f"{engagement_id}-summary.html"
    source.write_text(f"<html><body><h1>{engagement_id}</h1><p>CNA publish placeholder</p></body></html>\n")
    target = static_site_dir / "index.html"
    copyfile(source, target)
    return target


def build_blob_target(engagement_id: str, filename: str) -> str:
    return f"engagements/{engagement_id}/{filename}"


def main() -> None:
    work_dir = Path("/tmp/cna-worker")
    work_dir.mkdir(parents=True, exist_ok=True)
    layout = bootstrap_workspace(work_dir)
    published = publish_placeholder(work_dir / "deliverables", work_dir / "static-site", "sample-engagement")
    blob_container = os.getenv("CNA_STORAGE_STATIC_CONTAINER", "static-site")
    blob_target = build_blob_target("sample-engagement", published.name)
    print("cna-worker bootstrap ready")
    print(f"layout={layout}")
    print(f"published={published}")
    print(f"blob_container={blob_container}")
    print(f"blob_target={blob_target}")


if __name__ == "__main__":
    main()
