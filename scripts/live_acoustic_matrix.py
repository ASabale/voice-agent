"""Live acoustic matrix: plays clips through the speakers into the real mic and
judges the controller only by its log and by the text that lands in TextEdit.

Run from the omp python venv. Uses the launchd controller's stdout log.
"""
import json, os, subprocess, sys, time
from pathlib import Path

D = Path(__file__).resolve().parents[1] / ".local" / "live-2026-11-21"
LOG = Path.home() / ".local/state/omp-voice/controller-restart.log"
STATUS = Path.home() / ".local/state/omp-voice/status.json"


def osa(s: str) -> str:
    return subprocess.run(["osascript", "-e", s], capture_output=True, text=True).stdout.strip()


def set_volume(v: int) -> None:
    osa(f"set volume output volume {v}")


def play(name: str) -> None:
    subprocess.run(["afplay", str(D / f"{name}.wav")], check=False)


def mark() -> int:
    return LOG.stat().st_size


def since(m: int) -> list[str]:
    with LOG.open("rb") as f:
        f.seek(m)
        return f.read().decode("utf-8", "replace").splitlines()


def state() -> str:
    try:
        return json.loads(STATUS.read_text())["controller"]["state"]
    except Exception:
        return "?"


def doc_text() -> str:
    return osa('tell application "TextEdit" to get text of document 1')


def reset_doc() -> None:
    osa('tell application "TextEdit" to set text of document 1 to ""')
    osa('tell application "TextEdit" to activate')
    time.sleep(0.5)


def footprint(pattern: str) -> float:
    pids = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
    best = 0.0
    for p in pids:
        out = subprocess.run(["footprint", "-p", p], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if "phys_footprint:" in line:
                val, unit = line.split(":")[1].split()[:2]
                mb = float(val) * {"KB": 1 / 1024, "MB": 1, "GB": 1024}.get(unit, 1)
                best = max(best, mb)
    return round(best, 1)


def mem() -> dict:
    return {"handy_mb": footprint("Handy.app/Contents/MacOS/handy"), "voicebox_mb": footprint("voicebox-server")}


def has(lines, needle):
    return [l for l in lines if needle in l]


def wait_idle(timeout=25):
    t = time.time()
    while time.time() - t < timeout and state() != "IDLE":
        time.sleep(0.5)
    return state()


def dictation_round(vol: int) -> dict:
    r = {"volume": vol}
    set_volume(vol)
    reset_doc()
    wait_idle()
    m = mark()
    play("wake"); time.sleep(2.5)
    r["woke"] = bool(has(since(m), "Wake triggered"))
    r["state_after_wake"] = state()
    play("dict1"); time.sleep(8)
    r["text_after_dict1"] = doc_text()
    play("scratch"); time.sleep(5)
    r["text_after_scratch"] = doc_text()
    play("dict2"); time.sleep(8)
    r["text_after_dict2"] = doc_text()
    play("pause"); time.sleep(5)
    r["state_after_pause"] = state()
    r["text_final"] = doc_text()
    r["log"] = [l[22:160] for l in since(m) if any(k in l for k in ("Wake", "Handy transcribed", "outcome", "Paused", "Partial written", "closed", "missing", "Draft "))]
    return r


def ambient_round(vol: int, clips: list[str]) -> dict:
    set_volume(vol)
    wait_idle()
    m = mark()
    for c in clips:
        play(c)
    time.sleep(3)
    lines = since(m)
    return {"volume": vol, "clips": clips, "false_wakes": [l[22:150] for l in has(lines, "Wake triggered")],
            "submits": [l[22:150] for l in has(lines, "Standalone")]}


if __name__ == "__main__":
    mode = sys.argv[1]
    out = {"mem_before": mem()}
    if mode == "dictation":
        out["rounds"] = [dictation_round(v) for v in (25, 50, 80)]
    elif mode == "ambient":
        out["rounds"] = [ambient_round(v, ["yt_talk", "chatter", "yt_jarvis"]) for v in (25, 50, 80)]
    out["mem_after"] = mem()
    out["volume_restored"] = 56
    set_volume(56)
    print(json.dumps(out, indent=1))
