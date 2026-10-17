"""JSON file persistence for custom agents and agent stats."""

import json
import os
import threading
from pathlib import Path
from typing import Dict, Optional

_lock = threading.RLock()
_data: Optional[dict] = None


def _data_dir() -> Path:
    return Path(os.getenv("AGENTVERSE_DATA_DIR", str(Path(__file__).parent / "data")))


def _store_file() -> Path:
    return _data_dir() / "store.json"


def _empty() -> dict:
    return {"custom_agents": {}, "stats": {}}


def _ensure() -> dict:
    global _data
    if _data is None:
        loaded = _empty()
        try:
            path = _store_file()
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    agents = raw.get("custom_agents")
                    stats = raw.get("stats")
                    if isinstance(agents, dict):
                        loaded["custom_agents"] = agents
                    if isinstance(stats, dict):
                        loaded["stats"] = stats
        except (OSError, json.JSONDecodeError):
            loaded = _empty()
        _data = loaded
    return _data


def _write() -> None:
    try:
        path = _store_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(_data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _reset() -> None:
    """Clear in-memory cache (next access re-reads from disk)."""
    global _data
    with _lock:
        _data = None


def get_custom_agents() -> Dict[str, dict]:
    with _lock:
        return dict(_ensure()["custom_agents"])


def put_custom_agent(agent_dict: dict) -> None:
    with _lock:
        _ensure()
        _data["custom_agents"][agent_dict["id"]] = agent_dict
        _write()


def remove_custom_agent(agent_id: str) -> bool:
    with _lock:
        _ensure()
        existed = _data["custom_agents"].pop(agent_id, None) is not None
        if existed:
            _write()
        return existed


def _stat(agent_id: str) -> dict:
    st = _ensure()["stats"].setdefault(agent_id, {"run_count": 0, "star_count": 0})
    st.setdefault("run_count", 0)
    st.setdefault("star_count", 0)
    return st


def get_stat(agent_id: str) -> dict:
    with _lock:
        st = _ensure()["stats"].get(agent_id)
        return {"run_count": st.get("run_count", 0), "star_count": st.get("star_count", 0)} if st else {"run_count": 0, "star_count": 0}


def all_stats() -> Dict[str, dict]:
    with _lock:
        return {k: {"run_count": v.get("run_count", 0), "star_count": v.get("star_count", 0)} for k, v in _ensure()["stats"].items()}


def bump_run_count(agent_id: str) -> int:
    with _lock:
        _ensure()
        st = _stat(agent_id)
        st["run_count"] += 1
        _write()
        return st["run_count"]


def adjust_star_count(agent_id: str, delta: int) -> int:
    with _lock:
        _ensure()
        st = _stat(agent_id)
        st["star_count"] = max(0, st.get("star_count", 0) + delta)
        _write()
        return st["star_count"]
