#!/usr/bin/env python3
"""Replace the featured-project block with the current highest-star public repos.

Project names and metadata are discovered from GitHub's public API on every run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "himadrijunior")
ORGANIZATION = os.environ.get("GITHUB_ORGANIZATION", "Invokeil")
API_ROOT = "https://api.github.com"
START = "<!-- FEATURED_PROJECTS:START -->"
END = "<!-- FEATURED_PROJECTS:END -->"
EXCLUDED_REPOS = {".github", USERNAME.lower()}
MAX_PROJECTS = int(os.environ.get("FEATURED_PROJECT_COUNT", "3"))


def github_json(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-project-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def repositories(owner: str, is_organization: bool = False) -> list[dict]:
    if is_organization:
        endpoint = f"{API_ROOT}/orgs/{owner}/repos?per_page=100&sort=updated&type=public"
    else:
        endpoint = f"{API_ROOT}/users/{owner}/repos?per_page=100&sort=updated&type=owner"
    data = github_json(endpoint)
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected repository response for {owner}")
    return data


def clean(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def project_markdown(repo: dict) -> str:
    name = clean(repo["name"])
    full_name = clean(repo["full_name"])
    url = repo["html_url"]
    description = clean(repo.get("description") or "")
    topics = repo.get("topics") or []
    stack_parts = []
    if repo.get("language"):
        stack_parts.append(clean(repo["language"]))
    stack_parts.extend(clean(topic) for topic in topics[:5])
    stack = " · ".join(dict.fromkeys(stack_parts))
    scale = f"{repo.get('stargazers_count', 0)} stars · {repo.get('forks_count', 0)} forks"

    return f"""<details>
<summary><strong>{name}</strong> · {scale}</summary>

{description}

| Stack | Scale | Performance | Security | Impact | Repository |
|:--|:--|:--|:--|:--|:--|
| {stack} | {scale} |  |  | {description} | [{full_name}]({url}) |

</details>"""


def main() -> None:
    all_repos: dict[str, dict] = {}
    for owner, is_org in ((USERNAME, False), (ORGANIZATION, True)):
        for repo in repositories(owner, is_org):
            name = repo.get("name", "")
            if repo.get("fork") or name.lower() in EXCLUDED_REPOS:
                continue
            all_repos[repo["full_name"].lower()] = repo

    ranked = sorted(
        all_repos.values(),
        key=lambda repo: (
            int(repo.get("stargazers_count", 0)),
            repo.get("updated_at", ""),
            repo.get("full_name", "").lower(),
        ),
        reverse=True,
    )[:MAX_PROJECTS]
    generated = "\n\n".join(project_markdown(repo) for repo in ranked)
    readme_path = Path(sys.argv[1] if len(sys.argv) > 1 else "README.md")
    readme = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    replacement = f"{START}\n\n{generated}\n\n{END}"
    updated, count = pattern.subn(lambda _: replacement, readme, count=1)
    if count != 1:
        raise RuntimeError("Featured project markers are missing or duplicated")
    readme_path.write_text(updated, encoding="utf-8")
    print(f"Updated {len(ranked)} featured repositories in {readme_path}")


if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError) as error:
        print(f"Unable to update featured projects: {error}", file=sys.stderr)
        raise SystemExit(1)
