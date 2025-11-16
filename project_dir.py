import os
from pathlib import Path

# -------- 설정값 --------
ROOT_DIR = Path(".").resolve()  # 현재 폴더 기준 루트
OUTPUT_FILE = Path("project_dir.txt")

# 제외할 디렉토리들
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "node_modules",
    ".pytest_cache",
}

# 제외할 확장자들 (이미지, 바이너리 등)
EXCLUDE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".pdf", ".zip", ".tar", ".gz",
    ".db", ".sqlite", ".pyc",
}

MAX_FILE_CHARS = 20_000   # 파일 하나에서 최대 가져올 문자 수
MAX_TOTAL_CHARS = 300_000 # 전체 합산 최대 문자 수 (너무 크면 LLM이 못 받음)

# ------------------------


def should_skip_dir(path: Path) -> bool:
    """제외 디렉토리 규칙."""
    parts = set(path.parts)
    return any(d in parts for d in EXCLUDE_DIRS)


def should_skip_file(path: Path) -> bool:
    """제외 파일 규칙."""
    if path.suffix.lower() in EXCLUDE_EXTS:
        return True
    return False


def is_text_file(path: Path) -> bool:
    """간단한 방식으로 텍스트/바이너리 구분 (대충이면 충분)."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        # 널바이트가 있으면 대충 바이너리로 간주
        if b"\x00" in chunk:
            return False
        return True
    except Exception:
        return False


def main():
    total_chars = 0
    lines = []

    lines.append(f"# Project dump from: {ROOT_DIR}\n\n")

    for root, dirs, files in os.walk(ROOT_DIR):
        root_path = Path(root)

        # 제외 디렉토리 필터
        if should_skip_dir(root_path.relative_to(ROOT_DIR)):
            dirs[:] = []  # 이 디렉토리 아래는 더 안 내려감
            continue

        # 하위 탐색 시에도 제외 디렉토리 제거
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for filename in files:
            file_path = root_path / filename
            rel_path = file_path.relative_to(ROOT_DIR)

            if should_skip_file(file_path):
                continue
            if not is_text_file(file_path):
                continue

            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if not text.strip():
                continue

            # 파일 당 최대 길이 제한
            if len(text) > MAX_FILE_CHARS:
                text = text[:MAX_FILE_CHARS] + "\n\n...[TRUNCATED]...\n"

            block = []
            block.append("\n" + "=" * 80 + "\n")
            block.append(f"FILE: {rel_path}\n")
            block.append("=" * 80 + "\n\n")
            block.append(text)
            block.append("\n")

            block_str = "".join(block)

            # 전체 최대 길이 초과하면 중단
            if total_chars + len(block_str) > MAX_TOTAL_CHARS:
                lines.append(
                    "\n\n...[STOPPED: MAX_TOTAL_CHARS reached, remaining files omitted]...\n"
                )
                OUTPUT_FILE.write_text("".join(lines), encoding="utf-8")
                print(f"[+] Written (truncated) to {OUTPUT_FILE}")
                return

            lines.append(block_str)
            total_chars += len(block_str)

    OUTPUT_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"[+] Written to {OUTPUT_FILE} (total_chars={total_chars})")


if __name__ == "__main__":
    main()
