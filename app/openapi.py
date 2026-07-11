OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "HOMINSU REST API",
        "version": "1.0.0",
        "description": (
            "Interactive API documentation for the HOMINSU consumer, creator, "
            "wallet, live-streaming, and venue-operator services. Use POST "
            "/api/v1/auth/login, copy access_token, then select Authorize and "
            "enter the token to test protected endpoints."
        ),
    },
    "servers": [{"url": "/", "description": "Current Uvicorn server"}],
    "tags": [
        {"name": "System", "description": "Service discovery and health"},
        {"name": "Authentication", "description": "Login and JWT access"},
        {"name": "Catalog", "description": "VR content and live streams"},
        {"name": "Account", "description": "Profile, wallet, and purchases"},
        {"name": "Operator", "description": "Venue headset fleet control"},
    ],
    "paths": {
        "/": {
            "get": {
                "tags": ["System"], "summary": "Get API information",
                "operationId": "getApiIndex", "responses": {"200": {"description": "API information"}},
            }
        },
        "/health": {
            "get": {
                "tags": ["System"], "summary": "Check API health",
                "operationId": "getHealth", "responses": {"200": {"description": "Service is healthy"}},
            }
        },
        "/api/v1/auth/login": {
            "post": {
                "tags": ["Authentication"], "summary": "Log in and create an access token",
                "operationId": "login", "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginRequest"}, "example": {"email": "member@hominsu.local", "password": "member1234"}}},
                },
                "responses": {
                    "200": {"description": "Login succeeded", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginResponse"}}}},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                },
            }
        },
        "/api/v1/catalog/categories": {
            "get": {
                "tags": ["Catalog"], "summary": "List content categories",
                "operationId": "listCategories", "responses": {"200": {"description": "Category list"}},
            }
        },
        "/api/v1/content": {
            "get": {
                "tags": ["Catalog"], "summary": "Search and filter VR content",
                "operationId": "listContent", "parameters": [
                    {"name": "category", "in": "query", "schema": {"type": "string"}, "description": "Category slug, for example travel"},
                    {"name": "feed", "in": "query", "schema": {"type": "string", "enum": ["latest", "featured", "free"]}},
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Title or description search"},
                ],
                "responses": {"200": {"description": "Content list"}, "400": {"$ref": "#/components/responses/ValidationError"}},
            }
        },
        "/api/v1/content/{content_id}": {
            "get": {
                "tags": ["Catalog"], "summary": "Get content details",
                "operationId": "getContent", "parameters": [{"$ref": "#/components/parameters/ContentId"}],
                "responses": {"200": {"description": "Content details"}, "404": {"$ref": "#/components/responses/NotFound"}},
            }
        },
        "/api/v1/content/{content_id}/unlock": {
            "post": {
                "tags": ["Account"], "summary": "Unlock content using an ad, points, or cash",
                "operationId": "unlockContent", "security": [{"BearerAuth": []}],
                "parameters": [{"$ref": "#/components/parameters/ContentId"}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UnlockRequest"}, "example": {"method": "points"}}}},
                "responses": {
                    "200": {"description": "Content was already unlocked"}, "201": {"description": "Content unlocked"},
                    "401": {"$ref": "#/components/responses/Unauthorized"}, "409": {"description": "Insufficient funds"},
                },
            }
        },
        "/api/v1/live": {
            "get": {
                "tags": ["Catalog"], "summary": "List live and scheduled streams",
                "operationId": "listLiveStreams", "responses": {"200": {"description": "Live-stream list"}},
            }
        },
        "/api/v1/me": {
            "get": {
                "tags": ["Account"], "summary": "Get the current user profile",
                "operationId": "getCurrentUser", "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "Current user"}, "401": {"$ref": "#/components/responses/Unauthorized"}},
            }
        },
        "/api/v1/wallet": {
            "get": {
                "tags": ["Account"], "summary": "Get wallet balances",
                "operationId": "getWallet", "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "Wallet details"}, "401": {"$ref": "#/components/responses/Unauthorized"}},
            }
        },
        "/api/v1/wallet/packages": {
            "get": {
                "tags": ["Account"], "summary": "List point top-up packages",
                "operationId": "listWalletPackages", "responses": {"200": {"description": "Point package list"}},
            }
        },
        "/api/v1/wallet/topups": {
            "post": {
                "tags": ["Account"], "summary": "Credit a purchased point package",
                "operationId": "createWalletTopup", "security": [{"BearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TopupRequest"}, "example": {"package_id": 1, "reference": "swagger-payment-001"}}}},
                "responses": {
                    "201": {"description": "Top-up completed"}, "401": {"$ref": "#/components/responses/Unauthorized"},
                    "409": {"description": "Payment reference was already processed"},
                },
            }
        },
        "/api/v1/operator/devices": {
            "get": {
                "tags": ["Operator"], "summary": "List venue headsets",
                "operationId": "listDevices", "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "Device fleet"}, "403": {"$ref": "#/components/responses/Forbidden"}},
            }
        },
        "/api/v1/operator/devices/actions": {
            "post": {
                "tags": ["Operator"], "summary": "Send a bulk action to headsets",
                "operationId": "createDeviceActions", "security": [{"BearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/DeviceActionRequest"}, "example": {"device_ids": [1, 2], "action": "reboot", "payload": {}}}}},
                "responses": {"201": {"description": "Actions accepted"}, "403": {"$ref": "#/components/responses/Forbidden"}},
            }
        },
        "/api/v1/operator/sync": {
            "post": {
                "tags": ["Operator"], "summary": "Synchronize playback across headsets",
                "operationId": "syncDevices", "security": [{"BearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/DeviceSyncRequest"}, "example": {"device_ids": [1, 2], "payload": {"content_id": 1, "position_seconds": 0}}}}},
                "responses": {"201": {"description": "Synchronization accepted"}, "403": {"$ref": "#/components/responses/Forbidden"}},
            }
        },
    },
    "components": {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        },
        "parameters": {
            "ContentId": {"name": "content_id", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}}
        },
        "schemas": {
            "LoginRequest": {
                "type": "object", "required": ["email", "password"],
                "properties": {"email": {"type": "string", "format": "email"}, "password": {"type": "string", "format": "password"}},
            },
            "LoginResponse": {
                "type": "object", "properties": {"data": {"type": "object", "properties": {"access_token": {"type": "string"}, "token_type": {"type": "string"}, "user": {"type": "object"}}}}
            },
            "UnlockRequest": {"type": "object", "required": ["method"], "properties": {"method": {"type": "string", "enum": ["ad", "points", "cash"]}}},
            "TopupRequest": {
                "type": "object", "required": ["package_id", "reference"],
                "properties": {"package_id": {"type": "integer", "minimum": 1}, "reference": {"type": "string", "minLength": 1}},
            },
            "DeviceActionRequest": {
                "type": "object", "required": ["device_ids", "action"],
                "properties": {
                    "device_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "integer"}},
                    "action": {"type": "string", "enum": ["launch_content", "stop_content", "wake", "sleep", "reboot", "update", "refresh_catalog"]},
                    "payload": {"type": "object", "additionalProperties": True},
                },
            },
            "DeviceSyncRequest": {
                "type": "object", "required": ["device_ids"],
                "properties": {"device_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "integer"}}, "payload": {"type": "object", "additionalProperties": True}},
            },
            "Error": {
                "type": "object", "properties": {"error": {"type": "object", "properties": {"code": {"type": "string"}, "message": {"type": "string"}}}}
            },
        },
        "responses": {
            "Unauthorized": {"description": "Missing or invalid access token", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "Forbidden": {"description": "The account does not have the required role", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "NotFound": {"description": "Resource not found", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "ValidationError": {"description": "Request validation failed", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        },
    },
}
