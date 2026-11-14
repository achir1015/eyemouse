"""產生台灣華語語音（edge-tts 曉臻）：python tools/gen_voice.py [--force]"""
import asyncio
import importlib.util
import os
import sys

import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "voice")
VOICE = "zh-TW-HsiaoChenNeural"

spec = importlib.util.spec_from_file_location("texts", os.path.join(ROOT, "app", "texts.py"))
texts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(texts)


async def one(name, text, force):
    p = os.path.join(OUT, f"{name}.mp3")
    if os.path.exists(p) and not force:
        return
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, VOICE, rate="-5%").save(p)
            print("ok", name)
            return
        except Exception as e:  # noqa: BLE001
            print("retry", name, e)
            await asyncio.sleep(2)
    raise SystemExit(f"failed {name}")


async def main():
    os.makedirs(OUT, exist_ok=True)
    force = "--force" in sys.argv
    jobs = list(texts.VOICE.items()) + [(f"tut_{k}", t) for k, _, t in texts.TUTORIAL]
    for name, text in jobs:
        await one(name, text, force)


asyncio.run(main())
