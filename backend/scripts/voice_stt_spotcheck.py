"""STT accuracy spot-check for the voice session log Phase 2 gate.

Run against real therapist audio samples (Indian-accented English and
code-switched speech) before enabling a provider on staging:

    cd backend
    AI_ENABLED=true VOICE_STT_PROVIDER=openai OPENAI_API_KEY=sk-... \
        python3 -m scripts.voice_stt_spotcheck sample1.webm sample2.m4a

Prints transcript, language, provider/model, and processing time per file so
a clinical reviewer can judge accuracy against what was actually said.
"""

from __future__ import annotations

import mimetypes
import sys
from pathlib import Path

from app.services.voice_transcription_service import transcribe_audio_bytes


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 1
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            print(f"-- {path}: not found, skipping")
            continue
        mime = mimetypes.guess_type(path.name)[0] or "audio/webm"
        result = transcribe_audio_bytes(path.read_bytes(), mime)
        print(f"\n=== {path.name} ===")
        print(f"provider={result.provider} model={result.model} language={result.language} time={result.processing_ms}ms")
        print(result.transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
