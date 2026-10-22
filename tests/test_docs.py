"""The docs follow the MCP server: every tool in the references, every tool count right."""

import re
from pathlib import Path

from midibakery.mcp import build_server

ROOT = Path(__file__).resolve().parent.parent
REFERENCES = ("docs/user/MCP_SERVER.md", "docs/user/MCP_SERVER.de.md")
# "40 tools", "40 Werkzeuge", "40 MCP tools"; not ranges such as "25–35 tools".
COUNT = re.compile(r"(?<![–\-\d])(\d+) (?:MCP[- ])?(?:tools|Tools|Werkzeuge)\b")


async def _tool_names() -> set[str]:
    return {t.name for t in await build_server().list_tools()}


async def test_tool_references_list_every_tool():
    names = await _tool_names()
    for doc in REFERENCES:
        rows = [line for line in (ROOT / doc).read_text(encoding="utf-8").splitlines() if line.startswith("| `")]
        listed = {name for row in rows for name in re.findall(r"`([a-z_]+)`", row.split("|")[1])}
        assert names - listed == set(), f"{doc} misses tools"
        assert listed - names == set(), f"{doc} lists tools the server does not have"


async def test_tool_counts_in_docs_match_the_server():
    allowed = {len(await _tool_names())}
    docs = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    wrong = [
        f"{doc.relative_to(ROOT)}: {match.group(0)}"
        for doc in docs
        for match in COUNT.finditer(doc.read_text(encoding="utf-8"))
        if int(match.group(1)) not in allowed
    ]
    assert wrong == []
