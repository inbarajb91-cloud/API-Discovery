"""Tool implementations for the API Discovery Agent.

Each function here corresponds to a tool schema in tool_definitions.py.
The execute_tool() dispatcher routes tool calls from Claude to the right function.
"""

import json
import base64
import re
import requests
import yaml
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from config import APIS_GURU_LIST_URL
from pdf_report import create_report

# Module-level state — persists across tool calls within a session
_state = {
    "spec": None,           # Parsed OpenAPI spec
    "base_url": "",         # API base URL from spec
    "endpoints": [],        # Parsed endpoints list
    "auth_headers": {},     # Stored authentication headers
    "apis_guru_cache": None # Cached APIs.guru directory
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call to the appropriate function. Returns result as string."""
    handlers = {
        "lookup_api_directory": _lookup_api_directory,
        "fetch_openapi_spec": _fetch_openapi_spec,
        "list_endpoints": _list_endpoints,
        "search_endpoints": _search_endpoints,
        "authenticate": _authenticate,
        "call_api": _call_api,
        "validate_integration": _validate_integration,
        "generate_pdf_report": _generate_pdf_report,
        "discover_api_spec": _discover_api_spec,
        "scrape_documentation": _scrape_documentation,
        "web_search": _web_search,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return f"Error: Unknown tool '{tool_name}'"
    try:
        return handler(tool_input)
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"


# ---------------------------------------------------------------------------
# Tool 1: lookup_api_directory
# ---------------------------------------------------------------------------
def _lookup_api_directory(params: dict) -> str:
    """Search APIs.guru directory for APIs matching a query."""
    query = params.get("query", "").lower().strip()
    if not query:
        return "Error: query parameter is required"

    # Fetch and cache the directory
    if _state["apis_guru_cache"] is None:
        try:
            resp = requests.get(APIS_GURU_LIST_URL, timeout=15)
            resp.raise_for_status()
            _state["apis_guru_cache"] = resp.json()
        except Exception as e:
            return f"Error fetching APIs.guru directory: {str(e)}. Please provide the OpenAPI spec URL directly."

    directory = _state["apis_guru_cache"]
    matches = []

    for provider_key, provider_data in directory.items():
        provider_lower = provider_key.lower()
        if query in provider_lower:
            # Get all versions/services under this provider
            versions = provider_data.get("versions", {})
            preferred = provider_data.get("preferred", "")

            # Find the preferred or latest version
            if preferred and preferred in versions:
                version_data = versions[preferred]
            elif versions:
                version_data = list(versions.values())[-1]
            else:
                continue

            info = version_data.get("info", {})
            swagger_url = version_data.get("swaggerUrl", "")

            matches.append({
                "provider": provider_key,
                "title": info.get("title", provider_key),
                "description": info.get("description", "")[:200],
                "version": info.get("version", "unknown"),
                "spec_url": swagger_url,
            })

            if len(matches) >= 10:
                break

    if not matches:
        return f"No APIs found matching '{query}' in APIs.guru directory. Please provide the OpenAPI spec URL directly."

    result_lines = [f"Found {len(matches)} API(s) matching '{query}':\n"]
    for m in matches:
        result_lines.append(f"  - {m['title']} (v{m['version']})")
        result_lines.append(f"    Provider: {m['provider']}")
        if m['description']:
            result_lines.append(f"    Description: {m['description']}")
        result_lines.append(f"    Spec URL: {m['spec_url']}")
        result_lines.append("")

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Tool 2: fetch_openapi_spec
# ---------------------------------------------------------------------------
def _fetch_openapi_spec(params: dict) -> str:
    """Download and parse an OpenAPI/Swagger specification."""
    spec_url = params.get("spec_url", "").strip()
    if not spec_url:
        return "Error: spec_url parameter is required"

    try:
        resp = requests.get(spec_url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return f"Error fetching spec from {spec_url}: {str(e)}"

    # Parse JSON or YAML
    content = resp.text
    try:
        spec = json.loads(content)
    except json.JSONDecodeError:
        try:
            spec = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return f"Error parsing spec: {str(e)}"

    if not isinstance(spec, dict):
        return "Error: Spec did not parse into a valid object"

    _state["spec"] = spec

    # Extract base URL
    if "servers" in spec and spec["servers"]:
        _state["base_url"] = spec["servers"][0].get("url", "")
    elif "host" in spec:
        scheme = "https"
        if "schemes" in spec and spec["schemes"]:
            scheme = spec["schemes"][0]
        base_path = spec.get("basePath", "")
        _state["base_url"] = f"{scheme}://{spec['host']}{base_path}"
    else:
        _state["base_url"] = ""

    # Parse endpoints
    paths = spec.get("paths", {})
    endpoints = []
    tags_found = set()

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "patch", "delete"]:
            if method not in path_item:
                continue
            operation = path_item[method]
            tags = operation.get("tags", [])
            tags_found.update(tags)

            params_list = []
            for p in operation.get("parameters", []):
                params_list.append({
                    "name": p.get("name", ""),
                    "in": p.get("in", ""),
                    "required": p.get("required", False),
                    "type": p.get("schema", {}).get("type", p.get("type", "string")),
                })

            endpoints.append({
                "method": method.upper(),
                "path": path,
                "summary": operation.get("summary", ""),
                "description": operation.get("description", ""),
                "operationId": operation.get("operationId", ""),
                "tags": tags,
                "parameters": params_list,
            })

    _state["endpoints"] = endpoints

    title = spec.get("info", {}).get("title", "Unknown API")
    version = spec.get("info", {}).get("version", "unknown")
    description = spec.get("info", {}).get("description", "")[:200]

    return (
        f"Successfully parsed OpenAPI spec.\n"
        f"  Title: {title}\n"
        f"  Version: {version}\n"
        f"  Base URL: {_state['base_url']}\n"
        f"  Description: {description}\n"
        f"  Endpoints: {len(endpoints)}\n"
        f"  Tags: {', '.join(sorted(tags_found)) if tags_found else 'none'}"
    )


# ---------------------------------------------------------------------------
# Tool 3: list_endpoints
# ---------------------------------------------------------------------------
def _list_endpoints(params: dict) -> str:
    """List all endpoints from the loaded spec."""
    if not _state["endpoints"]:
        return "Error: No OpenAPI spec loaded. Use fetch_openapi_spec first."

    filter_tag = params.get("filter_tag", "").lower().strip()
    endpoints = _state["endpoints"]

    if filter_tag:
        endpoints = [e for e in endpoints if filter_tag in [t.lower() for t in e.get("tags", [])]]

    if not endpoints:
        return f"No endpoints found{' with tag: ' + filter_tag if filter_tag else ''}."

    lines = [f"Found {len(endpoints)} endpoint(s):\n"]
    for ep in endpoints:
        lines.append(f"  {ep['method']} {ep['path']}")
        if ep["summary"]:
            lines.append(f"    Summary: {ep['summary']}")
        if ep["tags"]:
            lines.append(f"    Tags: {', '.join(ep['tags'])}")
        if ep["parameters"]:
            param_strs = []
            for p in ep["parameters"]:
                req = " (required)" if p["required"] else ""
                param_strs.append(f"{p['name']} [{p['in']}]{req}")
            lines.append(f"    Params: {', '.join(param_strs)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4: search_endpoints
# ---------------------------------------------------------------------------
def _search_endpoints(params: dict) -> str:
    """Search endpoints by keyword."""
    if not _state["endpoints"]:
        return "Error: No OpenAPI spec loaded. Use fetch_openapi_spec first."

    query = params.get("query", "").lower().strip()
    if not query:
        return "Error: query parameter is required"

    query_terms = query.split()
    scored = []

    for ep in _state["endpoints"]:
        score = 0
        searchable = {
            "path": ep["path"].lower(),
            "summary": ep["summary"].lower(),
            "description": ep["description"].lower(),
            "operationId": ep["operationId"].lower(),
            "tags": " ".join(ep["tags"]).lower(),
        }

        for term in query_terms:
            if term in searchable["path"]:
                score += 3
            if term in searchable["summary"]:
                score += 2
            if term in searchable["operationId"]:
                score += 2
            if term in searchable["description"]:
                score += 1
            if term in searchable["tags"]:
                score += 1

        if score > 0:
            scored.append((score, ep))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:10]

    if not top:
        return f"No endpoints matching '{query}' found."

    lines = [f"Found {len(top)} endpoint(s) matching '{query}':\n"]
    for score, ep in top:
        lines.append(f"  {ep['method']} {ep['path']} (relevance: {score})")
        if ep["summary"]:
            lines.append(f"    Summary: {ep['summary']}")
        if ep["parameters"]:
            param_strs = [p["name"] for p in ep["parameters"][:5]]
            lines.append(f"    Params: {', '.join(param_strs)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 5: authenticate
# ---------------------------------------------------------------------------
def _authenticate(params: dict) -> str:
    """Set up authentication for subsequent API calls."""
    auth_type = params.get("auth_type", "")
    credentials = params.get("credentials", {})

    if auth_type == "bearer":
        token = credentials.get("token", "")
        if not token:
            return "Error: 'token' is required for bearer auth"
        _state["auth_headers"] = {"Authorization": f"Bearer {token}"}
        return "Authentication configured: Bearer token set."

    elif auth_type == "api_key":
        key = credentials.get("key", "")
        header_name = credentials.get("header_name", "api_key")
        if not key:
            return "Error: 'key' is required for api_key auth"
        _state["auth_headers"] = {header_name: key}
        return f"Authentication configured: API key set in header '{header_name}'."

    elif auth_type == "basic":
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if not username:
            return "Error: 'username' is required for basic auth"
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        _state["auth_headers"] = {"Authorization": f"Basic {encoded}"}
        return "Authentication configured: Basic auth credentials set."

    elif auth_type == "oauth2_client_credentials":
        token_url = credentials.get("token_url", "")
        client_id = credentials.get("client_id", "")
        client_secret = credentials.get("client_secret", "")
        scope = credentials.get("scope", "")

        if not all([token_url, client_id, client_secret]):
            return "Error: 'token_url', 'client_id', and 'client_secret' are required for OAuth2"

        try:
            data = {"grant_type": "client_credentials"}
            if scope:
                data["scope"] = scope
            resp = requests.post(
                token_url,
                data=data,
                auth=(client_id, client_secret),
                timeout=15,
            )
            resp.raise_for_status()
            token_data = resp.json()
            access_token = token_data.get("access_token", "")
            if not access_token:
                return f"Error: No access_token in response: {json.dumps(token_data)[:500]}"
            _state["auth_headers"] = {"Authorization": f"Bearer {access_token}"}
            expires = token_data.get("expires_in", "unknown")
            return f"Authentication configured: OAuth2 token obtained (expires in {expires}s)."
        except Exception as e:
            return f"Error obtaining OAuth2 token: {str(e)}"

    else:
        return f"Error: Unknown auth_type '{auth_type}'. Use: bearer, api_key, basic, or oauth2_client_credentials"


# ---------------------------------------------------------------------------
# Tool 6: call_api
# ---------------------------------------------------------------------------
def _call_api(params: dict) -> str:
    """Make a real HTTP request to test an endpoint."""
    method = params.get("method", "GET").upper()
    url = params.get("url", "")
    headers = params.get("headers", {}) or {}
    body = params.get("body")
    query_params = params.get("query_params", {}) or {}

    if not url:
        return "Error: url parameter is required"

    # Inject stored auth headers
    all_headers = {**_state["auth_headers"], **headers}
    if body and "Content-Type" not in all_headers:
        all_headers["Content-Type"] = "application/json"

    try:
        resp = requests.request(
            method=method,
            url=url,
            headers=all_headers,
            json=body if body else None,
            params=query_params if query_params else None,
            timeout=15,
        )
    except requests.exceptions.Timeout:
        return f"Error: Request to {url} timed out after 15 seconds"
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to {url}"
    except Exception as e:
        return f"Error: {str(e)}"

    # Format response
    body_text = resp.text[:3000]
    try:
        body_json = resp.json()
        body_text = json.dumps(body_json, indent=2)[:3000]
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract response field names for validation
    field_names = []
    try:
        body_json = resp.json()
        if isinstance(body_json, dict):
            field_names = list(body_json.keys())
        elif isinstance(body_json, list) and body_json:
            first = body_json[0] if isinstance(body_json[0], dict) else {}
            field_names = list(first.keys())
    except (json.JSONDecodeError, ValueError):
        pass

    return (
        f"HTTP {method} {url}\n"
        f"Status: {resp.status_code} {resp.reason}\n"
        f"Response fields: {', '.join(field_names) if field_names else 'N/A'}\n"
        f"Response body:\n{body_text}"
    )


# ---------------------------------------------------------------------------
# Tool 7: validate_integration
# ---------------------------------------------------------------------------
def _validate_integration(params: dict) -> str:
    """Evaluate whether the integration use case is achievable."""
    use_case = params.get("use_case", "")
    required_caps = params.get("required_capabilities", [])
    discovered = params.get("discovered_endpoints", [])
    test_results = params.get("test_results", [])

    capability_mapping = []
    verified_count = 0
    total_caps = len(required_caps)

    for cap in required_caps:
        capability = cap.get("capability", "")
        required_fields = cap.get("required_fields", [])

        # Find matching endpoint
        matched_endpoint = None
        for ep in discovered:
            if ep.get("maps_to_capability", "").lower() == capability.lower():
                matched_endpoint = ep
                break

        # Find test result for this endpoint
        matched_test = None
        if matched_endpoint:
            ep_key = f"{matched_endpoint['method']} {matched_endpoint['path']}"
            for tr in test_results:
                if tr.get("endpoint", "") == ep_key:
                    matched_test = tr
                    break

        if matched_endpoint and matched_test:
            status_code = matched_test.get("status_code", 0)
            available_fields = matched_test.get("available_fields", [])
            missing = [f for f in required_fields if f.lower() not in [a.lower() for a in available_fields]]

            if 200 <= status_code < 300 and not missing:
                status = "VERIFIED"
                verified_count += 1
            elif 200 <= status_code < 300:
                status = "PARTIAL"
            else:
                status = "FAILED"

            capability_mapping.append({
                "capability": capability,
                "endpoint": f"{matched_endpoint['method']} {matched_endpoint['path']}",
                "status": status,
                "available_fields": available_fields,
                "missing_fields": missing,
            })
        elif matched_endpoint:
            capability_mapping.append({
                "capability": capability,
                "endpoint": f"{matched_endpoint['method']} {matched_endpoint['path']}",
                "status": "UNTESTED",
                "available_fields": [],
                "missing_fields": required_fields,
            })
        else:
            capability_mapping.append({
                "capability": capability,
                "endpoint": "NOT FOUND",
                "status": "MISSING",
                "available_fields": [],
                "missing_fields": required_fields,
            })

    # Determine verdict
    if total_caps == 0:
        verdict = "ACHIEVABLE"
        confidence = 0.5
    elif verified_count == total_caps:
        verdict = "ACHIEVABLE"
        confidence = 0.95
    elif verified_count > 0:
        verdict = "PARTIALLY_ACHIEVABLE"
        confidence = round(verified_count / total_caps, 2)
    else:
        verdict = "NOT_ACHIEVABLE"
        confidence = 0.1

    gaps = []
    recommendations = []
    for cm in capability_mapping:
        if cm["status"] == "MISSING":
            gaps.append(f"No endpoint found for: {cm['capability']}")
        elif cm["status"] == "PARTIAL":
            gaps.append(f"Missing fields for {cm['capability']}: {', '.join(cm['missing_fields'])}")
        elif cm["status"] == "FAILED":
            gaps.append(f"Endpoint for {cm['capability']} returned an error")
            recommendations.append(f"Check authentication and permissions for {cm['endpoint']}")

    if verdict == "ACHIEVABLE":
        recommendations.append("All capabilities verified. Proceed with integration implementation.")
    elif gaps:
        recommendations.append("Consider alternative APIs or custom solutions for the identified gaps.")

    result = {
        "overall_verdict": verdict,
        "confidence_score": confidence,
        "capability_mapping": capability_mapping,
        "gaps": gaps,
        "recommendations": recommendations,
    }

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 8: generate_pdf_report
# ---------------------------------------------------------------------------
def _generate_pdf_report(params: dict) -> str:
    """Generate a PDF report and return the file path."""
    report_data = params.get("report_data", {})
    if not report_data:
        return "Error: report_data parameter is required"

    try:
        filepath = create_report(report_data)
        return filepath
    except Exception as e:
        return f"Error generating PDF: {str(e)}"


# ---------------------------------------------------------------------------
# Tool 9: discover_api_spec
# ---------------------------------------------------------------------------
_COMMON_SPEC_PATHS = [
    "/openapi.json",
    "/openapi.yaml",
    "/swagger.json",
    "/swagger.yaml",
    "/api-docs",
    "/v2/api-docs",
    "/v3/api-docs",
    "/api/openapi.json",
    "/api/swagger.json",
    "/api/v1/openapi.json",
    "/api/v2/openapi.json",
    "/api/v3/openapi.json",
    "/docs/openapi.json",
    "/api/docs",
    "/.well-known/openapi.json",
    "/api.json",
    "/swagger/v1/swagger.json",
    "/swagger/docs/v1",
]


def _discover_api_spec(params: dict) -> str:
    """Try common paths to find an OpenAPI/Swagger spec on a base URL."""
    base_url = params.get("base_url", "").strip().rstrip("/")
    if not base_url:
        return "Error: base_url parameter is required"

    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    found = []
    tried = []

    for path in _COMMON_SPEC_PATHS:
        url = f"{base_url}{path}"
        tried.append(url)
        try:
            resp = requests.get(url, timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                # Check if it looks like a spec (JSON or YAML with paths/swagger/openapi key)
                content = resp.text[:500]
                if any(keyword in content.lower() for keyword in ['"paths"', '"swagger"', '"openapi"', "'paths'", "paths:", "swagger:", "openapi:"]):
                    found.append({
                        "url": url,
                        "content_type": resp.headers.get("Content-Type", "unknown"),
                        "size": len(resp.text),
                    })
        except (requests.RequestException, Exception):
            continue

    if found:
        lines = [f"Found {len(found)} OpenAPI/Swagger spec(s):\n"]
        for f in found:
            lines.append(f"  URL: {f['url']}")
            lines.append(f"  Content-Type: {f['content_type']}")
            lines.append(f"  Size: {f['size']} bytes")
            lines.append("")
        lines.append("Use fetch_openapi_spec with the URL above to parse the spec.")
        return "\n".join(lines)
    else:
        return (
            f"No OpenAPI/Swagger spec found at {base_url}.\n"
            f"Tried {len(tried)} common paths.\n\n"
            f"Suggestions:\n"
            f"  - Use web_search to find the documentation URL\n"
            f"  - Use scrape_documentation to read their developer docs\n"
            f"  - Ask the user for the spec URL directly"
        )


# ---------------------------------------------------------------------------
# Tool 10: scrape_documentation
# ---------------------------------------------------------------------------
def _scrape_documentation(params: dict) -> str:
    """Fetch and extract text from an API documentation webpage using Jina Reader."""
    url = params.get("url", "").strip()
    extract_links = params.get("extract_links", False)

    if not url:
        return "Error: url parameter is required"

    if not url.startswith("http"):
        url = f"https://{url}"

    # Use Jina Reader API — renders JavaScript, bypasses bot protection, returns clean markdown
    jina_url = f"https://r.jina.ai/{url}"

    try:
        headers = {
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
        }
        if extract_links:
            headers["X-With-Links"] = "true"

        resp = requests.get(jina_url, timeout=30, headers=headers)
        resp.raise_for_status()
        content = resp.text
    except Exception as e:
        # Fallback to direct requests + BeautifulSoup if Jina fails
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.body or soup
            content = main.get_text(separator="\n", strip=True)
        except Exception as e2:
            return f"Error fetching {url}: Jina failed ({str(e)}), direct fetch also failed ({str(e2)})"

    # Truncate to ~5000 chars for Claude context
    if len(content) > 5000:
        content = content[:5000] + "\n\n[... content truncated, scrape more specific pages for details]"

    return f"Documentation from {url}:\n\n{content}"


# ---------------------------------------------------------------------------
# Tool 11: web_search
# ---------------------------------------------------------------------------
def _web_search(params: dict) -> str:
    """Search the web for API documentation using DuckDuckGo."""
    query = params.get("query", "").strip()
    max_results = min(params.get("max_results", 5), 10)

    if not query:
        return "Error: query parameter is required"

    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as e:
        return f"Error searching: {str(e)}"

    if not results:
        return f"No results found for '{query}'."

    lines = [f"Search results for '{query}':\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. {r.get('title', 'No title')}")
        lines.append(f"     URL: {r.get('href', 'No URL')}")
        body = r.get("body", "")
        if body:
            lines.append(f"     {body[:150]}")
        lines.append("")

    lines.append("Use scrape_documentation to read any of these pages, or fetch_openapi_spec if a URL points to a spec file.")
    return "\n".join(lines)
