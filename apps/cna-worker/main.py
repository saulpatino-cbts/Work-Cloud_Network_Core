from pathlib import Path


def main() -> None:
    work_dir = Path("/tmp/cna-worker")
    work_dir.mkdir(parents=True, exist_ok=True)
    print("cna-worker bootstrap ready")
    print(f"work_dir={work_dir}")


if __name__ == "__main__":
    main()
