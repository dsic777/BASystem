"""실행 엔트리.

    python main.py                  빈 당구대에서 시작
    python main.py C:\\sc\\5.jpg      캡처 사진에서 공 위치를 읽어 배치
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui.app import run  # noqa: E402

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
