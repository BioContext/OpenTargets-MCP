"""
FastMCP server that exposes selected Open Targets Platform GraphQL
end‑points as MCP tools.

Save as  `opentargets_server.py`  (replacing the previous weather server).
Run with:  python opentargets_server.py
"""
from typing import Any, Dict, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------
# FastMCP initialisation
# ---------------------------------------------------------------------
mcp = FastMCP("open_targets")

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
OT_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
USER_AGENT = "open-targets-mcp/1.0"

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------
async def make_ot_request(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Perform a POST request to the Open Targets GraphQL API.
    Returns the parsed `data` block or None on any error.
    """
    payload: Dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OT_GRAPHQL_URL, json=payload, headers=headers, timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
                return None
            return data.get("data")
        except Exception as e:
            print(f"Request error: {str(e)}")
            return None


def _fmt_block(title: str, lines: List[str]) -> str:
    """Utility to make small readable blocks."""
    joined = "\n".join(f"- {ln}" for ln in lines)
    return f"\n{title}:\n{joined}\n"


# ---------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------
@mcp.tool()
async def get_target_info(ensembl_id: str) -> str:
    """Return basic Open Targets annotation for a target (gene/protein)."""
    query = """
    query targetInfo($id: String!) {
      target(ensemblId: $id) {
        id
        approvedSymbol
        approvedName
        biotype
        tractability {
          modality
          label
          value
        }
      }
    }
    """
    data = await make_ot_request(query, {"id": ensembl_id})
    if not data:
        return "Target not found or API error."
    
    target = data.get("target")
    if not target:
        return "Target not found in response."
    
    lines = [
        f"Symbol: {target.get('approvedSymbol', 'N/A')}",
        f"Name: {target.get('approvedName', 'N/A')}",
        f"Biotype: {target.get('biotype', 'N/A')}",
    ]
    
    tractability = target.get("tractability", [])
    if tractability:
        tract_info = tractability[0] if isinstance(tractability, list) else tractability
        lines.append(f"Tractability: {tract_info.get('label', 'N/A')} ({tract_info.get('modality', 'N/A')} → {tract_info.get('value', 'N/A')})")
    
    return _fmt_block(f"Target {ensembl_id}", lines)


@mcp.tool()
async def get_disease_info(efo_id: str) -> str:
    """Return basic Open Targets annotation for a disease / phenotype."""
    query = """
    query diseaseInfo($id: String!) {
      disease(efoId: $id) {
        id
        name
        therapeuticAreas
        ontology
      }
    }
    """
    data = await make_ot_request(query, {"id": efo_id})
    if not data:
        return "Disease not found or API error."
    
    disease = data.get("disease")
    if not disease:
        return "Disease not found in response."
    
    lines = [
        f"Name: {disease.get('name', 'N/A')}",
        f"Ontology: {disease.get('ontology', 'N/A')}",
        f"Therapeutic areas: {', '.join(disease.get('therapeuticAreas', [])) or 'N/A'}"
    ]
    
    return _fmt_block(f"Disease {efo_id}", lines)


@mcp.tool()
async def targets_associated_with_disease(
    efo_id: str, page_index: int = 0, page_size: int = 10
) -> str:
    """Return the first page of targets associated with a disease."""
    query = """
    query diseaseTargets($id: String!, $index: Int!, $size: Int!) {
      disease(efoId: $id) {
        name
        associatedTargets(page: {index: $index, size: $size}) {
          count
          rows { target { id approvedSymbol } score }
        }
      }
    }
    """
    vars_ = {"id": efo_id, "index": page_index, "size": page_size}
    data = await make_ot_request(query, vars_)
    if not data or not data.get("disease"):
        return "Disease not found or API error."

    rows = data["disease"]["associatedTargets"]["rows"]
    if not rows:
        return "No associated targets returned for this page."

    lines = [
        f"{row['target']['approvedSymbol']} (score {row['score']:.3f})"
        for row in rows
    ]
    return _fmt_block(
        f"Targets for {data['disease']['name']} "
        f"(page {page_index}, size {page_size})",
        lines,
    )


@mcp.tool()
async def diseases_associated_with_target(
    ensembl_id: str, page_index: int = 0, page_size: int = 10
) -> str:
    """Return the first page of diseases associated with a target."""
    query = """
    query targetDiseases($id: String!, $index: Int!, $size: Int!) {
      target(ensemblId: $id) {
        approvedSymbol
        associatedDiseases(page: {index: $index, size: $size}) {
          count
          rows { disease { id name } score }
        }
      }
    }
    """
    vars_ = {"id": ensembl_id, "index": page_index, "size": page_size}
    data = await make_ot_request(query, vars_)
    if not data or not data.get("target"):
        return "Target not found or API error."

    rows = data["target"]["associatedDiseases"]["rows"]
    if not rows:
        return "No associated diseases returned for this page."

    lines = [
        f"{row['disease']['name']} (score {row['score']:.3f})"
        for row in rows
    ]
    return _fmt_block(
        f"Diseases for {data['target']['approvedSymbol']} "
        f"(page {page_index}, size {page_size})",
        lines,
    )


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
