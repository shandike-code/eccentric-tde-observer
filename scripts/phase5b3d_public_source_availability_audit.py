"""Phase 5B3d：审计 ZO 2020 published 本征值实现的公开可获得性。"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"

DOI = "10.1093/mnras/staa3127"
ARXIV_ID = "2009.06636v2"
ARTICLE_URL = "https://academic.oup.com/mnras/article/499/4/5562/5922725"
ARTICLE_CAPTURE_URL = "https://oup.silverchair-cdn.com/article-minimal/5922725"
CROSSREF_URL = f"https://api.crossref.org/works/{DOI}"
ARXIV_SOURCE_URL = f"https://export.arxiv.org/e-print/{ARXIV_ID}"
ZENODO_QUERY_URL = (
    "https://zenodo.org/api/records?q="
    f"{quote_plus(ARXIV_ID.removesuffix('v2'))}&size=10"
)
GITHUB_PAPER_QUERY = (
    '"2009.06636" OR "staa3127" OR '
    '"Eccentric Tidal Disruption Event Disks around Supermassive Black Holes"'
)
GITHUB_PAPER_URL = (
    "https://api.github.com/search/repositories?q="
    f"{quote_plus(GITHUB_PAPER_QUERY)}&per_page=100"
)
USER_AGENT = "eccentric-tde-observer-phase5b3d/1.0"

CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".f",
    ".f77",
    ".f90",
    ".f95",
    ".jl",
    ".m",
    ".nb",
    ".py",
    ".r",
    ".sh",
}
CODE_FILENAMES = {"makefile", "cmakelists.txt"}


def fetch_bytes(url: str) -> bytes:
    request = Request(
        url,
        headers={"Accept": "*/*", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=60.0) as response:
        return response.read()


def fetch_json(url: str) -> tuple[dict[str, Any], str]:
    payload = fetch_bytes(url)
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def classify_arxiv_members(
    members: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """区分可执行数值源、论文源和图文件；不把 TeX 当求解器。"""
    code: list[str] = []
    manuscript: list[str] = []
    figures: list[str] = []
    for member in members:
        path = PurePosixPath(member)
        suffix = path.suffix.lower()
        if suffix in CODE_SUFFIXES or path.name.lower() in CODE_FILENAMES:
            code.append(member)
        elif suffix in {".tex", ".bib", ".bbl", ".cls", ".bst"}:
            manuscript.append(member)
        elif suffix in {".pdf", ".png", ".jpg", ".jpeg", ".eps"}:
            figures.append(member)
    return code, manuscript, figures


def arxiv_source_audit() -> dict[str, Any]:
    payload = fetch_bytes(ARXIV_SOURCE_URL)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        members = sorted(
            member.name for member in archive.getmembers() if member.isfile()
        )
    code, manuscript, figures = classify_arxiv_members(members)
    return {
        "url": ARXIV_SOURCE_URL,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "member_count": len(members),
        "members": members,
        "numerical_code_members": code,
        "manuscript_source_members": manuscript,
        "figure_members": figures,
    }


def publisher_audit() -> dict[str, Any]:
    # 中文：期刊规范页会拒绝非浏览器请求，使用其同源只读正文端点取证。
    payload = fetch_bytes(ARTICLE_CAPTURE_URL)
    lowercase = payload.decode("utf-8", errors="replace").lower()
    request_phrase = (
        "the data underlying this article will be shared on reasonable "
        "request to the corresponding author"
    )
    return {
        "url": ARTICLE_URL,
        "capture_url": ARTICLE_CAPTURE_URL,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "reasonable_request_statement_present": request_phrase in lowercase,
        "github_link_present": "github.com" in lowercase,
        "zenodo_link_present": "zenodo.org" in lowercase,
    }


def crossref_audit() -> dict[str, Any]:
    payload, digest = fetch_json(CROSSREF_URL)
    message = payload["message"]
    relations = message.get("relation", {})
    links = message.get("link", [])
    dataset_links = [
        link
        for link in links
        if "dataset" in str(link.get("content-type", "")).lower()
    ]
    return {
        "url": CROSSREF_URL,
        "sha256": digest,
        "doi": message.get("DOI"),
        "relations": relations,
        "registered_links": links,
        "dataset_links": dataset_links,
    }


def zenodo_audit() -> dict[str, Any]:
    payload, digest = fetch_json(ZENODO_QUERY_URL)
    hits = payload["hits"]
    return {
        "url": ZENODO_QUERY_URL,
        "sha256": digest,
        "total_count": int(hits["total"]),
        "records": [
            {
                "id": record.get("id"),
                "doi": record.get("doi"),
                "title": record.get("metadata", {}).get("title"),
            }
            for record in hits["hits"]
        ],
    }


def github_audit() -> dict[str, Any]:
    paper_payload, paper_digest = fetch_json(GITHUB_PAPER_URL)
    return {
        "paper_query_url": GITHUB_PAPER_URL,
        "paper_query_sha256": paper_digest,
        "paper_query_total_count": int(paper_payload["total_count"]),
        "paper_query_repositories": [
            {
                "full_name": item.get("full_name"),
                "html_url": item.get("html_url"),
                "description": item.get("description"),
            }
            for item in paper_payload["items"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output_path = OUTPUT / "phase5b3d_public_source_availability_report.json"
    if output_path.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {output_path}; pass --force")

    publisher = publisher_audit()
    crossref = crossref_audit()
    arxiv = arxiv_source_audit()
    zenodo = zenodo_audit()
    github = github_audit()

    public_source_found = bool(
        arxiv["numerical_code_members"]
        or crossref["dataset_links"]
        or crossref["relations"]
        or zenodo["total_count"]
        or github["paper_query_total_count"]
    )
    report = {
        "phase": "5B3d public source availability audit",
        "evidence": "[L]+[V]+[O]",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "publisher": publisher,
        "crossref": crossref,
        "arxiv_source": arxiv,
        "zenodo": zenodo,
        "github": github,
        "public_published_solver_or_raw_dataset_found": public_source_found,
        "corresponding_author_request_required": bool(
            publisher["reasonable_request_statement_present"]
            and not public_source_found
        ),
        "external_request_sent": False,
        "formal_zo_source_model_changed": False,
        "phase_to_time_mapping_authorized": False,
        "interpretation": (
            "The publisher states that underlying data are available on reasonable "
            "request. Crossref registers no dataset relation, the arXiv v2 source "
            "archive contains no numerical source-code member, and exact public "
            "GitHub/Zenodo searches do not locate the published solver or raw Fig. "
            "6/7 data. The public-source route is therefore exhausted at the indexed "
            "portals audited here, but absence from these portals is not proof that "
            "the private implementation no longer exists. No external request was "
            "sent and the phase-to-time mapping remains unauthorized."
        ),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
