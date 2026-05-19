from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


_ALLOWED_GITHUB_HOSTS = {
    "github.com",
    "raw.githubusercontent.com",
    "api.github.com",
}


def normalize_github_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("GitHub-URL muss mit http oder https beginnen")
    if parsed.netloc not in _ALLOWED_GITHUB_HOSTS:
        raise ValueError("Nur github.com und raw.githubusercontent.com sind erlaubt")

    if parsed.netloc == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        # Falls es ein Repo-Import ist (kein blob), behandeln wir es als Repo
        if len(parts) >= 2 and (len(parts) == 2 or parts[2] != "blob"):
            owner = parts[0]
            repo = parts[1].replace(".git", "")
            return f"https://api.github.com/repos/{owner}/{repo}/contents/manifest.json"
        
        if len(parts) >= 5 and parts[2] == "blob":
            owner, repo, _blob, ref = parts[:4]
            rest = "/".join(parts[4:])
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{rest}"
        raise ValueError("GitHub-URL muss auf eine Datei oder ein Repository zeigen")

    return url


def fetch_repo_manifest(url: str) -> dict:
    normalized_url = normalize_github_url(url)
    request = Request(
        normalized_url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PI-Guardian-Router/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8").strip()
    except HTTPError as exc:
        raise HTTPError(exc.url, exc.code, exc.msg, exc.hdrs, exc.fp) from exc
    except URLError as exc:
        raise ValueError(f"GitHub nicht erreichbar: {exc.reason}") from exc
    data = json.loads(raw)
    
    if "content" not in data:
        raise ValueError("Keine manifest.json im Repository gefunden")
        
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content)


def _fetch_default_branch(owner: str, repo: str) -> str:
    """Fetch the default branch name from GitHub repo metadata."""
    meta_url = f"https://api.github.com/repos/{owner}/{repo}"
    request = Request(
        meta_url,
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "PI-Guardian-Router/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("default_branch", "main")
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f"Repository '{owner}/{repo}' nicht gefunden auf GitHub") from exc
        raise ValueError(f"GitHub API Fehler ({exc.code}): {exc.reason}") from exc
    except URLError as exc:
        raise ValueError(f"GitHub nicht erreichbar: {exc.reason}") from exc


def scan_github_repo(url: str) -> dict:
    parsed = urlparse(url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Ungültige GitHub-Repository-URL")

    owner = parts[0]
    repo = parts[1].replace(".git", "")

    # 1. Versuche manifest.json
    try:
        return fetch_repo_manifest(url)
    except Exception:
        pass

    # 2. Default Branch ermitteln, dann rekursiv scannen
    branch = _fetch_default_branch(owner, repo)
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    request = Request(
        tree_url,
        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "PI-Guardian-Router/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            tree_data = json.loads(response.read().decode("utf-8").strip())
    except HTTPError as exc:
        raise ValueError(f"GitHub API Fehler beim Tree-Scan ({exc.code}): {exc.reason}") from exc
    except URLError as exc:
        raise ValueError(f"GitHub nicht erreichbar: {exc.reason}") from exc

    entries = []
    for item in tree_data.get("tree", []):
        if item.get("type") == "blob":
            path = item["path"]
            path_lower = path.lower()

            # Nur .json oder .md Dateien
            if not (path_lower.endswith(".json") or path_lower.endswith(".md")):
                continue

            # Ignoriere Standarddateien
            if path.split("/")[-1].lower() in ["readme.md", "license", "contributing.md", ".gitignore"]:
                continue

            # Typ-Erkennung
            res_type = None
            if "agent" in path_lower or "/agents/" in f"/{path_lower}":
                res_type = "agent"
            elif "skill" in path_lower or "/skills/" in f"/{path_lower}":
                res_type = "skill"

            if res_type:
                entries.append({
                    "name": path.split("/")[-1].replace(".json", "").replace(".md", ""),
                    "type": res_type,
                    "path": path
                })

    return {
        "repository": repo,
        "version": "auto-scanned",
        "branch": branch,
        "entries": entries
    }


def fetch_text_from_github(url: str) -> str:
    normalized_url = normalize_github_url(url)
    request = Request(
        normalized_url,
        headers={
            "Accept": "text/plain, */*",
            "User-Agent": "PI-Guardian-Router/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8").strip()
    except HTTPError as exc:
        raise ValueError(f"GitHub-Datei nicht gefunden ({exc.code}): {url}") from exc
    except URLError as exc:
        raise ValueError(f"GitHub nicht erreichbar: {exc.reason}") from exc


def fetch_json_from_github(url: str) -> dict:
    # Falls es eine API-URL ist (Repo-Import), delegieren wir
    if "api.github.com" in url or (url.startswith("https://github.com") and len(url.split("/")) <= 5):
        return scan_github_repo(url)

    normalized_url = normalize_github_url(url)
    request = Request(
        normalized_url,
        headers={
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.1",
            "User-Agent": "PI-Guardian-Router/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:  # nosec B310 - GitHub host is allowlisted.
            raw = response.read().decode("utf-8").strip()
    except HTTPError as exc:
        raise ValueError(f"GitHub-Datei nicht gefunden ({exc.code}): {url}") from exc
    except URLError as exc:
        raise ValueError(f"GitHub nicht erreichbar: {exc.reason}") from exc
    if not raw:
        raise ValueError("GitHub-Datei ist leer")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub-Datei enthält kein gültiges JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("GitHub-Datei muss ein JSON-Objekt enthalten")
    return parsed
