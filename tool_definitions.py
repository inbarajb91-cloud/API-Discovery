"""Tool schemas for Claude's tool_use. These define what tools the agent can call."""

TOOLS = [
    {
        "name": "lookup_api_directory",
        "description": "Search the APIs.guru directory (14,000+ public APIs) to find an API by name or keyword. Returns matching APIs with their OpenAPI spec URLs. Use this when the user mentions a system/service name but hasn't provided a spec URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - API provider name, service name, or keyword. Examples: 'stripe', 'petstore', 'weather', 'github'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_openapi_spec",
        "description": "Download and parse an OpenAPI/Swagger specification from a URL. Supports both JSON and YAML formats (OpenAPI 2.0 and 3.x). Returns a summary of the API including title, version, base URL, and endpoint count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spec_url": {
                    "type": "string",
                    "description": "URL to the OpenAPI/Swagger specification file (JSON or YAML)"
                }
            },
            "required": ["spec_url"]
        }
    },
    {
        "name": "list_endpoints",
        "description": "List all endpoints from the currently loaded OpenAPI spec. Shows HTTP method, path, summary, parameters, and request body schema for each endpoint. Optionally filter by tag.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter_tag": {
                    "type": "string",
                    "description": "Optional tag to filter endpoints by (e.g., 'pet', 'store', 'user')"
                }
            },
            "required": []
        }
    },
    {
        "name": "search_endpoints",
        "description": "Search through discovered endpoints by keyword or capability description. Searches across endpoint paths, summaries, descriptions, operation IDs, and tags. Returns matching endpoints ranked by relevance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query describing the capability you're looking for. Examples: 'list pets', 'create order', 'update status', 'delete user'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "authenticate",
        "description": "Authenticate to a target API system. Stores credentials for subsequent API calls. Supports Bearer token, API key, Basic auth, and OAuth2 client credentials flow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "auth_type": {
                    "type": "string",
                    "enum": ["bearer", "api_key", "basic", "oauth2_client_credentials"],
                    "description": "Authentication method to use"
                },
                "credentials": {
                    "type": "object",
                    "description": "Credentials object. For 'bearer': {token}. For 'api_key': {key, header_name}. For 'basic': {username, password}. For 'oauth2_client_credentials': {token_url, client_id, client_secret, scope}.",
                    "properties": {
                        "token": {"type": "string", "description": "Bearer token"},
                        "key": {"type": "string", "description": "API key value"},
                        "header_name": {"type": "string", "description": "Header name for API key (default: 'api_key')"},
                        "username": {"type": "string", "description": "Username for basic auth"},
                        "password": {"type": "string", "description": "Password for basic auth"},
                        "token_url": {"type": "string", "description": "OAuth2 token endpoint URL"},
                        "client_id": {"type": "string", "description": "OAuth2 client ID"},
                        "client_secret": {"type": "string", "description": "OAuth2 client secret"},
                        "scope": {"type": "string", "description": "OAuth2 scope (space-separated)"}
                    }
                }
            },
            "required": ["auth_type", "credentials"]
        }
    },
    {
        "name": "call_api",
        "description": "Make a real HTTP request to test an API endpoint. Automatically includes any stored authentication credentials. Returns the status code, response headers, and response body (truncated to 3000 characters).",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method"
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to call (e.g., 'https://petstore3.swagger.io/api/v3/pet/findByStatus?status=available')"
                },
                "headers": {
                    "type": "object",
                    "description": "Additional HTTP headers to include (auth headers are injected automatically)",
                    "additionalProperties": {"type": "string"}
                },
                "body": {
                    "type": "object",
                    "description": "Request body (for POST/PUT/PATCH). Will be sent as JSON."
                },
                "query_params": {
                    "type": "object",
                    "description": "URL query parameters",
                    "additionalProperties": {"type": "string"}
                }
            },
            "required": ["method", "url"]
        }
    },
    {
        "name": "validate_integration",
        "description": "Evaluate whether a use case is achievable based on discovered endpoints and test results. Maps required capabilities to available endpoints, checks response payloads for required fields, and produces a structured verdict with confidence score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "use_case": {
                    "type": "string",
                    "description": "The user's integration use case description"
                },
                "required_capabilities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "capability": {"type": "string", "description": "What the user needs to do (e.g., 'List available pets')"},
                            "required_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Data fields needed for this capability"
                            }
                        },
                        "required": ["capability"]
                    },
                    "description": "List of capabilities the user needs"
                },
                "discovered_endpoints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "method": {"type": "string"},
                            "path": {"type": "string"},
                            "summary": {"type": "string"},
                            "maps_to_capability": {"type": "string", "description": "Which required capability this endpoint serves"}
                        },
                        "required": ["method", "path"]
                    },
                    "description": "Endpoints discovered from the API spec"
                },
                "test_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "endpoint": {"type": "string", "description": "e.g., 'GET /pet/findByStatus'"},
                            "status_code": {"type": "integer"},
                            "available_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Fields found in the response"
                            }
                        },
                        "required": ["endpoint", "status_code"]
                    },
                    "description": "Results from testing the endpoints"
                }
            },
            "required": ["use_case", "required_capabilities", "discovered_endpoints", "test_results"]
        }
    },
    {
        "name": "generate_pdf_report",
        "description": "Generate a professional PDF report summarizing the API discovery findings. The report includes an executive summary, endpoint details, capability mapping, gaps, and recommendations. Returns the file path for download.",
        "input_schema": {
            "type": "object",
            "properties": {
                "report_data": {
                    "type": "object",
                    "description": "Report content",
                    "properties": {
                        "title": {"type": "string", "description": "Report title (e.g., 'API Discovery Report: Petstore API')"},
                        "use_case": {"type": "string", "description": "The user's use case description"},
                        "target_system": {"type": "string", "description": "Name of the target API/system"},
                        "verdict": {
                            "type": "string",
                            "enum": ["ACHIEVABLE", "PARTIALLY_ACHIEVABLE", "NOT_ACHIEVABLE"],
                            "description": "Overall verdict"
                        },
                        "confidence_score": {"type": "number", "description": "Confidence score from 0 to 1"},
                        "endpoints": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "method": {"type": "string"},
                                    "path": {"type": "string"},
                                    "description": {"type": "string"},
                                    "test_status": {"type": "string"},
                                    "maps_to": {"type": "string"}
                                }
                            },
                            "description": "Endpoints used in the integration"
                        },
                        "capability_mapping": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "capability": {"type": "string"},
                                    "endpoint": {"type": "string"},
                                    "status": {"type": "string"},
                                    "available_fields": {"type": "array", "items": {"type": "string"}},
                                    "missing_fields": {"type": "array", "items": {"type": "string"}}
                                }
                            },
                            "description": "Mapping of required capabilities to endpoints"
                        },
                        "gaps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Identified gaps or missing capabilities"
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recommendations for the integration"
                        }
                    },
                    "required": ["title", "use_case", "verdict", "endpoints"]
                }
            },
            "required": ["report_data"]
        }
    }
]
