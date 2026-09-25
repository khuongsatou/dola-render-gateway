# Mẫu tích hợp MCP dùng chung cho nhiều sản phẩm

Tài liệu này là template trung lập để áp dụng cho nhiều website/app khác nhau. Mỗi sản phẩm có thể dùng domain, base URL, cơ chế đăng nhập, tool và quota riêng.

Không hardcode tên Banana, endpoint `/mcp`, tool `generate_image` hoặc quy tắc quota ảnh vào core dùng chung. Mọi khác biệt phải nằm trong manifest cấu hình của từng sản phẩm.

## 1. Các biến bắt buộc của một sản phẩm

| Biến | Ví dụ | Mục đích |
|---|---|---|
| `<PRODUCT_NAME>` | `Image Studio` | Tên hiển thị |
| `<PRODUCT_SLUG>` | `image-studio` | ID ổn định trong config/client |
| `<APP_BASE_URL>` | `https://app.example.com` | Giao diện người dùng |
| `<AUTH_BASE_URL>` | `https://key.example.com` | Đăng nhập/cấp phiên nếu tách host |
| `<API_BASE_URL>` | `https://api.example.com` | REST API chung |
| `<MCP_BASE_URL>` | `https://mcp.example.com` | Origin MCP public |
| `<MCP_PATH>` | `/mcp` | Streamable HTTP path |
| `<MEDIA_BASE_URL>` | `https://media.example.com` | Tải/xem output |
| `<DOCS_BASE_URL>` | `https://docs.example.com` | Tài liệu public |
| `<KEY_PREFIX>` | `imgmcp_` | Nhận diện managed key |
| `<AUTH_HEADER>` | `x-api-key` | Header xác thực MCP |
| `<PROTOCOL_VERSION>` | `2025-03-26` | MCP protocol version |
| `<RATE_LIMIT_PER_MINUTE>` | `60` | Rate limit gateway |
| `<USAGE_TIMEZONE>` | `Asia/Ho_Chi_Minh` | Bucket/reset quota |

Các base URL có thể cùng hoặc khác domain. Client phải đọc đúng trường trong manifest; không tự suy ra `MCP_BASE_URL` từ `APP_BASE_URL`.

## 2. Manifest cấu hình theo sản phẩm

Mỗi dự án tạo một manifest dựa trên `docs/mcp-integration.manifest.example.yaml`.

Manifest là nguồn dữ liệu cho:

- Trang MCP API Keys.
- Setup snippets cho MCP client.
- MCP Playground.
- Danh sách feature/tool.
- Usage Dashboard.
- Quota enforcement.
- Media/output delivery.
- Tài liệu tích hợp riêng của sản phẩm.

Ví dụ rút gọn:

```yaml
schema_version: 1
product:
  name: "<PRODUCT_NAME>"
  slug: "<PRODUCT_SLUG>"

endpoints:
  app_base_url: "<APP_BASE_URL>"
  auth_base_url: "<AUTH_BASE_URL>"
  api_base_url: "<API_BASE_URL>"
  mcp_base_url: "<MCP_BASE_URL>"
  mcp_path: "<MCP_PATH>"
  media_base_url: "<MEDIA_BASE_URL>"
  docs_base_url: "<DOCS_BASE_URL>"

mcp:
  transport: streamable-http
  protocol_version: "<PROTOCOL_VERSION>"
  auth:
    type: header
    header: "<AUTH_HEADER>"
    key_prefix: "<KEY_PREFIX>"

features:
  - id: "<FEATURE_ID>"
    label: "<FEATURE_LABEL>"
    tools: ["<PRIMARY_TOOL>"]
    result_delivery: signed_url
    quota_metric: "<SUCCESS_METRIC>"
```

## 3. Prompt chung giao cho dev hoặc AI coding agent

```text
Hãy xây dựng hệ thống cấp API key và tích hợp MCP theo manifest của sản phẩm, không hardcode domain, tên sản phẩm, tool hoặc quota.

Nguồn cấu hình:
- product.name/product.slug dùng cho nhãn UI và server ID.
- endpoints.* là các base URL độc lập; không suy diễn host này từ host khác.
- mcp.transport/protocol_version/path/auth dùng cho MCP client và gateway.
- features[] định nghĩa chức năng, tool mapping, input/output, result delivery và metric.
- quota.policies[] định nghĩa scope, metric, limit, period, consume_on và reset timezone.

Trang MCP API Keys phải có:
1. Public MCP endpoint lấy từ endpoints.mcp_base_url + endpoints.mcp_path.
2. Tạo/list/revoke managed API key; secret chỉ hiển thị một lần.
3. Setup Guide được render từ product.slug, endpoint và auth header trong manifest.
4. Playground cho phép chọn feature/tool từ manifest, render form theo input schema và gọi MCP thật.
5. Usage Dashboard render KPI theo usage.dashboard_metrics thay vì cố định cho ảnh.
6. Quota card render từng quota policy; gateway enforce quota trước khi dispatch tool.
7. Recent Activity hiển thị tool, key preview, status, latency, error code và output type; không lộ key/prompt nhạy cảm.

Backend phải:
- Tạo key bằng CSPRNG tối thiểu 256 bit, thêm key_prefix, chỉ lưu hash.
- Scope key và usage theo tenant/workspace/user theo manifest.
- Xác thực public MCP request trước rate limit/quota/upstream.
- Ghi telemetry tại gateway cho tất cả MCP client, không chỉ Playground.
- Dùng idempotency key để retry không đếm trùng.
- Không giả định output luôn là ảnh hoặc server-local path.
- Hỗ trợ result_delivery: inline_json, base64, asset_id, signed_url hoặc server_path theo feature.
- Chỉ đếm download qua asset ID/signed URL thuộc output đã được MCP tạo.

Không hoàn thành task nếu chỉ có mock UI. Phải smoke test initialize → notifications/initialized → tools/list → tools/call, kiểm tra usage/quota và chụp bằng chứng production.
```

## 4. Kiến trúc base URL

```text
User browser
  ├─ APP_BASE_URL   → giao diện
  ├─ AUTH_BASE_URL  → login/session/API-key management
  ├─ API_BASE_URL   → REST nghiệp vụ
  ├─ MCP_BASE_URL   → MCP public gateway
  ├─ MEDIA_BASE_URL → output/download
  └─ DOCS_BASE_URL  → tài liệu

MCP_BASE_URL + MCP_PATH
  → auth
  → rate limit
  → quota gate
  → telemetry
  → internal MCP upstream
  → provider/service riêng của feature
```

Quy tắc:

- Mọi URL phải là absolute URL trong manifest.
- Validate HTTPS cho public endpoint production.
- Không gửi provider secret từ client.
- Internal upstream nên nghe loopback/private network.
- CORS được cấu hình theo `allowed_origins`, không mặc định wildcard nếu dùng cookie credentials.

## 5. API quản lý API key

Tên route có thể đổi nhưng contract nên thống nhất.

### Đọc public MCP config

```http
GET <AUTH_BASE_URL>/api/mcp/config
Authorization: Bearer <USER_SESSION_TOKEN>
```

```json
{
  "ok": true,
  "product": {"name":"<PRODUCT_NAME>","slug":"<PRODUCT_SLUG>"},
  "endpoint": "<MCP_BASE_URL><MCP_PATH>",
  "transport": "streamable-http",
  "protocolVersion": "<PROTOCOL_VERSION>",
  "auth": {"type":"header","header":"<AUTH_HEADER>"},
  "features": []
}
```

Không trả provider secret, key hash, internal upstream hoặc validator function.

### List key

```http
GET <AUTH_BASE_URL>/api/mcp/keys
Authorization: Bearer <USER_SESSION_TOKEN>
```

```json
{
  "ok": true,
  "keys": [
    {
      "id": "uuid",
      "name": "Desktop client",
      "prefix": "<KEY_PREFIX>AbCd…9xYz",
      "status": "active",
      "createdAt": "...",
      "createdBy": "...",
      "lastUsedAt": "...",
      "revokedAt": "",
      "legacy": false
    }
  ]
}
```

### Tạo key

```http
POST <AUTH_BASE_URL>/api/mcp/keys
Content-Type: application/json
Authorization: Bearer <USER_SESSION_TOKEN>

{"name":"Desktop client"}
```

```json
{
  "ok": true,
  "apiKey": "<KEY_PREFIX><ONE_TIME_SECRET>",
  "key": {"id":"uuid","name":"Desktop client","prefix":"<KEY_PREFIX>AbCd…9xYz","status":"active"}
}
```

`apiKey` chỉ xuất hiện trong response tạo key.

### Revoke key

```http
DELETE <AUTH_BASE_URL>/api/mcp/keys/<KEY_ID>
Authorization: Bearer <USER_SESSION_TOKEN>
```

Revoke phải làm request MCP tiếp theo thất bại ngay.

Electron có thể dùng IPC `mcpKeys:list/create/revoke/usage` qua preload bridge thay cho REST, nhưng public contract và security rule không đổi.

## 6. Setup snippets sinh từ manifest

### Remote MCP chuẩn

```json
{
  "mcpServers": {
    "<PRODUCT_SLUG>": {
      "url": "<MCP_BASE_URL><MCP_PATH>",
      "headers": {
        "<AUTH_HEADER>": "YOUR_MCP_API_KEY"
      }
    }
  }
}
```

### VS Code

```json
{
  "servers": {
    "<PRODUCT_SLUG>": {
      "type": "http",
      "url": "<MCP_BASE_URL><MCP_PATH>",
      "headers": {
        "<AUTH_HEADER>": "YOUR_MCP_API_KEY"
      }
    }
  }
}
```

### Client chỉ nhận URL/header thủ công

```text
Server URL: <MCP_BASE_URL><MCP_PATH>
Transport: Streamable HTTP
Authentication: Custom header
<AUTH_HEADER>: YOUR_MCP_API_KEY
```

Setup Guide phải sinh runtime từ manifest, không lưu snippet domain-specific trong component dùng chung.

## 7. MCP session flow dùng chung

Header:

```http
Content-Type: application/json
Accept: application/json, text/event-stream
<AUTH_HEADER>: YOUR_MCP_API_KEY
```

Initialize:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "<PROTOCOL_VERSION>",
    "capabilities": {},
    "clientInfo": {"name":"<CLIENT_NAME>","version":"1.0.0"}
  }
}
```

Giữ `mcp-session-id` từ response, sau đó gửi:

```json
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
```

Khám phá tool:

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

Gọi tool:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "<TOOL_NAME>",
    "arguments": {}
  }
}
```

Client phải parse cả `application/json` và `text/event-stream`, đồng thời kiểm tra HTTP status, JSON-RPC `error` và `result.isError`.

## 8. Định nghĩa chức năng và tool

Mỗi feature khai báo rõ:

```yaml
- id: "<FEATURE_ID>"
  label: "<FEATURE_LABEL>"
  tools:
    - name: "<TOOL_NAME>"
      operation: "<OPERATION>"
      input_schema_ref: "#/schemas/<TOOL_NAME>_input"
      output_schema_ref: "#/schemas/<TOOL_NAME>_output"
  result_delivery: "<RESULT_DELIVERY>"
  usage_events:
    requested: "<FEATURE>_requested"
    success: "<FEATURE>_success"
    failed: "<FEATURE>_failed"
    downloaded: "<FEATURE>_download_success"
  quota_metric: "<FEATURE>_success"
```

Feature khác có thể là:

- `watermark_removal`
- `video_generation`
- `text_to_speech`
- `speech_to_text`
- `upscale`
- `search`
- `data_export`
- `automation_run`

Không dùng regex tên tool để đoán feature nếu manifest đã có mapping chính thức.

## 9. Cách trả kết quả

| `result_delivery` | Dùng khi | Client nhận |
|---|---|---|
| `inline_json` | Kết quả nhỏ | Structured JSON |
| `base64` | File nhỏ cần truyền trực tiếp | MIME + base64 |
| `asset_id` | Media/file cần quản lý | ID rồi gọi media API |
| `signed_url` | Client tải trực tiếp | URL có hạn dùng |
| `server_path` | Workflow chạy cùng host | Path nội bộ |

Public remote MCP không nên mặc định trả `server_path`. Ưu tiên `asset_id`, `signed_url` hoặc `base64` tùy kích thước.

Output schema chung:

```json
{
  "ok": true,
  "feature": "<FEATURE_ID>",
  "tool": "<TOOL_NAME>",
  "provider": "<PROVIDER>",
  "model": "<MODEL>",
  "asset": {
    "id": "asset-uuid",
    "mimeType": "application/octet-stream",
    "bytes": 123456,
    "downloadUrl": "<MEDIA_BASE_URL>/assets/asset-uuid/download"
  },
  "latencyMs": 1200
}
```

## 10. Usage Dashboard dùng chung

Telemetry được ghi tại MCP gateway sau auth.

Event schema:

```json
{
  "eventId": "uuid",
  "requestId": "idempotency-id",
  "tenantId": "tenant-uuid",
  "workspaceId": "workspace-uuid",
  "keyId": "key-uuid",
  "keyPrefix": "prefix…last4",
  "feature": "<FEATURE_ID>",
  "tool": "<TOOL_NAME>",
  "operation": "create",
  "eventType": "<METRIC_NAME>",
  "status": "success",
  "provider": "",
  "model": "",
  "bytes": 0,
  "latencyMs": 0,
  "errorCode": "",
  "createdAt": "ISO-8601"
}
```

Dashboard metrics lấy từ manifest:

```yaml
usage:
  dashboard_metrics:
    - metric: tool_call_total
      label: "Tool calls"
    - metric: "<SUCCESS_METRIC>"
      label: "Thành công"
    - metric: "<FAILED_METRIC>"
      label: "Thất bại"
    - metric: "<DOWNLOAD_METRIC>"
      label: "Tải xuống"
```

API:

```http
GET <AUTH_BASE_URL>/api/mcp/usage?period=7d&feature=all&keyId=all
Authorization: Bearer <USER_SESSION_TOKEN>
```

UI chung phải hỗ trợ:

- Hôm nay, 7 ngày, 30 ngày.
- Filter feature/tool/API key/provider.
- KPI cards sinh từ manifest.
- Quota cards cho nhiều policy.
- Series theo ngày.
- Recent Activity.
- Loading/empty/error states không chồng lên dữ liệu.

## 11. Quota policy dùng chung

```yaml
quota:
  policies:
    - id: daily_primary_feature
      metric: "<SUCCESS_METRIC>"
      scope: workspace
      period: day
      limit: 100
      consume_on: success
      timezone: "<USAGE_TIMEZONE>"
```

Các lựa chọn:

| Trường | Giá trị gợi ý |
|---|---|
| `scope` | `user`, `api_key`, `workspace`, `tenant` |
| `period` | `minute`, `hour`, `day`, `month` |
| `consume_on` | `request`, `dispatch`, `success` |
| `metric` | Metric riêng của feature |

Quota phải check atomically và giữ reservation khi request chạy đồng thời.

Lỗi chung:

```json
{
  "ok": false,
  "error": "mcp_quota_exceeded",
  "policyId": "daily_primary_feature",
  "metric": "<SUCCESS_METRIC>",
  "limit": 100,
  "used": 100,
  "remaining": 0,
  "resetAt": "ISO-8601"
}
```

## 12. Download tracking

Đếm download dựa trên `asset_id` hoặc signed URL do MCP tạo, không dựa vào raw filesystem path do client nhập.

```http
GET <MEDIA_BASE_URL>/assets/<ASSET_ID>/download
Authorization: Bearer <USER_SESSION_TOKEN_OR_ASSET_TOKEN>
```

Download success chỉ ghi khi response file hoàn tất thành công. Download retry dùng request ID/idempotency rule tùy chính sách sản phẩm.

## 13. Authentication, CORS và proxy

- MCP key không thay thế user session cho trang quản trị.
- Endpoint quản lý key/usage dùng user session và permission riêng.
- MCP transport dùng managed MCP key.
- Chấp nhận header hoặc Bearer theo manifest; không tự bật cả hai nếu policy cấm.
- Không forward public `Origin` vào loopback upstream nếu upstream dùng DNS-rebinding protection; chỉ xóa tại trusted internal hop.
- `allowed_origins` phải lấy từ manifest.
- Không dùng `Access-Control-Allow-Origin: *` cùng credentialed cookies.
- Forward `mcp-session-id` và `mcp-protocol-version`.
- Streaming endpoint nên tắt proxy buffering và tăng read timeout phù hợp tool.

## 14. Environment template

```dotenv
PRODUCT_NAME=<PRODUCT_NAME>
PRODUCT_SLUG=<PRODUCT_SLUG>

APP_BASE_URL=<APP_BASE_URL>
AUTH_BASE_URL=<AUTH_BASE_URL>
API_BASE_URL=<API_BASE_URL>
MCP_BASE_URL=<MCP_BASE_URL>
MCP_PATH=<MCP_PATH>
MEDIA_BASE_URL=<MEDIA_BASE_URL>
DOCS_BASE_URL=<DOCS_BASE_URL>

MCP_PUBLIC_ENABLED=1
MCP_AUTOSTART=1
MCP_TRANSPORT=streamable-http
MCP_INTERNAL_HOST=127.0.0.1
MCP_INTERNAL_PORT=8000
MCP_INTERNAL_UPSTREAM=http://127.0.0.1:8000
MCP_AUTH_HEADER=<AUTH_HEADER>
MCP_KEY_PREFIX=<KEY_PREFIX>
MCP_RATE_LIMIT_PER_MINUTE=<RATE_LIMIT_PER_MINUTE>
MCP_USAGE_TIMEZONE=<USAGE_TIMEZONE>
MCP_USAGE_RETENTION_DAYS=90
```

Tool/provider env nằm trong adapter của từng feature, không đưa vào template core.

## 15. Error contract chung

| HTTP | Error | Ý nghĩa |
|---:|---|---|
| 400 | `mcp_invalid_request` | Payload/JSON-RPC không hợp lệ |
| 401 | `mcp_unauthorized` | Key thiếu/sai/revoked |
| 403 | `mcp_forbidden` | Key đúng nhưng thiếu scope |
| 404 | `mcp_tool_not_found` | Tool không có trong manifest/server |
| 409 | `mcp_request_conflict` | Idempotency conflict |
| 413 | `mcp_payload_too_large` | Upload/request quá lớn |
| 429 | `mcp_rate_limited` | Vượt rate limit |
| 429 | `mcp_quota_exceeded` | Vượt quota policy |
| 502 | `mcp_upstream_error` | Upstream/provider lỗi |
| 503 | `mcp_upstream_unavailable` | Upstream chưa sẵn sàng |
| 504 | `mcp_tool_timeout` | Tool timeout |

Feature adapter có thể thêm error code riêng nhưng phải giữ envelope chung.

## 16. Security checklist

- Secret tạo bằng CSPRNG tối thiểu 256 bit.
- Chỉ lưu hash, preview và metadata.
- Constant-time hash comparison.
- Secret chỉ trả một lần.
- Storage permission `0600` hoặc database encryption/ACL tương đương.
- Không log key, Authorization, provider secret, full prompt nhạy cảm.
- Health/status không trả secret/internal callbacks.
- Tenant/workspace isolation có test.
- Revoke có hiệu lực request kế tiếp.
- Rate limit và quota enforce tại gateway.
- Idempotency chống đếm trùng.
- Media asset kiểm tra ownership/scope.
- Multi-replica dùng shared transactional store.

## 17. Smoke test chung

1. `GET health` của sản phẩm đạt ready criteria trong manifest.
2. Key sai trả 401.
3. Key đúng initialize thành công.
4. Nhận và reuse `mcp-session-id`.
5. `notifications/initialized` thành công.
6. `tools/list` khớp manifest.
7. Gọi ít nhất một tool thật cho mỗi feature chính.
8. Output delivery hoạt động đúng mode.
9. Dashboard tăng đúng requested/success/failed.
10. Download làm tăng đúng metric download.
11. Quota limit và resetAt đúng.
12. Retry cùng idempotency key không đếm trùng.
13. Revoke key rồi request kế tiếp trả 401.
14. Restart service và usage/key vẫn còn.
15. Chụp bằng chứng production, không để lộ secret.

## 18. Ba ví dụ sản phẩm

### Website tạo ảnh

```yaml
product: {name: "Image Studio", slug: "image-studio"}
endpoints:
  app_base_url: "https://image.example.com"
  mcp_base_url: "https://image-api.example.com"
  mcp_path: "/mcp"
features:
  - id: image_generation
    tools: [generate_image, edit_image]
    result_delivery: asset_id
    quota_metric: image_create_success
```

### Website xóa watermark

```yaml
product: {name: "Clean Media", slug: "clean-media"}
endpoints:
  app_base_url: "https://clean.example.com"
  mcp_base_url: "https://clean.example.com"
  mcp_path: "/mcp"
features:
  - id: watermark_removal
    tools: [inspect_image, create_mask, remove_watermark, get_result]
    result_delivery: signed_url
    quota_metric: watermark_job_success
```

### Website TTS

```yaml
product: {name: "Voice Studio", slug: "voice-studio"}
endpoints:
  app_base_url: "https://voice.example.com"
  mcp_base_url: "https://voice-api.example.com"
  mcp_path: "/mcp/v1"
features:
  - id: text_to_speech
    tools: [list_voices, generate_speech, get_speech_job]
    result_delivery: signed_url
    quota_metric: tts_character_success
```

## 19. Definition of Done

- Chỉ thay manifest là đổi được product name, base URL, auth header, tools, metrics và quota.
- Core UI/backend không chứa domain hoặc tool name của một sản phẩm cụ thể.
- API key management, MCP transport, usage và quota có test.
- Playground render form từ tool schema/manifest và gọi thật.
- Public output không phụ thuộc server-local path nếu client ở xa.
- Tài liệu riêng của mỗi sản phẩm được sinh từ manifest và có smoke proof.
