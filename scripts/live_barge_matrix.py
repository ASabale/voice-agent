"""Live speak/barge matrix on a real isolated omp session (Flash-Next worker).

For each trial: ask for a long spoken reply, wait until VoiceBox audio plays,
then play a disturbance through the speakers and judge only by what really
happened: did afplay die (stopped), did later sentences of that reply keep
coming (stale speech), and what the controller logged.
"""
import json, os, pty, select, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / ".local" / "live-2026-11-21"
STATE = Path.home() / ".local/state/omp-voice"
LOG = STATE / "controller-restart.log"
SPEECH = STATE / "speech.log"
MODEL = "strata/qwen3.8-flash-next-q2_0"
PROMPT = "Explain in about 200 words, in plain spoken sentences with no lists, how a bicycle gear system works."


def osa(s):
    return subprocess.run(["osascript", "-e", s], capture_output=True, text=True).stdout.strip()


def start_omp():
    begun = time.time()
    master, slave = pty.openpty()
    proc = subprocess.Popen(["omp", "--model", MODEL], stdin=slave, stdout=slave, stderr=slave,
                            start_new_session=True, cwd=str(Path.home() / "Development"))
    os.close(slave)
    rec_path = STATE / "sessions" / f"{proc.pid}.json"
    deadline = time.time() + 40
    while time.time() < deadline:
        r, _, _ = select.select([master], [], [], 0.25)
        if r:
            try:
                os.read(master, 65536)
            except OSError:
                pass
        if rec_path.exists():
            return proc, json.loads(rec_path.read_text()), master
    raise SystemExit("omp session never registered")


def drain(master):
    while True:
        r, _, _ = select.select([master], [], [], 0)
        if not r:
            return
        try:
            os.read(master, 65536)
        except OSError:
            return


def post(port, text):
    subprocess.run(["curl", "-s", "-m", "5", "-X", "POST", f"http://127.0.0.1:{port}/transcript",
                    "-H", "Content-Type: application/json", "-d", json.dumps({"text": text})],
                   capture_output=True, check=False)


def slot(pid):
    try:
        return json.loads((STATE / "tts-playing" / f"{pid}.json").read_text())
    except Exception:
        return None


def playing(pid):
    s = slot(pid)
    if not s or not s.get("afplay_pid") or s.get("ended_at"):
        return False
    try:
        os.kill(int(s["afplay_pid"]), 0)
        return True
    except OSError:
        return False


def wait_playing(pid, master, timeout):
    t = time.time()
    while time.time() - t < timeout:
        drain(master)
        if playing(pid):
            return time.time()
        time.sleep(0.1)
    return None


def speech_events(pid, since):
    out = []
    for line in SPEECH.read_text(errors="replace").splitlines()[-600:]:
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("pid") not in (pid, None) and str(j.get("pid")) != str(pid):
            continue
        t = j.get("t") or j.get("at") or j.get("ts")
        try:
            t = float(t) if not isinstance(t, str) else time.mktime(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone * 0
        except Exception:
            t = None
        out.append({"t": t, "event": j.get("event"), "text": (j.get("text") or "")[:70], "reason": j.get("reason")})
    return out


def log_mark():
    return LOG.stat().st_size


def log_since(m):
    with LOG.open("rb") as f:
        f.seek(m)
        return [l[22:170] for l in f.read().decode("utf-8", "replace").splitlines()
                if any(k in l for k in ("barge", "Barge", "stop", "Stop", "Ignored", "Wake", "hold", "duck", "resume"))]


def trial(proc, rec, master, disturbance, volume):
    osa(f"set volume output volume {volume}")
    post(rec["port"], PROMPT)
    post(rec["port"], "send prompt")
    asked = time.time()
    onset = wait_playing(proc.pid, master, 300)
    r = {"disturbance": disturbance, "volume": volume, "first_audio_s": round(onset - asked, 1) if onset else None}
    if not onset:
        return r
    time.sleep(2.0)
    m = log_mark()
    played_at = time.time()
    subprocess.run(["afplay", str(D / f"{disturbance}.wav")], check=False)
    # Watch 6 s after the disturbance ends.
    stopped_at = None
    t_end = time.time() + 6
    while time.time() < t_end:
        drain(master)
        if not playing(proc.pid) and stopped_at is None:
            stopped_at = time.time()
        time.sleep(0.05)
    r["stopped"] = stopped_at is not None
    r["stop_after_disturbance_start_s"] = round(stopped_at - played_at, 2) if stopped_at else None
    # Stale speech: anything still playing 6-20 s after a stop is leftover reply audio.
    if r["stopped"]:
        resumed = None
        t_end = time.time() + 14
        while time.time() < t_end:
            drain(master)
            if playing(proc.pid):
                resumed = round(time.time() - stopped_at, 1)
                break
            time.sleep(0.1)
        r["stale_audio_after_stop_s"] = resumed
    r["controller"] = log_since(m)[:25]
    # Let the reply finish or be stopped before the next trial.
    t_end = time.time() + 90
    while time.time() < t_end and playing(proc.pid):
        drain(master)
        time.sleep(0.3)
    post(rec["port"], "clear draft")
    time.sleep(2)
    return r

if __name__ == "__main__":
    trials = [("yt_talk", 50), ("chatter", 50), ("stop", 50), ("stop", 25), ("stop", 80), ("yt_talk", 80)]
    if len(sys.argv) > 1:
        trials = [(t.split(":")[0], int(t.split(":")[1])) for t in sys.argv[1:]]
    proc, rec, master = start_omp()
    out = {"omp_pid": proc.pid, "port": rec["port"], "trials": []}
    try:
        for dist, vol in trials:
            res = trial(proc, rec, master, dist, vol)
            out["trials"].append(res)
            print(json.dumps(res), flush=True)
    finally:
        osa("set volume output volume 56")
        os.killpg(proc.pid, signal.SIGTERM)
    (D / "barge.json").write_text(json.dumps(out, indent=1))
