# Admin RBAC Backend

Version: 0.1.0

## 基础路由：`http://localhost:8000`

## ARP/MAC采集

### 手动采集单设备

**URL**: `/api/v1/collect/collect/device/{device_id}`

**Method**: `POST`

**Description**:

立即采集指定设备的 ARP/MAC 表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Request Body (application/json)

No properties (Empty Object)

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                  | 必填 | 描述    |
| :-------- | :-------------------- | :--- | :------ |
| `code`    | `integer`             | 否   | Code    |
| `message` | `string`              | 否   | Message |
| `data`    | `DeviceCollectResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量采集设备

**URL**: `/api/v1/collect/collect/batch`

**Method**: `POST`

**Description**:

批量采集多台设备的 ARP/MAC 表。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                       |
| :------------ | :-------------- | :--- | :------------------------- |
| `device_ids`  | `Array[string]` | 是   | 设备ID列表                 |
| `collect_arp` | `boolean`       | 否   | 是否采集 ARP 表            |
| `collect_mac` | `boolean`       | 否   | 是否采集 MAC 表            |
| `otp_code`    | `string`        | 否   | OTP 验证码（如果设备需要） |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型            | 必填 | 描述    |
| :-------- | :-------------- | :--- | :------ |
| `code`    | `integer`       | 否   | Code    |
| `message` | `string`        | 否   | Message |
| `data`    | `CollectResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 异步批量采集（Celery）

**URL**: `/api/v1/collect/collect/batch/async`

**Method**: `POST`

**Description**:

提交异步批量采集任务到 Celery 队列。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                       |
| :------------ | :-------------- | :--- | :------------------------- |
| `device_ids`  | `Array[string]` | 是   | 设备ID列表                 |
| `collect_arp` | `boolean`       | 否   | 是否采集 ARP 表            |
| `collect_mac` | `boolean`       | 否   | 是否采集 MAC 表            |
| `otp_code`    | `string`        | 否   | OTP 验证码（如果设备需要） |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `CollectTaskStatus` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询采集任务状态

**URL**: `/api/v1/collect/collect/task/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 异步采集任务的执行状态。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `CollectTaskStatus` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备 ARP 表

**URL**: `/api/v1/collect/collect/device/{device_id}/arp`

**Method**: `GET`

**Description**:

获取设备缓存的 ARP 表数据。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `ARPTableResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备 MAC 表

**URL**: `/api/v1/collect/collect/device/{device_id}/mac`

**Method**: `GET`

**Description**:

获取设备缓存的 MAC 地址表数据。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `MACTableResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### IP 地址定位

**URL**: `/api/v1/collect/collect/locate/ip/{ip_address}`

**Method**: `GET`

**Description**:

根据 IP 地址查询所在设备和端口。

#### Requests Parameters (Query/Path)

| 参数名       | 位置   | 类型     | 必填 | 描述       | Default |
| :----------- | :----- | :------- | :--- | :--------- | :------ |
| `ip_address` | `path` | `string` | 是   | Ip Address |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `LocateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### MAC 地址定位

**URL**: `/api/v1/collect/collect/locate/mac/{mac_address}`

**Method**: `GET`

**Description**:

根据 MAC 地址查询所在设备和端口。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `mac_address` | `path` | `string` | 是   | Mac Address |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `LocateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Alerts

### 获取告警列表

**URL**: `/api/v1/alerts/`

**Method**: `GET`

**Description**:

获取分页过滤的告警列表。

根据提供的关键词、告警类型、严重程度、状态以及关联设备 ID 进行筛选，返回分页后的告警列表。

Args:
alert_service (AlertService): 告警服务依赖。
current_user (User): 当前登录用户。
page (int): 请求的页码，从 1 开始。默认为 1。
page_size (int): 每页显示的记录数。默认为 20。
keyword (str | None): 搜索关键词，匹配告警标题或正文。
alert_type (AlertType | None): 告警类型筛选。
severity (AlertSeverity | None): 告警严重程度筛选。
status (AlertStatus | None): 告警状态筛选。
related_device_id (UUID | None): 关联的设备 ID 筛选。

Returns:
ResponseBase[PaginatedResponse[AlertResponse]]: 包含分页后的告警数据及其总数的响应。

#### Requests Parameters (Query/Path)

| 参数名              | 位置    | 类型      | 必填 | 描述              | Default |
| :------------------ | :------ | :-------- | :--- | :---------------- | :------ |
| `page`              | `query` | `integer` | 否   | 页码              | 1       |
| `page_size`         | `query` | `integer` | 否   | 每页数量          | 20      |
| `keyword`           | `query` | `string`  | 否   | 关键词(标题/正文) |         |
| `alert_type`        | `query` | `string`  | 否   | 类型筛选          |         |
| `severity`          | `query` | `string`  | 否   | 级别筛选          |         |
| `status`            | `query` | `string`  | 否   | 状态筛选          |         |
| `related_device_id` | `query` | `string`  | 否   | 设备筛选          |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                               | 必填 | 描述    |
| :-------- | :--------------------------------- | :--- | :------ |
| `code`    | `integer`                          | 否   | Code    |
| `message` | `string`                           | 否   | Message |
| `data`    | `PaginatedResponse_AlertResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取告警详情

**URL**: `/api/v1/alerts/{alert_id}`

**Method**: `GET`

**Description**:

根据 ID 获取单个告警的详细信息。

Args:
alert_id (UUID): 告警的主键 ID。
alert_service (AlertService): 告警服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[AlertResponse]: 包含告警详情数据的响应。

#### Requests Parameters (Query/Path)

| 参数名     | 位置   | 类型     | 必填 | 描述     | Default |
| :--------- | :----- | :------- | :--- | :------- | :------ |
| `alert_id` | `path` | `string` | 是   | Alert Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型            | 必填 | 描述    |
| :-------- | :-------------- | :--- | :------ |
| `code`    | `integer`       | 否   | Code    |
| `message` | `string`        | 否   | Message |
| `data`    | `AlertResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 确认告警

**URL**: `/api/v1/alerts/{alert_id}/ack`

**Method**: `POST`

**Description**:

确认指定的告警。

将被选中的告警状态更新为“已确认”，并记录处理人信息。

Args:
alert_id (UUID): 告警的主键 ID。
alert_service (AlertService): 告警服务依赖。
current_user (User): 当前执行确认操作的用户。

Returns:
ResponseBase[AlertResponse]: 更新状态后的告警详情。

#### Requests Parameters (Query/Path)

| 参数名     | 位置   | 类型     | 必填 | 描述     | Default |
| :--------- | :----- | :------- | :--- | :------- | :------ |
| `alert_id` | `path` | `string` | 是   | Alert Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型            | 必填 | 描述    |
| :-------- | :-------------- | :--- | :------ |
| `code`    | `integer`       | 否   | Code    |
| `message` | `string`        | 否   | Message |
| `data`    | `AlertResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 关闭告警

**URL**: `/api/v1/alerts/{alert_id}/close`

**Method**: `POST`

**Description**:

关闭指定的告警。

将被选中的告警状态更新为“已关闭”，表示告警已处理完毕或已恢复。

Args:
alert_id (UUID): 告警的主键 ID。
alert_service (AlertService): 告警服务依赖。
current_user (User): 当前执行关闭操作的用户。

Returns:
ResponseBase[AlertResponse]: 状态更新后的告警详情。

#### Requests Parameters (Query/Path)

| 参数名     | 位置   | 类型     | 必填 | 描述     | Default |
| :--------- | :----- | :------- | :--- | :------- | :------ |
| `alert_id` | `path` | `string` | 是   | Alert Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型            | 必填 | 描述    |
| :-------- | :-------------- | :--- | :------ |
| `code`    | `integer`       | 否   | Code    |
| `message` | `string`        | 否   | Message |
| `data`    | `AlertResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Auth

### 用户登录

**URL**: `/api/v1/auth/login`

**Method**: `POST`

**Description**:

OAuth2 兼容的 Token 登录接口。

验证用户名和密码，返回短期有效的 Access Token 和长期有效的 Refresh Token。
每个 IP 每分钟最多允许 5 次请求。

Args:
request (Request): 请求对象，用于获取 IP 地址。
background_tasks (BackgroundTasks): 后台任务，用于异步记录登录日志。
form_data (OAuth2PasswordRequestForm): 表单数据，包含 username 和 password。
auth_service (AuthService): 认证服务依赖。

Returns:
TokenAccess: 包含 Access Token 和 Refresh Token 的响应对象。

Raises:
CustomException: 当用户名或密码错误时抛出 400 错误。

#### Request Body (application/x-www-form-urlencoded)

| 参数名          | 类型     | 必填 | 描述          |
| :-------------- | :------- | :--- | :------------ |
| `grant_type`    | `string` | 否   | Grant Type    |
| `username`      | `string` | 是   | Username      |
| `password`      | `string` | 是   | Password      |
| `scope`         | `string` | 否   | Scope         |
| `client_id`     | `string` | 否   | Client Id     |
| `client_secret` | `string` | 否   | Client Secret |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名         | 类型     | 必填 | 描述         |
| :------------- | :------- | :--- | :----------- |
| `access_token` | `string` | 是   | Access Token |
| `token_type`   | `string` | 是   | Token Type   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 刷新令牌

**URL**: `/api/v1/auth/refresh`

**Method**: `POST`

**Description**:

使用 Refresh Token 换取新的 Access Token。

当 Access Token 过期时，可以使用此接口获取新的 Access Token，而无需重新登录。

Args:
token_in (TokenRefresh): 包含 refresh_token 的请求体。
auth_service (AuthService): 认证服务依赖。

Returns:
Token: 包含新的 Access Token 和 (可选) 新的 Refresh Token。

Raises:
UnauthorizedException: 当 Refresh Token 无效或过期时抛出 401 错误。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名         | 类型     | 必填 | 描述         |
| :------------- | :------- | :--- | :----------- |
| `access_token` | `string` | 是   | Access Token |
| `token_type`   | `string` | 是   | Token Type   |

---

### 测试令牌有效性

**URL**: `/api/v1/auth/test-token`

**Method**: `POST`

**Description**:

测试 Access Token 是否有效。

仅用于验证当前请求携带的 Token 是否合法，并返回当前用户信息。

Args:
current_user (User): 当前登录用户 (由依赖自动注入)。

Returns:
ResponseBase[UserResponse]: 包含当前用户信息的统一响应结构。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

---

### 用户退出登录

**URL**: `/api/v1/auth/logout`

**Method**: `POST`

**Description**:

退出登录。

后端撤销当前用户的 refresh 会话（Refresh Token Rotation 场景下，撤销后 refresh 将不可再用于刷新）。
Access Token 理论上仍可能在过期前短暂可用，但前端应立即清理并停止使用。
Args:
response (Response): 响应对象，用于清理认证相关的 Cookie。
current_user (User): 当前登录用户 (由依赖自动注入)。
auth_service (AuthService): 认证服务依赖。
Returns:
ResponseBase[None]: 统一响应结构，data 为空。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `null`    | 否   | Data    |

---

## Backups

### 获取备份列表

**URL**: `/api/v1/backups/backups/`

**Method**: `GET`

**Description**:

获取分页过滤的配置备份列表。

#### Requests Parameters (Query/Path)

| 参数名        | 位置    | 类型      | 必填 | 描述         | Default |
| :------------ | :------ | :-------- | :--- | :----------- | :------ |
| `page`        | `query` | `integer` | 否   | 页码         | 1       |
| `page_size`   | `query` | `integer` | 否   | 每页数量     | 20      |
| `device_id`   | `query` | `string`  | 否   | 设备ID筛选   |         |
| `backup_type` | `query` | `string`  | 否   | 备份类型筛选 |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                | 必填 | 描述    |
| :-------- | :---------------------------------- | :--- | :------ |
| `code`    | `integer`                           | 否   | Code    |
| `message` | `string`                            | 否   | Message |
| `data`    | `PaginatedResponse_BackupResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取备份详情

**URL**: `/api/v1/backups/backups/{backup_id}`

**Method**: `GET`

**Description**:

根据 ID 获取备份详情。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `BackupResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除备份

**URL**: `/api/v1/backups/backups/{backup_id}`

**Method**: `DELETE`

**Description**:

软删除指定的备份记录。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `object`  | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取备份配置内容

**URL**: `/api/v1/backups/backups/{backup_id}/content`

**Method**: `GET`

**Description**:

获取备份的完整配置内容。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                    | 必填 | 描述    |
| :-------- | :---------------------- | :--- | :------ |
| `code`    | `integer`               | 否   | Code    |
| `message` | `string`                | 否   | Message |
| `data`    | `BackupContentResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 手动备份单设备

**URL**: `/api/v1/backups/backups/device/{device_id}`

**Method**: `POST`

**Description**:

立即备份指定设备的配置。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Request Body (application/json)

No properties (Empty Object)

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `BackupResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量备份设备

**URL**: `/api/v1/backups/backups/batch`

**Method**: `POST`

**Description**:

批量备份多台设备配置（支持断点续传）。

#### Request Body (application/json)

| 参数名            | 类型            | 必填 | 描述               |
| :---------------- | :-------------- | :--- | :----------------- |
| `device_ids`      | `Array[string]` | 是   | 设备ID列表         |
| `backup_type`     | `BackupType`    | 否   | 备份类型           |
| `resume_task_id`  | `string`        | 否   | 断点续传任务ID     |
| `skip_device_ids` | `array`         | 否   | 跳过已成功的设备ID |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `BackupBatchResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询备份任务状态

**URL**: `/api/v1/backups/backups/task/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 异步备份任务的执行状态。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `BackupTaskStatus` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备最新备份

**URL**: `/api/v1/backups/backups/device/{device_id}/latest`

**Method**: `GET`

**Description**:

获取指定设备的最新成功备份。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `BackupResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备备份历史

**URL**: `/api/v1/backups/backups/device/{device_id}/history`

**Method**: `GET`

**Description**:

获取指定设备的备份历史列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `device_id` | `path`  | `string`  | 是   | Device Id |         |
| `page`      | `query` | `integer` | 否   | 页码      | 1       |
| `page_size` | `query` | `integer` | 否   | 每页数量  | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                | 必填 | 描述    |
| :-------- | :---------------------------------- | :--- | :------ |
| `code`    | `integer`                           | 否   | Code    |
| `message` | `string`                            | 否   | Message |
| `data`    | `PaginatedResponse_BackupResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 下载备份配置文件

**URL**: `/api/v1/backups/backups/{backup_id}/download`

**Method**: `GET`

**Description**:

将备份配置内容导出为文件下载。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Collect

### 手动采集单设备

**URL**: `/api/v1/collect/collect/device/{device_id}`

**Method**: `POST`

**Description**:

立即采集指定设备的 ARP/MAC 表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Request Body (application/json)

No properties (Empty Object)

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                  | 必填 | 描述    |
| :-------- | :-------------------- | :--- | :------ |
| `code`    | `integer`             | 否   | Code    |
| `message` | `string`              | 否   | Message |
| `data`    | `DeviceCollectResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量采集设备

**URL**: `/api/v1/collect/collect/batch`

**Method**: `POST`

**Description**:

批量采集多台设备的 ARP/MAC 表。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                       |
| :------------ | :-------------- | :--- | :------------------------- |
| `device_ids`  | `Array[string]` | 是   | 设备ID列表                 |
| `collect_arp` | `boolean`       | 否   | 是否采集 ARP 表            |
| `collect_mac` | `boolean`       | 否   | 是否采集 MAC 表            |
| `otp_code`    | `string`        | 否   | OTP 验证码（如果设备需要） |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型            | 必填 | 描述    |
| :-------- | :-------------- | :--- | :------ |
| `code`    | `integer`       | 否   | Code    |
| `message` | `string`        | 否   | Message |
| `data`    | `CollectResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 异步批量采集（Celery）

**URL**: `/api/v1/collect/collect/batch/async`

**Method**: `POST`

**Description**:

提交异步批量采集任务到 Celery 队列。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                       |
| :------------ | :-------------- | :--- | :------------------------- |
| `device_ids`  | `Array[string]` | 是   | 设备ID列表                 |
| `collect_arp` | `boolean`       | 否   | 是否采集 ARP 表            |
| `collect_mac` | `boolean`       | 否   | 是否采集 MAC 表            |
| `otp_code`    | `string`        | 否   | OTP 验证码（如果设备需要） |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `CollectTaskStatus` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询采集任务状态

**URL**: `/api/v1/collect/collect/task/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 异步采集任务的执行状态。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `CollectTaskStatus` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备 ARP 表

**URL**: `/api/v1/collect/collect/device/{device_id}/arp`

**Method**: `GET`

**Description**:

获取设备缓存的 ARP 表数据。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `ARPTableResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备 MAC 表

**URL**: `/api/v1/collect/collect/device/{device_id}/mac`

**Method**: `GET`

**Description**:

获取设备缓存的 MAC 地址表数据。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `MACTableResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### IP 地址定位

**URL**: `/api/v1/collect/collect/locate/ip/{ip_address}`

**Method**: `GET`

**Description**:

根据 IP 地址查询所在设备和端口。

#### Requests Parameters (Query/Path)

| 参数名       | 位置   | 类型     | 必填 | 描述       | Default |
| :----------- | :----- | :------- | :--- | :--------- | :------ |
| `ip_address` | `path` | `string` | 是   | Ip Address |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `LocateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### MAC 地址定位

**URL**: `/api/v1/collect/collect/locate/mac/{mac_address}`

**Method**: `GET`

**Description**:

根据 MAC 地址查询所在设备和端口。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `mac_address` | `path` | `string` | 是   | Mac Address |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `LocateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Credentials

### 获取凭据列表

**URL**: `/api/v1/credentials/`

**Method**: `GET`

**Description**:

查询凭据列表（分页）。

支持按部门和设备分组进行过滤。

Args:
credential_service (CredentialService): 凭据服务依赖。
current_user (User): 当前登录用户。
page (int): 页码。
page_size (int): 每页数量。
dept_id (UUID | None): 部门 ID 筛选。
device_group (DeviceGroup | None): 设备分组筛选。

Returns:
ResponseBase[PaginatedResponse[DeviceGroupCredentialResponse]]: 分页后的凭据列表响应。

#### Requests Parameters (Query/Path)

| 参数名         | 位置    | 类型      | 必填 | 描述         | Default |
| :------------- | :------ | :-------- | :--- | :----------- | :------ |
| `page`         | `query` | `integer` | 否   | 页码         | 1       |
| `page_size`    | `query` | `integer` | 否   | 每页数量     | 20      |
| `dept_id`      | `query` | `string`  | 否   | 部门筛选     |         |
| `device_group` | `query` | `string`  | 否   | 设备分组筛选 |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                               | 必填 | 描述    |
| :-------- | :------------------------------------------------- | :--- | :------ |
| `code`    | `integer`                                          | 否   | Code    |
| `message` | `string`                                           | 否   | Message |
| `data`    | `PaginatedResponse_DeviceGroupCredentialResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建凭据

**URL**: `/api/v1/credentials/`

**Method**: `POST`

**Description**:

创建设备分组凭据。

每个“部门 + 设备分组”组合只能有一个凭据。OTP 种子将被加密存储。

Args:
obj_in (DeviceGroupCredentialCreate): 创建凭据的请求数据。
credential_service (CredentialService): 凭据服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceGroupCredentialResponse]: 创建成功后的凭据详情。

#### Request Body (application/json)

| 参数名         | 类型          | 必填 | 描述                         |
| :------------- | :------------ | :--- | :--------------------------- |
| `dept_id`      | `string`      | 是   | 部门ID                       |
| `device_group` | `DeviceGroup` | 是   | 设备分组                     |
| `username`     | `string`      | 是   | SSH 账号                     |
| `otp_seed`     | `string`      | 否   | OTP 种子（明文，存储时加密） |
| `auth_type`    | `AuthType`    | 否   | 认证类型                     |
| `description`  | `string`      | 否   | 凭据描述                     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                            | 必填 | 描述    |
| :-------- | :------------------------------ | :--- | :------ |
| `code`    | `integer`                       | 否   | Code    |
| `message` | `string`                        | 否   | Message |
| `data`    | `DeviceGroupCredentialResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取凭据详情

**URL**: `/api/v1/credentials/{credential_id}`

**Method**: `GET`

**Description**:

根据 ID 获取凭据详情。

Args:
credential_id (UUID): 凭据 ID。
credential_service (CredentialService): 凭据服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceGroupCredentialResponse]: 凭据详情响应。

#### Requests Parameters (Query/Path)

| 参数名          | 位置   | 类型     | 必填 | 描述          | Default |
| :-------------- | :----- | :------- | :--- | :------------ | :------ |
| `credential_id` | `path` | `string` | 是   | Credential Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                            | 必填 | 描述    |
| :-------- | :------------------------------ | :--- | :------ |
| `code`    | `integer`                       | 否   | Code    |
| `message` | `string`                        | 否   | Message |
| `data`    | `DeviceGroupCredentialResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新凭据

**URL**: `/api/v1/credentials/{credential_id}`

**Method**: `PUT`

**Description**:

更新凭据信息。

如果提供了新的 OTP 种子，将覆盖原有种子。

Args:
credential_id (UUID): 凭据 ID。
obj_in (DeviceGroupCredentialUpdate): 更新内容。
credential_service (CredentialService): 凭据服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceGroupCredentialResponse]: 更新后的凭据详情。

#### Requests Parameters (Query/Path)

| 参数名          | 位置   | 类型     | 必填 | 描述          | Default |
| :-------------- | :----- | :------- | :--- | :------------ | :------ |
| `credential_id` | `path` | `string` | 是   | Credential Id |         |

#### Request Body (application/json)

| 参数名        | 类型       | 必填 | 描述                         |
| :------------ | :--------- | :--- | :--------------------------- |
| `username`    | `string`   | 否   | SSH 账号                     |
| `otp_seed`    | `string`   | 否   | OTP 种子（明文，存储时加密） |
| `auth_type`   | `AuthType` | 否   | 认证类型                     |
| `description` | `string`   | 否   | 凭据描述                     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                            | 必填 | 描述    |
| :-------- | :------------------------------ | :--- | :------ |
| `code`    | `integer`                       | 否   | Code    |
| `message` | `string`                        | 否   | Message |
| `data`    | `DeviceGroupCredentialResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除凭据

**URL**: `/api/v1/credentials/{credential_id}`

**Method**: `DELETE`

**Description**:

删除凭据（软删除）。

Args:
credential_id (UUID): 凭据 ID。
credential_service (CredentialService): 凭据服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceGroupCredentialResponse]: 已删除的凭据简要信息。

#### Requests Parameters (Query/Path)

| 参数名          | 位置   | 类型     | 必填 | 描述          | Default |
| :-------------- | :----- | :------- | :--- | :------------ | :------ |
| `credential_id` | `path` | `string` | 是   | Credential Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                            | 必填 | 描述    |
| :-------- | :------------------------------ | :--- | :------ |
| `code`    | `integer`                       | 否   | Code    |
| `message` | `string`                        | 否   | Message |
| `data`    | `DeviceGroupCredentialResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 缓存 OTP 验证码

**URL**: `/api/v1/credentials/otp/cache`

**Method**: `POST`

**Description**:

缓存用户手动输入的 OTP 验证码。

该验证码将在 Redis 中短期缓存，供批量设备登录使用。仅对指定了手动输入 OTP 的分组有效。

Args:
request (OTPCacheRequest): 包含凭据标识和 OTP 验证码的请求。
credential_service (CredentialService): 凭据服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[OTPCacheResponse]: 缓存结果详情。

#### Request Body (application/json)

| 参数名         | 类型          | 必填 | 描述       |
| :------------- | :------------ | :--- | :--------- |
| `dept_id`      | `string`      | 是   | 部门ID     |
| `device_group` | `DeviceGroup` | 是   | 设备分组   |
| `otp_code`     | `string`      | 是   | OTP 验证码 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `OTPCacheResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Dashboard

### 获取仪表盘统计

**URL**: `/api/v1/dashboard/summary`

**Method**: `GET`

**Description**:

获取仪表盘统计数据。

聚合查询用户、角色、菜单的总量，以及今日登录/操作次数、近七日登录趋势和最新登录记录。
数据用于前端仪表盘首页展示。

Args:
current_user (User): 当前登录用户。
service (DashboardService): 仪表盘服务依赖。

Returns:
ResponseBase[DashboardStats]: 包含各项统计指标的响应对象。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DashboardStats` | 否   |         |

---

## Deploy

### 创建下发任务

**URL**: `/api/v1/deploy/deploy/`

**Method**: `POST`

**Description**:

创建批量设备配置下发任务。

通过指定渲染后的配置内容和目标设备，并在正式下发前创建多级审批流。

Args:
body (DeployCreateRequest): 包含任务名称、描述、目标设备及下发内容的请求。
service (DeployService): 下发服务依赖。
user (User): 任务提交人。

Returns:
ResponseBase[DeployTaskResponse]: 包含初始状态及审批进度的任务详情。

#### Request Body (application/json)

| 参数名               | 类型            | 必填 | 描述                             |
| :------------------- | :-------------- | :--- | :------------------------------- |
| `name`               | `string`        | 是   | Name                             |
| `description`        | `string`        | 否   | Description                      |
| `template_id`        | `string`        | 是   | 模板ID                           |
| `template_params`    | `object`        | 否   | 模板参数                         |
| `device_ids`         | `Array[string]` | 是   | 目标设备ID列表                   |
| `change_description` | `string`        | 否   | 变更说明                         |
| `impact_scope`       | `string`        | 否   | 影响范围                         |
| `rollback_plan`      | `string`        | 否   | 回退方案                         |
| `approver_ids`       | `array`         | 否   | 三级审批人ID列表（长度=3，可选） |
| `deploy_plan`        | `DeployPlan`    | 否   |                                  |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 下发任务列表（复用 Task 表）

**URL**: `/api/v1/deploy/deploy/`

**Method**: `GET`

**Description**:

获取所有批量配置下发任务的列表。

Args:
service (DeployService): 下发服务依赖。
page (int): 当前页码。
page_size (int): 每页限制数量。

Returns:
ResponseBase[PaginatedResponse[DeployTaskResponse]]: 分页后的任务概览。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                    | 必填 | 描述    |
| :-------- | :-------------------------------------- | :--- | :------ |
| `code`    | `integer`                               | 否   | Code    |
| `message` | `string`                                | 否   | Message |
| `data`    | `PaginatedResponse_DeployTaskResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 审批(某一级)

**URL**: `/api/v1/deploy/deploy/{task_id}/approve`

**Method**: `POST`

**Description**:

对指定的下发任务进行单级审批操作。

支持多级审批逻辑。如果所有级别均已通过，任务状态将更新为“已审批”。

Args:
task_id (UUID): 任务 ID。
body (DeployApproveRequest): 包含审批级别、审批结论 (通过/拒绝) 及意见。
service (DeployService): 下发服务依赖。
user (User): 当前审批人。

Returns:
ResponseBase[DeployTaskResponse]: 更新后的任务及审批进度。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Request Body (application/json)

| 参数名    | 类型      | 必填 | 描述                 |
| :-------- | :-------- | :--- | :------------------- |
| `level`   | `integer` | 是   | Level                |
| `approve` | `boolean` | 是   | true=通过 false=拒绝 |
| `comment` | `string`  | 否   | Comment              |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 执行下发任务（提交 Celery）

**URL**: `/api/v1/deploy/deploy/{task_id}/execute`

**Method**: `POST`

**Description**:

执行已审批通过的下发任务。

该接口会将执行逻辑委托给 Celery 异步队列，避免前端长连接阻塞。

Args:
task_id (UUID): 任务 ID。
service (DeployService): 下发服务依赖。

Raises:
BadRequestException: 如果任务类型不匹配或任务未处于“已审批”状态。

Returns:
ResponseBase[DeployTaskResponse]: 已绑定 Celery 任务 ID 的详情。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 触发回滚（Celery）

**URL**: `/api/v1/deploy/deploy/{task_id}/rollback`

**Method**: `POST`

**Description**:

对发生故障或需要撤回的下发任务进行回滚操作。

回滚通常通过在设备上执行反向指令或还原历史配置实现（具体视设备支持而定）。

Args:
task_id (UUID): 原下发任务 ID。

Returns:
ResponseBase[DeployRollbackResponse]: 包含回滚 Celery 任务 ID 的响应。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                     | 必填 | 描述    |
| :-------- | :----------------------- | :--- | :------ |
| `code`    | `integer`                | 否   | Code    |
| `message` | `string`                 | 否   | Message |
| `data`    | `DeployRollbackResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 下发任务详情

**URL**: `/api/v1/deploy/deploy/{task_id}`

**Method**: `GET`

**Description**:

获取下发任务的完整详细信息。

Args:
task_id (UUID): 任务 ID。
service (DeployService): 下发服务依赖。

Returns:
ResponseBase[DeployTaskResponse]: 包含设备下发日志及状态的详细数据。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Depts

### 获取部门树

**URL**: `/api/v1/depts/tree`

**Method**: `GET`

**Description**:

获取部门树结构。

Args:
current_user (User): 当前登录用户。
dept_service (DeptService): 部门服务依赖。
keyword (str | None, optional): 关键词过滤(部门名称/编码/负责人). Defaults to None.
is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[list[DeptResponse]]: 部门树。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型     | 必填 | 描述      | Default |
| :---------- | :------ | :------- | :--- | :-------- | :------ |
| `keyword`   | `query` | `string` | 否   | Keyword   |         |
| `is_active` | `query` | `string` | 否   | Is Active |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取部门列表

**URL**: `/api/v1/depts/`

**Method**: `GET`

**Description**:

获取部门列表（分页）。

Args:
current_user (User): 当前登录用户。
dept_service (DeptService): 部门服务依赖。
page (int, optional): 页码. Defaults to 1.
page_size (int, optional): 每页数量. Defaults to 20.
keyword (str | None, optional): 关键词过滤. Defaults to None.
is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[DeptResponse]]: 分页后的部门列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |
| `is_active` | `query` | `string`  | 否   | Is Active |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_DeptResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建部门

**URL**: `/api/v1/depts/`

**Method**: `POST`

**Description**:

创建新部门。

Args:
dept_in (DeptCreate): 部门创建数据。
current_user (User): 当前登录用户。
dept_service (DeptService): 部门服务依赖。

Returns:
ResponseBase[DeptResponse]: 创建成功的部门对象。

#### Request Body (application/json)

| 参数名      | 类型      | 必填 | 描述     |
| :---------- | :-------- | :--- | :------- |
| `name`      | `string`  | 是   | 部门名称 |
| `code`      | `string`  | 是   | 部门编码 |
| `parent_id` | `string`  | 否   | 父部门ID |
| `sort`      | `integer` | 否   | 排序     |
| `leader`    | `string`  | 否   | 负责人   |
| `phone`     | `string`  | 否   | 联系电话 |
| `email`     | `string`  | 否   | 联系邮箱 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `DeptResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新部门

**URL**: `/api/v1/depts/{id}`

**Method**: `PUT`

**Description**:

更新部门。

Args:
id (UUID): 部门 ID。
dept_in (DeptUpdate): 部门更新数据。
current_user (User): 当前登录用户。
dept_service (DeptService): 部门服务依赖。

Returns:
ResponseBase[DeptResponse]: 更新后的部门对象。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Request Body (application/json)

| 参数名      | 类型      | 必填 | 描述     |
| :---------- | :-------- | :--- | :------- |
| `name`      | `string`  | 否   | 部门名称 |
| `code`      | `string`  | 否   | 部门编码 |
| `parent_id` | `string`  | 否   | 父部门ID |
| `sort`      | `integer` | 否   | 排序     |
| `leader`    | `string`  | 否   | 负责人   |
| `phone`     | `string`  | 否   | 联系电话 |
| `email`     | `string`  | 否   | 联系邮箱 |
| `is_active` | `boolean` | 否   | 是否启用 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `DeptResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除部门

**URL**: `/api/v1/depts/{id}`

**Method**: `DELETE`

**Description**:

删除部门（软删除）。

Args:
id (UUID): 部门 ID。
current_user (User): 当前登录用户。
dept_service (DeptService): 部门服务依赖。

Returns:
ResponseBase[DeptResponse]: 删除后的部门对象。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `DeptResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量删除部门

**URL**: `/api/v1/depts/batch`

**Method**: `DELETE`

**Description**:

批量删除部门。

Args:
request (BatchDeleteRequest): 批量删除请求体。
current_user (User): 当前登录用户。
dept_service (DeptService): 部门服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量操作结果。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                    |
| :------------ | :-------------- | :--- | :---------------------- |
| `ids`         | `Array[string]` | 是   | 要删除的 ID 列表        |
| `hard_delete` | `boolean`       | 否   | 是否硬删除 (默认软删除) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取部门回收站列表

**URL**: `/api/v1/depts/recycle-bin`

**Method**: `GET`

**Description**:

获取已删除的部门列表（回收站）。
仅限超级管理员。

Args:
page (int, optional): 页码. Defaults to 1.
page_size (int, optional): 每页数量. Defaults to 20.
active_superuser (User): 超级管理员权限验证。
dept_service (DeptService): 部门服务依赖。
keyword (str | None, optional): 关键词过滤. Defaults to None.
is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[DeptResponse]]: 分页后的回收站部门列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |
| `is_active` | `query` | `string`  | 否   | Is Active |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_DeptResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量恢复部门

**URL**: `/api/v1/depts/batch/restore`

**Method**: `POST`

**Description**:

批量恢复部门。
需要超级管理员权限。

Args:
request (BatchRestoreRequest): 批量恢复请求体。
active_superuser (User): 超级管理员权限验证。
dept_service (DeptService): 部门服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量恢复结果。

#### Request Body (application/json)

| 参数名 | 类型            | 必填 | 描述             |
| :----- | :-------------- | :--- | :--------------- |
| `ids`  | `Array[string]` | 是   | 要恢复的 ID 列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 恢复已删除部门

**URL**: `/api/v1/depts/{id}/restore`

**Method**: `POST`

**Description**:

恢复已删除部门。
需要超级管理员权限。

Args:
id (UUID): 部门 ID。
active_superuser (User): 超级管理员权限验证。
dept_service (DeptService): 部门服务依赖。

Returns:
ResponseBase[DeptResponse]: 恢复后的部门对象。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `DeptResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Devices

### 获取设备列表

**URL**: `/api/v1/devices/`

**Method**: `GET`

**Description**:

查询设备列表（分页）。

支持按关键词、厂商、状态、设备分组、部门筛选。

Args:
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。
page (int): 页码。
page_size (int): 每页数量。
keyword (str | None): 搜索关键词，匹配名称、IP 或序列号。
vendor (DeviceVendor | None): 厂商筛选。
status (DeviceStatus | None): 状态筛选。
device_group (DeviceGroup | None): 设备分组筛选。
dept_id (UUID | None): 部门 ID 筛选。

Returns:
ResponseBase[PaginatedResponse[DeviceResponse]]: 分页后的设备列表响应。

#### Requests Parameters (Query/Path)

| 参数名         | 位置    | 类型      | 必填 | 描述         | Default |
| :------------- | :------ | :-------- | :--- | :----------- | :------ |
| `page`         | `query` | `integer` | 否   | 页码         | 1       |
| `page_size`    | `query` | `integer` | 否   | 每页数量     | 20      |
| `keyword`      | `query` | `string`  | 否   | 搜索关键词   |         |
| `vendor`       | `query` | `string`  | 否   | 厂商筛选     |         |
| `status`       | `query` | `string`  | 否   | 状态筛选     |         |
| `device_group` | `query` | `string`  | 否   | 设备分组筛选 |         |
| `dept_id`      | `query` | `string`  | 否   | 部门筛选     |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                | 必填 | 描述    |
| :-------- | :---------------------------------- | :--- | :------ |
| `code`    | `integer`                           | 否   | Code    |
| `message` | `string`                            | 否   | Message |
| `data`    | `PaginatedResponse_DeviceResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建设备

**URL**: `/api/v1/devices/`

**Method**: `POST`

**Description**:

添加单一新设备。

Args:
obj_in (DeviceCreate): 设备属性数据。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceResponse]: 创建成功后的设备详情。

#### Request Body (application/json)

| 参数名          | 类型           | 必填 | 描述                                       |
| :-------------- | :------------- | :--- | :----------------------------------------- |
| `name`          | `string`       | 是   | 设备名称/主机名                            |
| `ip_address`    | `string`       | 是   | IP 地址                                    |
| `vendor`        | `DeviceVendor` | 否   | 厂商                                       |
| `model`         | `string`       | 否   | 设备型号                                   |
| `platform`      | `string`       | 否   | 平台类型                                   |
| `location`      | `string`       | 否   | 物理位置                                   |
| `description`   | `string`       | 否   | 设备描述                                   |
| `ssh_port`      | `integer`      | 否   | SSH 端口                                   |
| `auth_type`     | `AuthType`     | 否   | 认证类型                                   |
| `dept_id`       | `string`       | 否   | 所属部门ID                                 |
| `device_group`  | `DeviceGroup`  | 否   | 设备分组                                   |
| `status`        | `DeviceStatus` | 否   | 设备状态                                   |
| `username`      | `string`       | 否   | SSH 用户名(仅 static 类型)                 |
| `password`      | `string`       | 否   | SSH 密码(仅 static 类型，明文，存储时加密) |
| `serial_number` | `string`       | 否   | 序列号                                     |
| `os_version`    | `string`       | 否   | 操作系统版本                               |
| `stock_in_at`   | `string`       | 否   | 入库时间                                   |
| `assigned_to`   | `string`       | 否   | 领用人                                     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DeviceResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取回收站设备

**URL**: `/api/v1/devices/recycle-bin`

**Method**: `GET`

**Description**:

查询回收站中的设备列表（分页）。

Args:
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。
page (int): 页码。
page_size (int): 每页数量。

Returns:
ResponseBase[PaginatedResponse[DeviceResponse]]: 分页后的已删除设备列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述     | Default |
| :---------- | :------ | :-------- | :--- | :------- | :------ |
| `page`      | `query` | `integer` | 否   | 页码     | 1       |
| `page_size` | `query` | `integer` | 否   | 每页数量 | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                | 必填 | 描述    |
| :-------- | :---------------------------------- | :--- | :------ |
| `code`    | `integer`                           | 否   | Code    |
| `message` | `string`                            | 否   | Message |
| `data`    | `PaginatedResponse_DeviceResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备详情

**URL**: `/api/v1/devices/{device_id}`

**Method**: `GET`

**Description**:

根据 ID 获取设备详情。

Args:
device_id (UUID): 设备的主键 ID。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceResponse]: 设备详情数据。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DeviceResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新设备

**URL**: `/api/v1/devices/{device_id}`

**Method**: `PUT`

**Description**:

更新指定设备的信息。

Args:
device_id (UUID): 设备 ID。
obj_in (DeviceUpdate): 更新字段。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceResponse]: 更新后的设备详情。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Request Body (application/json)

| 参数名          | 类型           | 必填 | 描述                       |
| :-------------- | :------------- | :--- | :------------------------- |
| `name`          | `string`       | 否   | 设备名称                   |
| `ip_address`    | `string`       | 否   | IP 地址                    |
| `vendor`        | `DeviceVendor` | 否   | 厂商                       |
| `model`         | `string`       | 否   | 设备型号                   |
| `platform`      | `string`       | 否   | 平台类型                   |
| `location`      | `string`       | 否   | 物理位置                   |
| `description`   | `string`       | 否   | 设备描述                   |
| `ssh_port`      | `integer`      | 否   | SSH 端口                   |
| `auth_type`     | `AuthType`     | 否   | 认证类型                   |
| `username`      | `string`       | 否   | SSH 用户名                 |
| `password`      | `string`       | 否   | SSH 密码(明文，存储时加密) |
| `dept_id`       | `string`       | 否   | 所属部门ID                 |
| `device_group`  | `DeviceGroup`  | 否   | 设备分组                   |
| `status`        | `DeviceStatus` | 否   | 设备状态                   |
| `serial_number` | `string`       | 否   | 序列号                     |
| `os_version`    | `string`       | 否   | 操作系统版本               |
| `stock_in_at`   | `string`       | 否   | 入库时间                   |
| `assigned_to`   | `string`       | 否   | 领用人                     |
| `retired_at`    | `string`       | 否   | 报废时间                   |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DeviceResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除设备

**URL**: `/api/v1/devices/{device_id}`

**Method**: `DELETE`

**Description**:

删除设备（软删除）。

设备将被移至回收站，不会从数据库物理删除。

Args:
device_id (UUID): 设备 ID。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceResponse]: 被删除设备的简要数据。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DeviceResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量创建设备

**URL**: `/api/v1/devices/batch`

**Method**: `POST`

**Description**:

批量创建设备（导入）。

单次最多支持 500 个设备。逻辑上会跳过重复项或记录错误。

Args:
obj_in (DeviceBatchCreate): 包含多个设备属性的列表。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceBatchResult]: 包含成功/失败总数及失败详情的响应。

#### Request Body (application/json)

| 参数名    | 类型                  | 必填 | 描述     |
| :-------- | :-------------------- | :--- | :------- |
| `devices` | `Array[DeviceCreate]` | 是   | 设备列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `DeviceBatchResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量删除设备

**URL**: `/api/v1/devices/batch`

**Method**: `DELETE`

**Description**:

批量将选中的设备移入回收站。

Args:
obj_in (DeviceBatchDeleteRequest): 包含目标设备 ID 列表。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceBatchResult]: 批量删除操作的结果报告。

#### Request Body (application/json)

| 参数名 | 类型            | 必填 | 描述       |
| :----- | :-------------- | :--- | :--------- |
| `ids`  | `Array[string]` | 是   | 设备ID列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `DeviceBatchResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 恢复设备

**URL**: `/api/v1/devices/{device_id}/restore`

**Method**: `POST`

**Description**:

从回收站中恢复设备到正常状态。

Args:
device_id (UUID): 设备 ID。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DeviceResponse]: 恢复后的设备详情。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DeviceResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 设备状态流转

**URL**: `/api/v1/devices/{device_id}/status/transition`

**Method**: `POST`

**Description**:

显式执行设备状态变更。

用于记录设备在资产生命周期中的状态变化（如：入库 -> 在运行 -> 报废）。

Args:
device_id (UUID): 设备 ID。
body (DeviceStatusTransitionRequest): 包含目标状态及变更原因。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前操作人。

Returns:
ResponseBase[DeviceResponse]: 状态变更后的设备对象。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Request Body (application/json)

| 参数名      | 类型           | 必填 | 描述           |
| :---------- | :------------- | :--- | :------------- |
| `to_status` | `DeviceStatus` | 是   | 目标状态       |
| `reason`    | `string`       | 否   | 流转原因(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `DeviceResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量设备状态流转

**URL**: `/api/v1/devices/status/transition/batch`

**Method**: `POST`

**Description**:

批量变更一批设备的状态。

Args:
body (DeviceStatusBatchTransitionRequest): 包含 ID 列表、目标状态及原因。
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前操作人。

Returns:
ResponseBase[DeviceBatchResult]: 批量变更操作的结果报告。

#### Request Body (application/json)

| 参数名      | 类型            | 必填 | 描述           |
| :---------- | :-------------- | :--- | :------------- |
| `ids`       | `Array[string]` | 是   | 设备ID列表     |
| `to_status` | `DeviceStatus`  | 是   | 目标状态       |
| `reason`    | `string`        | 否   | 流转原因(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `DeviceBatchResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 设备生命周期统计

**URL**: `/api/v1/devices/lifecycle/stats`

**Method**: `GET`

**Description**:

根据部门或厂商获取设备资产各状态的数量统计。

用于仪表盘或其他资产概览界面。

Args:
device_service (DeviceService): 设备服务依赖。
current_user (User): 当前登录用户。
dept_id (UUID | None): 部门维度过滤。
vendor (DeviceVendor | None): 厂商维度过滤。

Returns:
ResponseBase[DeviceLifecycleStatsResponse]: 包含各状态计数的响应。

#### Requests Parameters (Query/Path)

| 参数名    | 位置    | 类型     | 必填 | 描述     | Default |
| :-------- | :------ | :------- | :--- | :------- | :------ |
| `dept_id` | `query` | `string` | 否   | 部门筛选 |         |
| `vendor`  | `query` | `string` | 否   | 厂商筛选 |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                           | 必填 | 描述    |
| :-------- | :----------------------------- | :--- | :------ |
| `code`    | `integer`                      | 否   | Code    |
| `message` | `string`                       | 否   | Message |
| `data`    | `DeviceLifecycleStatsResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Diff

### 获取设备最新配置差异

**URL**: `/api/v1/diff/device/{device_id}/latest`

**Method**: `GET`

**Description**:

计算并获取指定设备最新两个备份版本之间的配置差异。

该接口会自动寻找最新的成功备份及其前一个版本进行 Diff 计算。

Args:
device_id (UUID): 设备 ID。
diff_service (DiffService): 差异计算服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[DiffResponse]: 包含 Unified Diff 格式文本及版本 MD5 的响应。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `DiffResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Discovery

### 触发网络扫描

**URL**: `/api/v1/discovery/discovery/scan`

**Method**: `POST`

**Description**:

触发针对特定网段的网络扫描任务。

通过 Nmap 或 Masscan 发现网络中的在线资产，并识别其开放端口及服务横幅。

Args:
request (ScanRequest): 包含网段、扫描类型、端口、扫描模式（同步/异步）的请求。
current_user (CurrentUser): 当前操作人。

Returns:
dict[str, Any]: 如果是异步模式，返回包含 task_id 的字典；同步模式返回扫描结果。

#### Request Body (application/json)

| 参数名       | 类型            | 必填 | 描述                       |
| :----------- | :-------------- | :--- | :------------------------- |
| `subnets`    | `Array[string]` | 是   | 待扫描网段列表 (CIDR 格式) |
| `scan_type`  | `string`        | 否   | 扫描类型 (nmap/masscan)    |
| `ports`      | `string`        | 否   | 扫描端口 (如 22,23,80,443) |
| `async_mode` | `boolean`       | 否   | 是否异步执行               |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询扫描任务状态

**URL**: `/api/v1/discovery/discovery/scan/task/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 扫描任务的当前进度和最终发现的资产。

Args:
task_id (str): Celery 任务 ID。

Returns:
ScanTaskStatus: 包含状态 (PENDING/SUCCESS) 及匹配记录或错误的详情。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名     | 类型         | 必填 | 描述       |
| :--------- | :----------- | :--- | :--------- |
| `task_id`  | `string`     | 是   | 任务ID     |
| `status`   | `string`     | 是   | 任务状态   |
| `progress` | `integer`    | 否   | 进度百分比 |
| `result`   | `ScanResult` | 否   | 扫描结果   |
| `error`    | `string`     | 否   | 错误信息   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取发现记录列表

**URL**: `/api/v1/discovery/discovery/`

**Method**: `GET`

**Description**:

获取通过网络扫描发现的所有设备记录。

Args:
db (Session): 数据库会话。
page (int): 当前页码。
page_size (int): 每页限制。
status (DiscoveryStatus | None): 状态过滤（如：NEW, IGNORED, MATCHED）。
keyword (str | None): 匹配 IP、MAC、主机名的搜索关键词。
scan_source (str | None): 识别扫描的具体来源标识。

Returns:
PaginatedResponse[DiscoveryResponse]: 包含发现资产详情的分页响应。

#### Requests Parameters (Query/Path)

| 参数名        | 位置    | 类型      | 必填 | 描述       | Default |
| :------------ | :------ | :-------- | :--- | :--------- | :------ |
| `page`        | `query` | `integer` | 否   | 页码       | 1       |
| `page_size`   | `query` | `integer` | 否   | 每页数量   | 20      |
| `status`      | `query` | `string`  | 否   | 状态筛选   |         |
| `keyword`     | `query` | `string`  | 否   | 关键词搜索 |         |
| `scan_source` | `query` | `string`  | 否   | 扫描来源   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名      | 类型                       | 必填 | 描述     |
| :---------- | :------------------------- | :--- | :------- |
| `total`     | `integer`                  | 是   | 总记录数 |
| `page`      | `integer`                  | 是   | 当前页码 |
| `page_size` | `integer`                  | 是   | 每页大小 |
| `items`     | `Array[DiscoveryResponse]` | 否   | 数据列表 |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取发现记录详情

**URL**: `/api/v1/discovery/discovery/{discovery_id}`

**Method**: `GET`

**Description**:

获取单个扫描发现记录的完整属性。

Args:
db (Session): 数据库会话。
discovery_id (UUID): 扫描结果主键 ID。

Returns:
DiscoveryResponse: 发现资产及 CMDB 匹配关联信息。

#### Requests Parameters (Query/Path)

| 参数名         | 位置   | 类型     | 必填 | 描述         | Default |
| :------------- | :----- | :------- | :--- | :----------- | :------ |
| `discovery_id` | `path` | `string` | 是   | Discovery Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名                | 类型      | 必填 | 描述              |
| :-------------------- | :-------- | :--- | :---------------- |
| `ip_address`          | `string`  | 是   | IP 地址           |
| `mac_address`         | `string`  | 否   | MAC 地址          |
| `vendor`              | `string`  | 否   | 厂商              |
| `device_type`         | `string`  | 否   | 设备类型          |
| `hostname`            | `string`  | 否   | 主机名            |
| `os_info`             | `string`  | 否   | 操作系统信息      |
| `id`                  | `string`  | 是   | Id                |
| `open_ports`          | `object`  | 否   | Open Ports        |
| `ssh_banner`          | `string`  | 否   | Ssh Banner        |
| `first_seen_at`       | `string`  | 是   | First Seen At     |
| `last_seen_at`        | `string`  | 是   | Last Seen At      |
| `offline_days`        | `integer` | 是   | Offline Days      |
| `status`              | `string`  | 是   | Status            |
| `matched_device_id`   | `string`  | 否   | Matched Device Id |
| `scan_source`         | `string`  | 否   | Scan Source       |
| `created_at`          | `string`  | 是   | Created At        |
| `updated_at`          | `string`  | 是   | Updated At        |
| `matched_device_name` | `string`  | 否   | 匹配设备名称      |
| `matched_device_ip`   | `string`  | 否   | 匹配设备IP        |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除发现记录

**URL**: `/api/v1/discovery/discovery/{discovery_id}`

**Method**: `DELETE`

**Description**:

物理删除或隐藏特定的扫描发现结果。

Args:
db (Session): 数据库会话。
discovery_id (UUID): 扫描记录 ID。
current_user (CurrentUser): 当前执行操作的用户。

Returns:
dict[str, str]: 确认删除的消息。

#### Requests Parameters (Query/Path)

| 参数名         | 位置   | 类型     | 必填 | 描述         | Default |
| :------------- | :----- | :------- | :--- | :----------- | :------ |
| `discovery_id` | `path` | `string` | 是   | Discovery Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 纳管设备

**URL**: `/api/v1/discovery/discovery/{discovery_id}/adopt`

**Method**: `POST`

**Description**:

将扫描结果中的在线资产直接录入为系统正式管理的设备。

录入过程会预填发现的 IP、MAC、厂商等信息，并根据请求配置所属部门和凭据。

Args:
db (Session): 数据库会话。
discovery_id (UUID): 发现记录关联 ID。
request (AdoptDeviceRequest): 纳管配置，包含名称、分组、凭据等。
scan_service (ScanService): 扫描资产服务。
current_user (CurrentUser): 当前操作人。

Returns:
dict[str, Any]: 包含新设备 ID 的确认响应。

#### Requests Parameters (Query/Path)

| 参数名         | 位置   | 类型     | 必填 | 描述         | Default |
| :------------- | :----- | :------- | :--- | :----------- | :------ |
| `discovery_id` | `path` | `string` | 是   | Discovery Id |         |

#### Request Body (application/json)

| 参数名         | 类型     | 必填 | 描述       |
| :------------- | :------- | :--- | :--------- |
| `name`         | `string` | 是   | 设备名称   |
| `vendor`       | `string` | 否   | 设备厂商   |
| `device_group` | `string` | 否   | 设备分组   |
| `dept_id`      | `string` | 否   | 所属部门ID |
| `username`     | `string` | 否   | SSH 用户名 |
| `password`     | `string` | 否   | SSH 密码   |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取影子资产列表

**URL**: `/api/v1/discovery/discovery/shadow`

**Method**: `GET`

**Description**:

获取所有已在线但尚未关联正式 CMDB 的网路资产。

Args:
db (Session): 数据库会话。
scan_service (ScanService): 扫描资产服务依赖。
page (int): 当前页码。
page_size (int): 每页限制。

Returns:
PaginatedResponse[DiscoveryResponse]: 影子资产（未知资产）列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名      | 类型                       | 必填 | 描述     |
| :---------- | :------------------------- | :--- | :------- |
| `total`     | `integer`                  | 是   | 总记录数 |
| `page`      | `integer`                  | 是   | 当前页码 |
| `page_size` | `integer`                  | 是   | 每页大小 |
| `items`     | `Array[DiscoveryResponse]` | 否   | 数据列表 |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取离线设备列表

**URL**: `/api/v1/discovery/discovery/offline`

**Method**: `GET`

**Description**:

获取由于长时间未能在扫描中发现而标记为离线的设备列表。

系统会将 CMDB 中的设备与最新的扫描记录比对，若超过阈值天数未出现，则视为离线。

Args:
db (Session): 数据库会话。
scan_service (ScanService): 扫描资产服务。
days_threshold (int): 判定离线的天数阈值（默认为 7 天）。

Returns:
list[OfflineDevice]: 包含设备 ID、名称及其最后一次被扫描到的时间。

#### Requests Parameters (Query/Path)

| 参数名           | 位置    | 类型      | 必填 | 描述         | Default |
| :--------------- | :------ | :-------- | :--- | :----------- | :------ |
| `days_threshold` | `query` | `integer` | 否   | 离线天数阈值 | 7       |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 执行 CMDB 比对

**URL**: `/api/v1/discovery/discovery/compare`

**Method**: `POST`

**Description**:

全量对比当前的扫描发现库与正式 CMDB 设备库。

用于同步状态、识别影子资产和更新离线天数统计。建议在完成全网大规模扫描后执行。

Args:
current_user (CurrentUser): 当前操作人。
async_mode (bool): 是否进入 Celery 异步处理模式。

Returns:
dict[str, Any]: 包含任务状态或同步结果的字典。

#### Requests Parameters (Query/Path)

| 参数名       | 位置    | 类型      | 必填 | 描述         | Default |
| :----------- | :------ | :-------- | :--- | :----------- | :------ |
| `async_mode` | `query` | `boolean` | 否   | 是否异步执行 | True    |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Inventory_audit

### 创建盘点任务（异步执行）

**URL**: `/api/v1/inventory_audit/`

**Method**: `POST`

**Description**:

提交一个资产盘点任务。

接口会立即创建记录并触发 Celery 异步扫描，识别在线、离线、影子资产以及配置不一致设备。

Args:
body (InventoryAuditCreate): 盘点配置，包括名称和审计范围（网段或部门）。
service (InventoryAuditService): 资产盘点服务。
current_user (User): 任务创建人。

Returns:
ResponseBase[InventoryAuditResponse]: 包含创建记录及其绑定的 Celery 任务 ID。

#### Request Body (application/json)

| 参数名  | 类型                  | 必填 | 描述         |
| :------ | :-------------------- | :--- | :----------- |
| `name`  | `string`              | 是   | 盘点任务名称 |
| `scope` | `InventoryAuditScope` | 是   | 盘点范围     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                     | 必填 | 描述    |
| :-------- | :----------------------- | :--- | :------ |
| `code`    | `integer`                | 否   | Code    |
| `message` | `string`                 | 否   | Message |
| `data`    | `InventoryAuditResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 盘点任务列表

**URL**: `/api/v1/inventory_audit/`

**Method**: `GET`

**Description**:

获取所有历史和正在进行的资产盘点任务记录。

Args:
service (InventoryAuditService): 资产盘点服务。
current_user (User): 当前登录用户。
page (int): 页码。
page_size (int): 每页限制。
status (str | None): 任务状态过滤。

Returns:
ResponseBase[PaginatedResponse[InventoryAuditResponse]]: 分页盘点记录。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `status`    | `query` | `string`  | 否   | 状态筛选  |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                        | 必填 | 描述    |
| :-------- | :------------------------------------------ | :--- | :------ |
| `code`    | `integer`                                   | 否   | Code    |
| `message` | `string`                                    | 否   | Message |
| `data`    | `PaginatedResponse_InventoryAuditResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 盘点任务详情

**URL**: `/api/v1/inventory_audit/{audit_id}`

**Method**: `GET`

**Description**:

获取指定盘点任务的执行结果摘要。

Args:
audit_id (UUID): 盘点任务 UUID。
service (InventoryAuditService): 资产盘点服务。
current_user (User): 当前登录用户。

Returns:
ResponseBase[InventoryAuditResponse]: 包含审计统计及分析报告的数据详情。

#### Requests Parameters (Query/Path)

| 参数名     | 位置   | 类型     | 必填 | 描述     | Default |
| :--------- | :----- | :------- | :--- | :------- | :------ |
| `audit_id` | `path` | `string` | 是   | Audit Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                     | 必填 | 描述    |
| :-------- | :----------------------- | :--- | :------ |
| `code`    | `integer`                | 否   | Code    |
| `message` | `string`                 | 否   | Message |
| `data`    | `InventoryAuditResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 导出盘点报告(JSON)

**URL**: `/api/v1/inventory_audit/{audit_id}/export`

**Method**: `GET`

**Description**:

以 JSON 结构获取盘点审计的完整详单。

Args:
audit_id (UUID): 任务 ID。
service (InventoryAuditService): 资产盘点服务。
current_user (User): 授权用户。

Returns:
ResponseBase[dict]: 包含范围、匹配明细、差异资产列表的原始数据。

#### Requests Parameters (Query/Path)

| 参数名     | 位置   | 类型     | 必填 | 描述     | Default |
| :--------- | :----- | :------- | :--- | :------- | :------ |
| `audit_id` | `path` | `string` | 是   | Audit Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `object`  | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Logs

### 获取登录日志

**URL**: `/api/v1/logs/login`

**Method**: `GET`

**Description**:

获取登录日志 (分页)。

查询系统登录日志记录，支持分页。按创建时间倒序排列。

Args:
current_user (User): 当前登录用户。
log_service (LogService): 日志服务依赖。
page (int, optional): 页码. Defaults to 1.
page_size (int, optional): 每页数量. Defaults to 20.
keyword (str | None, optional): 关键词过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[LoginLogResponse]]: 分页后的登录日志列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                  | 必填 | 描述    |
| :-------- | :------------------------------------ | :--- | :------ |
| `code`    | `integer`                             | 否   | Code    |
| `message` | `string`                              | 否   | Message |
| `data`    | `PaginatedResponse_LoginLogResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取操作日志

**URL**: `/api/v1/logs/operation`

**Method**: `GET`

**Description**:

获取操作日志 (分页)。

查询系统操作日志（API 调用记录），支持分页。按创建时间倒序排列。

Args:
current_user (User): 当前登录用户。
log_service (LogService): 日志服务依赖。
page (int, optional): 页码. Defaults to 1.
page_size (int, optional): 每页数量. Defaults to 20.
keyword (str | None, optional): 关键词过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[OperationLogResponse]]: 分页后的操作日志列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                      | 必填 | 描述    |
| :-------- | :---------------------------------------- | :--- | :------ |
| `code`    | `integer`                                 | 否   | Code    |
| `message` | `string`                                  | 否   | Message |
| `data`    | `PaginatedResponse_OperationLogResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Menus

### 获取可分配菜单选项

**URL**: `/api/v1/menus/options`

**Method**: `GET`

**Description**:

获取可分配菜单选项（树结构）。

用于角色创建/编辑时选择可分配菜单（包含隐藏权限点）。

Args:
current\*user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。

- (User): 权限依赖（需要 menu:options:list）。

Returns:
ResponseBase[list[MenuResponse]]: 菜单选项树。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足时。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

---

### 获取我的菜单

**URL**: `/api/v1/menus/me`

**Method**: `GET`

**Description**:

获取当前登录用户可见的导航菜单树。

不包含隐藏权限点（is_hidden=true 的菜单节点不会返回），但隐藏权限点会影响父级菜单的可见性判定。

Args:
current_user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[list[MenuResponse]]: 当前用户可见的导航菜单树。

Raises:
UnauthorizedException: 未登录或令牌无效时。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

---

### 获取菜单列表

**URL**: `/api/v1/menus/`

**Method**: `GET`

**Description**:

获取菜单列表 (分页)。

查询系统菜单记录，支持分页。按排序字段排序。

Args:
current_user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。
page (int, optional): 页码. Defaults to 1.
page_size (int, optional): 每页数量. Defaults to 20.
keyword (str | None, optional): 关键词过滤. Defaults to None.
is_active (bool | None, optional): 是否启用过滤. Defaults to None.
is_hidden (bool | None, optional): 是否隐藏过滤. Defaults to None.
type (MenuType | None, optional): 菜单类型过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[MenuResponse]]: 分页后的菜单列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |
| `is_active` | `query` | `string`  | 否   | Is Active |         |
| `is_hidden` | `query` | `string`  | 否   | Is Hidden |         |
| `type`      | `query` | `string`  | 否   | Type      |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_MenuResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建菜单

**URL**: `/api/v1/menus/`

**Method**: `POST`

**Description**:

创建新菜单。

创建新的系统菜单或权限节点。

Args:
menu_in (MenuCreate): 菜单创建数据 (标题, 路径, 类型等)。
current_user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[MenuResponse]: 创建成功的菜单对象。

#### Request Body (application/json)

| 参数名       | 类型       | 必填 | 描述                         |
| :----------- | :--------- | :--- | :--------------------------- |
| `type`       | `MenuType` | 否   | 菜单类型（目录/菜单/权限点） |
| `parent_id`  | `string`   | 否   | 父菜单ID                     |
| `path`       | `string`   | 否   | 路由路径                     |
| `component`  | `string`   | 否   | 组件路径                     |
| `icon`       | `string`   | 否   | 图标                         |
| `sort`       | `integer`  | 否   | 排序                         |
| `is_hidden`  | `boolean`  | 否   | 是否隐藏                     |
| `permission` | `string`   | 否   | 权限标识                     |
| `title`      | `string`   | 是   | 菜单标题                     |
| `name`       | `string`   | 是   | 组件名称                     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `MenuResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量删除菜单

**URL**: `/api/v1/menus/batch`

**Method**: `DELETE`

**Description**:

批量删除菜单。

支持软删除和硬删除。如果存在子菜单，将级联删除或校验（取决于具体实现策略）。

Args:
request (BatchDeleteRequest): 批量删除请求体 (包含 ID 列表和硬删除标志)。
current_user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量操作结果（成功数量等）。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                    |
| :------------ | :-------------- | :--- | :---------------------- |
| `ids`         | `Array[string]` | 是   | 要删除的 ID 列表        |
| `hard_delete` | `boolean`       | 否   | 是否硬删除 (默认软删除) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新菜单

**URL**: `/api/v1/menus/{id}`

**Method**: `PUT`

**Description**:

更新菜单。

更新指定 ID 的菜单信息。

Args:
id (UUID): 菜单 ID。
menu_in (MenuUpdate): 菜单更新数据。
current_user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[MenuResponse]: 更新后的菜单对象。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Request Body (application/json)

| 参数名       | 类型       | 必填 | 描述       |
| :----------- | :--------- | :--- | :--------- |
| `title`      | `string`   | 否   | Title      |
| `name`       | `string`   | 否   | Name       |
| `type`       | `MenuType` | 否   |            |
| `parent_id`  | `string`   | 否   | Parent Id  |
| `path`       | `string`   | 否   | Path       |
| `component`  | `string`   | 否   | Component  |
| `icon`       | `string`   | 否   | Icon       |
| `sort`       | `integer`  | 否   | Sort       |
| `is_hidden`  | `boolean`  | 否   | Is Hidden  |
| `is_active`  | `boolean`  | 否   | Is Active  |
| `permission` | `string`   | 否   | Permission |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `MenuResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除菜单

**URL**: `/api/v1/menus/{id}`

**Method**: `DELETE`

**Description**:

删除菜单。

删除指定 ID 的菜单。

Args:
id (UUID): 菜单 ID。
current_user (User): 当前登录用户。
menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[MenuResponse]: 已删除的菜单对象信息。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `MenuResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取菜单回收站列表

**URL**: `/api/v1/menus/recycle-bin`

**Method**: `GET`

**Description**:

获取已删除的菜单列表 (回收站)。
仅限超级管理员。

Args:
page (int, optional): 页码. Defaults to 1.
page\*size (int, optional): 每页数量. Defaults to 20.
active_superuser (User): 超级管理员权限验证。

- (User): 权限依赖（需要 menu:recycle）。
  menu_service (MenuService): 菜单服务依赖。
  keyword (str | None, optional): 关键词过滤. Defaults to None.
  is_active (bool | None, optional): 是否启用过滤. Defaults to None.
  is_hidden (bool | None, optional): 是否隐藏过滤. Defaults to None.
  type (MenuType | None, optional): 菜单类型过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[MenuResponse]]: 分页后的回收站菜单列表。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足或非超级管理员时。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |
| `is_active` | `query` | `string`  | 否   | Is Active |         |
| `is_hidden` | `query` | `string`  | 否   | Is Hidden |         |
| `type`      | `query` | `string`  | 否   | Type      |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_MenuResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量恢复菜单

**URL**: `/api/v1/menus/batch/restore`

**Method**: `POST`

**Description**:

批量恢复菜单。

从回收站中批量恢复软删除菜单。
需要超级管理员权限。

Args:
request (BatchRestoreRequest): 批量恢复请求体 (包含 ID 列表)。
active\*superuser (User): 超级管理员权限验证。

- (User): 权限依赖（需要 menu:restore）。
  menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量恢复结果。

#### Request Body (application/json)

| 参数名 | 类型            | 必填 | 描述             |
| :----- | :-------------- | :--- | :--------------- |
| `ids`  | `Array[string]` | 是   | 要恢复的 ID 列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 恢复已删除菜单

**URL**: `/api/v1/menus/{id}/restore`

**Method**: `POST`

**Description**:

恢复已删除菜单。

从回收站中恢复指定菜单。
需要超级管理员权限。

Args:
id (UUID): 菜单 ID。
active\*superuser (User): 超级管理员权限验证。

- (User): 权限依赖（需要 menu:restore）。
  menu_service (MenuService): 菜单服务依赖。

Returns:
ResponseBase[MenuResponse]: 恢复后的菜单对象。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足或非超级管理员时。
NotFoundException: 菜单不存在时。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `MenuResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Permissions

### 获取权限字典

**URL**: `/api/v1/permissions/`

**Method**: `GET`

**Description**:

获取系统权限字典（权限码以代码为源）。

前端用于菜单/角色管理时的“权限码选择”，避免手动输入权限字符串。

Args:
current\*user (User): 当前登录用户。
permission_service (PermissionService): 权限字典服务依赖。

- (User): 权限依赖（需要 menu:options:list）。

Returns:
ResponseBase[list[PermissionDictItem]]: 权限字典列表。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足时。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

---

## Render

### 模板渲染预览(Dry-Run)

**URL**: `/api/v1/render/render/template/{template_id}`

**Method**: `POST`

**Description**:

在下发前预览 Jinja2 模板渲染后的配置文本。

支持传入空参数或模拟设备上下文（从设备表中提取属性）进行 Dry-Run。

Args:
template_id (UUID): 配置模板 ID。
body (RenderRequest): 包含输入参数及可选设备上下文 ID 的请求。
template_service (TemplateService): 模板管理服务。
db (Session): 数据库会话。
device_crud (CRUDDevice): 设备 CRUD 抽象。
render_service (RenderService): 渲染逻辑核心服务。

Returns:
ResponseBase[RenderResponse]: 包含最终渲染出的配置字符串。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名      | 类型     | 必填 | 描述                     |
| :---------- | :------- | :--- | :----------------------- |
| `params`    | `object` | 否   | 模板参数                 |
| `device_id` | `string` | 否   | 用于上下文的设备ID(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `RenderResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Roles

### 获取角色列表

**URL**: `/api/v1/roles/`

**Method**: `GET`

**Description**:

获取角色列表 (分页)。

查询系统角色记录，支持分页。

Args:
role_service (RoleService): 角色服务依赖。
current_user (User): 当前登录用户。
page (int, optional): 页码. Defaults to 1.
page_size (int, optional): 每页数量. Defaults to 20.
keyword (str | None, optional): 关键词过滤. Defaults to None.
is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[RoleResponse]]: 分页后的角色列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |
| `is_active` | `query` | `string`  | 否   | Is Active |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_RoleResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建角色

**URL**: `/api/v1/roles/`

**Method**: `POST`

**Description**:

创建新角色。

创建新的系统角色。

Args:
role_in (RoleCreate): 角色创建数据 (名称, 标识, 描述等)。
current_user (User): 当前登录用户。
role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[RoleResponse]: 创建成功的角色对象。

#### Request Body (application/json)

| 参数名        | 类型      | 必填 | 描述     |
| :------------ | :-------- | :--- | :------- |
| `description` | `string`  | 否   | 描述     |
| `sort`        | `integer` | 否   | 排序     |
| `name`        | `string`  | 是   | 角色名称 |
| `code`        | `string`  | 是   | 角色编码 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `RoleResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量删除角色

**URL**: `/api/v1/roles/batch`

**Method**: `DELETE`

**Description**:

批量删除角色。

支持软删除和硬删除。

Args:
request (BatchDeleteRequest): 批量删除请求体 (包含 ID 列表和硬删除标志)。
current_user (User): 当前登录用户。
role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量操作结果（成功数量等）。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                    |
| :------------ | :-------------- | :--- | :---------------------- |
| `ids`         | `Array[string]` | 是   | 要删除的 ID 列表        |
| `hard_delete` | `boolean`       | 否   | 是否硬删除 (默认软删除) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新角色

**URL**: `/api/v1/roles/{id}`

**Method**: `PUT`

**Description**:

更新角色。

更新指定 ID 的角色信息。

Args:
id (UUID): 角色 ID。
role_in (RoleUpdate): 角色更新数据。
current_user (User): 当前登录用户。
role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[RoleResponse]: 更新后的角色对象。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Request Body (application/json)

| 参数名        | 类型      | 必填 | 描述     |
| :------------ | :-------- | :--- | :------- |
| `name`        | `string`  | 否   | 角色名称 |
| `code`        | `string`  | 否   | 角色编码 |
| `description` | `string`  | 否   | 描述     |
| `sort`        | `integer` | 否   | 排序     |
| `is_active`   | `boolean` | 否   | 是否激活 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `RoleResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除角色

**URL**: `/api/v1/roles/{id}`

**Method**: `DELETE`

**Description**:

删除角色 (软删除)。

Args:
id (UUID): 角色 ID。
active_superuser (User): 当前登录超级用户。
role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[RoleResponse]: 删除后的角色对象。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `RoleResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取角色回收站列表

**URL**: `/api/v1/roles/recycle-bin`

**Method**: `GET`

**Description**:

获取已删除的角色列表 (回收站)。
仅限超级管理员。

Args:
page (int, optional): 页码. Defaults to 1.
page\*size (int, optional): 每页数量. Defaults to 20.
active_superuser (User): 超级管理员权限验证。

- (User): 权限依赖（需要 role:recycle）。
  role_service (RoleService): 角色服务依赖。
  keyword (str | None, optional): 关键词过滤. Defaults to None.
  is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[RoleResponse]]: 分页后的回收站角色列表。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足或非超级管理员时。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |
| `is_active` | `query` | `string`  | 否   | Is Active |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_RoleResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量恢复角色

**URL**: `/api/v1/roles/batch/restore`

**Method**: `POST`

**Description**:

批量恢复角色。

从回收站中批量恢复软删除角色。
需要超级管理员权限。

Args:
request (BatchRestoreRequest): 批量恢复请求体 (包含 ID 列表)。
active\*superuser (User): 超级管理员权限验证。

- (User): 权限依赖（需要 role:restore）。
  role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量恢复结果。

#### Request Body (application/json)

| 参数名 | 类型            | 必填 | 描述             |
| :----- | :-------------- | :--- | :--------------- |
| `ids`  | `Array[string]` | 是   | 要恢复的 ID 列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 恢复已删除角色

**URL**: `/api/v1/roles/{id}/restore`

**Method**: `POST`

**Description**:

恢复已删除角色。

从回收站中恢复指定角色。
需要超级管理员权限。

Args:
id (UUID): 角色 ID。
active\*superuser (User): 超级管理员权限验证。

- (User): 权限依赖（需要 role:restore）。
  role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[RoleResponse]: 恢复后的角色对象。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足或非超级管理员时。
NotFoundException: 角色不存在时。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `RoleResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取角色菜单

**URL**: `/api/v1/roles/{id}/menus`

**Method**: `GET`

**Description**:

获取指定角色当前已绑定的所有菜单和权限点 ID。

用于角色编辑界面回显已勾选的权限树。

Args:
id (UUID): 角色 ID。
current_user (User): 当前登录用户。
role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[list[UUID]]: 菜单 ID 列表。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 设置角色菜单

**URL**: `/api/v1/roles/{id}/menus`

**Method**: `PUT`

**Description**:

全量更新角色的菜单和权限绑定关系。

Args:
id (UUID): 角色 ID。
req (RoleMenusUpdateRequest): 包含新的菜单 ID 集合。
current_user (User): 当前登录用户。
role_service (RoleService): 角色服务依赖。

Returns:
ResponseBase[list[UUID]]: 更新后的菜单 ID 列表。

#### Requests Parameters (Query/Path)

| 参数名 | 位置   | 类型     | 必填 | 描述 | Default |
| :----- | :----- | :------- | :--- | :--- | :------ |
| `id`   | `path` | `string` | 是   | Id   |         |

#### Request Body (application/json)

| 参数名     | 类型            | 必填 | 描述           |
| :--------- | :-------------- | :--- | :------------- |
| `menu_ids` | `Array[string]` | 否   | 关联菜单ID列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Sessions

### 获取在线会话列表

**URL**: `/api/v1/sessions/online`

**Method**: `GET`

**Description**:

获取在线会话列表，支持分页和搜索。
需要 SESSION_LIST 权限。

Args:
session_service (SessionService): 在线会话服务依赖。
current_user (User): 当前登录用户。
page (int): 页码，默认值为 1。
page_size (int): 每页数量，默认值为 20。
keyword (str | None): 关键词过滤，支持用户名和 IP 搜索。

Returns:
ResponseBase[PaginatedResponse[OnlineSessionResponse]]: 包含在线会话列表的响应对象。

Raises:
CustomException: 当用户没有权限时抛出 403 错误。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |
| `keyword`   | `query` | `string`  | 否   | Keyword   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                       | 必填 | 描述    |
| :-------- | :----------------------------------------- | :--- | :------ |
| `code`    | `integer`                                  | 否   | Code    |
| `message` | `string`                                   | 否   | Message |
| `data`    | `PaginatedResponse_OnlineSessionResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量强制下线

**URL**: `/api/v1/sessions/kick/batch`

**Method**: `POST`

**Description**:

批量强制下线指定用户列表。
需要 SESSION_KICK 权限。

Args:
request (KickUsersRequest): 包含要强制下线的用户ID列表的请求体。
session_service (SessionService): 在线会话服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[BatchOperationResult]: 包含操作结果的响应对象，包括成功数量和失败ID列表。

Raises:
CustomException: 当用户没有权限时抛出 403 错误。

#### Request Body (application/json)

| 参数名     | 类型            | 必填 | 描述                   |
| :--------- | :-------------- | :--- | :--------------------- |
| `user_ids` | `Array[string]` | 是   | 要强制下线的用户ID列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 强制下线(踢人)

**URL**: `/api/v1/sessions/kick/{user_id}`

**Method**: `POST`

**Description**:

强制下线指定用户。
需要 SESSION_KICK 权限。

Args:
user_id (UUID): 要强制下线的用户ID。
session_service (SessionService): 在线会话服务依赖。
current_user (User): 当前登录用户。

Returns:
ResponseBase[None]: 空响应对象，表示操作成功。

Raises:
CustomException: 当用户没有权限或用户不存在时抛出相应错误。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `null`    | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Tasks

### Get Task Status

**URL**: `/api/v1/tasks/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 任务的执行状态和结果。

仅限超级管理员访问。能够返回 PENDING, STARTED, SUCCESS, FAILURE 等状态，并在任务完成时返回结果或错误。

Args:
task\*id (str): Celery 任务的唯一 ID。

- (User): 超级管理员权限验证。

Returns:
TaskResponse: 包含任务 ID、状态、以及（如有）执行结果或错误的对象。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型     | 必填 | 描述    |
| :-------- | :------- | :--- | :------ |
| `task_id` | `string` | 是   | Task Id |
| `status`  | `string` | 是   | Status  |
| `result`  | `Any`    | 否   | Result  |
| `error`   | `string` | 否   | Error   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### Revoke Task

**URL**: `/api/v1/tasks/{task_id}`

**Method**: `DELETE`

**Description**:

撤销或强制终止正在执行的任务。

仅限超级管理员访问。

Args:
task\*id (str): 要撤销的任务 ID。

- (User): 超级管理员权限验证。

Returns:
dict: 操作确认信息。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### Trigger Ping

**URL**: `/api/v1/tasks/test/ping`

**Method**: `POST`

**Description**:

触发 Ping 测试异步任务。

用于回归测试或验证 Celery 分片和 Worker 是否正常运行。
仅限超级管理员访问。

Args:
\_ (User): 超级管理员权限验证。

Returns:
TaskResponse: 返回生成的任务 ID，状态为 PENDING。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型     | 必填 | 描述    |
| :-------- | :------- | :--- | :------ |
| `task_id` | `string` | 是   | Task Id |
| `status`  | `string` | 是   | Status  |
| `result`  | `Any`    | 否   | Result  |
| `error`   | `string` | 否   | Error   |

---

### Trigger Add

**URL**: `/api/v1/tasks/test/add`

**Method**: `POST`

**Description**:

触发一个简单的加法异步测试任务。

仅限超级管理员访问。

Args:
\_ (User): 超级管理员权限验证。
x (int): 第一个操作数。
y (int): 第二个操作数。

Returns:
TaskResponse: 生成的任务 ID。

#### Requests Parameters (Query/Path)

| 参数名 | 位置    | 类型      | 必填 | 描述 | Default |
| :----- | :------ | :-------- | :--- | :--- | :------ |
| `x`    | `query` | `integer` | 否   | X    | 1       |
| `y`    | `query` | `integer` | 否   | Y    | 2       |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型     | 必填 | 描述    |
| :-------- | :------- | :--- | :------ |
| `task_id` | `string` | 是   | Task Id |
| `status`  | `string` | 是   | Status  |
| `result`  | `Any`    | 否   | Result  |
| `error`   | `string` | 否   | Error   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### Trigger Long Running

**URL**: `/api/v1/tasks/test/long-running`

**Method**: `POST`

**Description**:

触发一个耗时模拟任务，用于测试进度反馈和超时处理。

仅限超级管理员访问。设置较长的 duration 可以测试撤销任务接口。

Args:
\_ (User): 超级管理员权限验证。
duration (int): 模拟运行时长（秒），默认 10s，由于是测试任务，限额 300s。

Returns:
TaskResponse: 生成的任务 ID。

Raises:
HTTPException: 当 duration 超过 300s 时。

#### Requests Parameters (Query/Path)

| 参数名     | 位置    | 类型      | 必填 | 描述     | Default |
| :--------- | :------ | :-------- | :--- | :------- | :------ |
| `duration` | `query` | `integer` | 否   | Duration | 10      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型     | 必填 | 描述    |
| :-------- | :------- | :--- | :------ |
| `task_id` | `string` | 是   | Task Id |
| `status`  | `string` | 是   | Status  |
| `result`  | `Any`    | 否   | Result  |
| `error`   | `string` | 否   | Error   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### Get Worker Stats

**URL**: `/api/v1/tasks/workers/stats`

**Method**: `GET`

**Description**:

实时获取当前已注册的所有 Celery Worker 节点的统计状态。

仅限超级管理员访问。返回包括并发设置、已完成任务数、运行中的任务等。

Args:
\_ (User): 超级管理员权限验证。

Returns:
dict: 包含 workers 列表、stats 统计和活动任务详情。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

---

## Templates

### 获取模板列表

**URL**: `/api/v1/templates/templates/`

**Method**: `GET`

**Description**:

分页获取配置模板列表。

Args:
service (TemplateService): 模板服务依赖。
page (int): 当前页码。
page_size (int): 每页大小（1-100）。
vendor (DeviceVendor | None): 按厂商过滤。
template_type (TemplateType | None): 按模板类型过滤。
status (TemplateStatus | None): 按状态过滤。

Returns:
ResponseBase[PaginatedResponse[TemplateResponse]]: 包含模板列表的分页响应。

#### Requests Parameters (Query/Path)

| 参数名          | 位置    | 类型      | 必填 | 描述          | Default |
| :-------------- | :------ | :-------- | :--- | :------------ | :------ |
| `page`          | `query` | `integer` | 否   | Page          | 1       |
| `page_size`     | `query` | `integer` | 否   | Page Size     | 20      |
| `vendor`        | `query` | `string`  | 否   | Vendor        |         |
| `template_type` | `query` | `string`  | 否   | Template Type |         |
| `status`        | `query` | `string`  | 否   | Status        |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                  | 必填 | 描述    |
| :-------- | :------------------------------------ | :--- | :------ |
| `code`    | `integer`                             | 否   | Code    |
| `message` | `string`                              | 否   | Message |
| `data`    | `PaginatedResponse_TemplateResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建模板(草稿)

**URL**: `/api/v1/templates/templates/`

**Method**: `POST`

**Description**:

创建一个新的配置模板草稿。

Args:
data (TemplateCreate): 创建表单数据。
service (TemplateService): 模板服务依赖。
user (User): 创建者信息。

Returns:
ResponseBase[TemplateResponse]: 创建成功的模板信息。

#### Request Body (application/json)

| 参数名          | 类型                  | 必填 | 描述                         |
| :-------------- | :-------------------- | :--- | :--------------------------- |
| `name`          | `string`              | 是   | 模板名称                     |
| `description`   | `string`              | 否   | 模板描述                     |
| `template_type` | `TemplateType`        | 否   | 模板类型                     |
| `content`       | `string`              | 是   | Jinja2 模板内容              |
| `vendors`       | `Array[DeviceVendor]` | 是   | 适用厂商列表                 |
| `device_type`   | `DeviceType`          | 否   | 适用设备类型                 |
| `parameters`    | `string`              | 否   | 参数定义(JSON Schema 字符串) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取模板详情

**URL**: `/api/v1/templates/templates/{template_id}`

**Method**: `GET`

**Description**:

根据 ID 获取模板的详细定义信息。

Args:
template_id (UUID): 模板 ID。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 模板详情。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新模板

**URL**: `/api/v1/templates/templates/{template_id}`

**Method**: `PUT`

**Description**:

更新处于草稿或拒绝状态的模板。

Args:
template_id (UUID): 模板 ID。
data (TemplateUpdate): 要更新的字段。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 更新后的模板信息。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名          | 类型             | 必填 | 描述                         |
| :-------------- | :--------------- | :--- | :--------------------------- |
| `name`          | `string`         | 否   | 模板名称                     |
| `description`   | `string`         | 否   | 模板描述                     |
| `template_type` | `TemplateType`   | 否   | 模板类型                     |
| `content`       | `string`         | 否   | Jinja2 模板内容              |
| `vendors`       | `array`          | 否   | 适用厂商列表                 |
| `device_type`   | `DeviceType`     | 否   | 适用设备类型                 |
| `parameters`    | `string`         | 否   | 参数定义(JSON Schema 字符串) |
| `status`        | `TemplateStatus` | 否   | 模板状态                     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除模板

**URL**: `/api/v1/templates/templates/{template_id}`

**Method**: `DELETE`

**Description**:

删除指定的模板。

Args:
template_id (UUID): 模板 ID。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 被删除的模板信息。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建新版本(草稿)

**URL**: `/api/v1/templates/templates/{template_id}/new-version`

**Method**: `POST`

**Description**:

基于现有模板创建一个新的修订版本（初始为草稿）。

Args:
template_id (UUID): 源模板 ID。
body (TemplateNewVersionRequest): 新版本的信息描述。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 新版本的模板详情。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名        | 类型     | 必填 | 描述             |
| :------------ | :------- | :--- | :--------------- |
| `name`        | `string` | 否   | 新版本名称(可选) |
| `description` | `string` | 否   | 新版本描述(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 提交模板审批

**URL**: `/api/v1/templates/templates/{template_id}/submit`

**Method**: `POST`

**Description**:

将草稿状态的模板提交至审批流程。

Args:
template_id (UUID): 模板 ID。
body (TemplateSubmitRequest): 提交备注信息。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 更新状态后的模板详情。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名    | 类型     | 必填 | 描述           |
| :-------- | :------- | :--- | :------------- |
| `comment` | `string` | 否   | 提交说明(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## Topology

### 获取拓扑数据

**URL**: `/api/v1/topology/topology/`

**Method**: `GET`

**Description**:

获取完整的网络拓扑数据，用于前端 vis.js 或相关拓扑引擎渲染。

Args:
db (Session): 数据库会话。
topology_service (TopologyService): 拓扑服务依赖。

Returns:
TopologyResponse: 包含节点 (nodes)、边 (edges) 和统计数据的对象。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名  | 类型                  | 必填 | 描述     |
| :------ | :-------------------- | :--- | :------- |
| `nodes` | `Array[TopologyNode]` | 否   | 节点列表 |
| `edges` | `Array[TopologyEdge]` | 否   | 边列表   |
| `stats` | `TopologyStats`       | 否   | 统计信息 |

---

### 获取链路列表

**URL**: `/api/v1/topology/topology/links`

**Method**: `GET`

**Description**:

分页获取所有已发现的网络链路列表。

Args:
db (Session): 数据库会话。
topology_service (TopologyService): 拓扑服务依赖。
page (int): 页码。
page_size (int): 每页条数。

Returns:
dict[str, Any]: 包含 links 列表和分页信息的字典。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 50      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备邻居

**URL**: `/api/v1/topology/topology/device/{device_id}/neighbors`

**Method**: `GET`

**Description**:

获取指定设备的所有直接连接的邻居链路。

Args:
db (Session): 数据库会话。
device_id (UUID): 设备 ID。
topology_service (TopologyService): 拓扑服务依赖。

Returns:
DeviceNeighborsResponse: 邻居链路列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名        | 类型                          | 必填 | 描述         |
| :------------ | :---------------------------- | :--- | :----------- |
| `device_id`   | `string`                      | 是   | 设备ID       |
| `device_name` | `string`                      | 否   | 设备名称     |
| `neighbors`   | `Array[TopologyLinkResponse]` | 否   | 邻居链路列表 |
| `total`       | `integer`                     | 否   | 邻居总数     |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 导出拓扑数据

**URL**: `/api/v1/topology/topology/export`

**Method**: `GET`

**Description**:

导出全量拓扑数据为 JSON 文件。

Args:
db (Session): 数据库会话。
topology_service (TopologyService): 拓扑服务依赖。

Returns:
JSONResponse: 下载响应。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

---

### 刷新拓扑

**URL**: `/api/v1/topology/topology/refresh`

**Method**: `POST`

**Description**:

触发全局或指定范围的拓扑发现任务。

Args:
request (TopologyCollectRequest): 采集请求参数，包括指定设备列表和是否异步。
current_user (User): 当前操作用户。

Returns:
dict[str, Any]: 任务 ID 或同步执行结果。

#### Request Body (application/json)

| 参数名       | 类型      | 必填 | 描述                            |
| :----------- | :-------- | :--- | :------------------------------ |
| `device_ids` | `array`   | 否   | 指定设备ID列表 (为空则采集所有) |
| `async_mode` | `boolean` | 否   | 是否异步执行                    |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 采集单设备拓扑

**URL**: `/api/v1/topology/topology/device/{device_id}/collect`

**Method**: `POST`

**Description**:

针对单个特定设备执行 LLDP 邻居采集。

Args:
device_id (UUID): 设备 ID。
current_user (User): 当前用户。
async_mode (bool): 是否异步模式。

Returns:
dict[str, Any]: 任务 ID 或执行信息。

#### Requests Parameters (Query/Path)

| 参数名       | 位置    | 类型      | 必填 | 描述       | Default |
| :----------- | :------ | :-------- | :--- | :--------- | :------ |
| `device_id`  | `path`  | `string`  | 是   | Device Id  |         |
| `async_mode` | `query` | `boolean` | 否   | Async Mode | True    |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询拓扑任务状态

**URL**: `/api/v1/topology/topology/task/{task_id}`

**Method**: `GET`

**Description**:

查询拓扑采集后台任务的执行实时状态。

Args:
task_id (str): Celery 任务 ID。

Returns:
TopologyTaskStatus: 任务状态和（如有）结果数据。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名     | 类型                    | 必填 | 描述       |
| :--------- | :---------------------- | :--- | :--------- |
| `task_id`  | `string`                | 是   | 任务ID     |
| `status`   | `string`                | 是   | 任务状态   |
| `progress` | `integer`               | 否   | 进度百分比 |
| `result`   | `TopologyCollectResult` | 否   | 采集结果   |
| `error`    | `string`                | 否   | 错误信息   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 重建拓扑缓存

**URL**: `/api/v1/topology/topology/cache/rebuild`

**Method**: `POST`

**Description**:

强制重新从数据库构建拓扑缓存并更新到 Redis。

Args:
current_user (User): 当前用户。

Returns:
dict[str, Any]: 任务 ID 信息。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

---

## Uncategorized

### Health Check

**URL**: `/api/v1/health`

**Method**: `GET`

**Description**:

健康检查接口 (Database & Cache Check).

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

---

## Users

### 获取用户列表

**URL**: `/api/v1/users/`

**Method**: `GET`

**Description**:

查询用户列表 (分页)。

获取所有系统用户，支持分页。需要用户-列表权限。

Args:
user\*service (UserService): 用户服务依赖。
current_user (User): 当前登录用户。

- (User): 权限依赖（需要 user:list）。
  page (int, optional): 页码. Defaults to 1.
  page_size (int, optional): 每页数量. Defaults to 20.
  keyword (str | None, optional): 关键词过滤. Defaults to None.
  is_superuser (bool | None, optional): 是否超级管理员过滤. Defaults to None.
  is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[UserResponse]]: 分页后的用户列表。

#### Requests Parameters (Query/Path)

| 参数名         | 位置    | 类型      | 必填 | 描述         | Default |
| :------------- | :------ | :-------- | :--- | :----------- | :------ |
| `page`         | `query` | `integer` | 否   | Page         | 1       |
| `page_size`    | `query` | `integer` | 否   | Page Size    | 20      |
| `keyword`      | `query` | `string`  | 否   | Keyword      |         |
| `is_superuser` | `query` | `string`  | 否   | Is Superuser |         |
| `is_active`    | `query` | `string`  | 否   | Is Active    |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_UserResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建用户

**URL**: `/api/v1/users/`

**Method**: `POST`

**Description**:

创建新用户。

注册新的系统用户。需要用户-创建权限。

Args:
user\*in (UserCreate): 用户创建数据 (用户名, 密码, 邮箱等)。
current_user (User): 当前登录用户。

- (User): 权限依赖（需要 user:create）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[UserResponse]: 创建成功的用户对象。

#### Request Body (application/json)

| 参数名         | 类型      | 必填 | 描述             |
| :------------- | :-------- | :--- | :--------------- |
| `username`     | `string`  | 是   | 用户名           |
| `email`        | `string`  | 否   | 邮箱             |
| `phone`        | `string`  | 是   | 手机号           |
| `nickname`     | `string`  | 否   | 昵称             |
| `gender`       | `string`  | 否   | 性别             |
| `is_active`    | `boolean` | 否   | 是否激活         |
| `is_superuser` | `boolean` | 否   | 是否为超级管理员 |
| `dept_id`      | `string`  | 否   | 所属部门ID       |
| `password`     | `string`  | 是   | 密码             |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量删除用户

**URL**: `/api/v1/users/batch`

**Method**: `DELETE`

**Description**:

批量删除用户。

支持软删除和硬删除。需要用户-删除权限。

Args:
request (BatchDeleteRequest): 批量删除请求体 (包含 ID 列表和硬删除标志)。
current\*user (User): 当前登录用户。

- (User): 权限依赖（需要 user:delete）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量操作结果（成功数量等）。

#### Request Body (application/json)

| 参数名        | 类型            | 必填 | 描述                    |
| :------------ | :-------------- | :--- | :---------------------- |
| `ids`         | `Array[string]` | 是   | 要删除的 ID 列表        |
| `hard_delete` | `boolean`       | 否   | 是否硬删除 (默认软删除) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取当前用户

**URL**: `/api/v1/users/me`

**Method**: `GET`

**Description**:

获取当前用户信息。

返回当前登录用户的详细信息。

Args:
current_user (User): 当前登录用户 (由依赖自动注入)。

Returns:
ResponseBase[UserResponse]: 当前用户的详细信息。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

---

### 更新当前用户

**URL**: `/api/v1/users/me`

**Method**: `PUT`

**Description**:

更新当前用户信息。

用户自行修改个人资料（如昵称、邮箱、手机号等）。

Args:
user_service (UserService): 用户服务依赖。
user_in (UserUpdate): 用户更新数据。
current_user (User): 当前登录用户。

Returns:
ResponseBase[UserResponse]: 更新后的用户信息。

#### Request Body (application/json)

| 参数名     | 类型     | 必填 | 描述     |
| :--------- | :------- | :--- | :------- |
| `email`    | `string` | 否   | Email    |
| `phone`    | `string` | 否   | Phone    |
| `nickname` | `string` | 否   | Nickname |
| `gender`   | `string` | 否   | Gender   |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 修改密码 (当前用户)

**URL**: `/api/v1/users/me/password`

**Method**: `PUT`

**Description**:

修改当前用户密码。

需要验证旧密码是否正确。

Args:
user_service (UserService): 用户服务依赖。
password_data (ChangePasswordRequest): 密码修改请求 (包含旧密码和新密码)。
current_user (User): 当前登录用户。

Returns:
ResponseBase[UserResponse]: 用户信息 (密码修改成功后)。

#### Request Body (application/json)

| 参数名         | 类型     | 必填 | 描述   |
| :------------- | :------- | :--- | :----- |
| `old_password` | `string` | 是   | 旧密码 |
| `new_password` | `string` | 是   | 新密码 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 重置密码 (管理员)

**URL**: `/api/v1/users/{user_id}/password`

**Method**: `PUT`

**Description**:

管理员重置用户密码。

强制修改指定用户的密码，不需要知道旧密码。需要用户-重置密码权限。

Args:
user\*id (UUID): 目标用户 ID。
password_data (ResetPasswordRequest): 密码重置请求 (包含新密码)。
current_user (User): 当前登录用户。

- (User): 权限依赖（需要 user:password:reset）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[UserResponse]: 用户信息 (密码重置成功后)。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Request Body (application/json)

| 参数名         | 类型     | 必填 | 描述   |
| :------------- | :------- | :--- | :----- |
| `new_password` | `string` | 是   | 新密码 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取用户回收站列表

**URL**: `/api/v1/users/recycle-bin`

**Method**: `GET`

**Description**:

获取已删除的用户列表 (回收站)。
需要用户-回收站权限。

Args:
page (int, optional): 页码. Defaults to 1.
page\*size (int, optional): 每页数量. Defaults to 20.

- (User): 权限依赖（需要 user:recycle）。
  user_service (UserService): 用户服务依赖。
  keyword (str | None, optional): 关键词过滤. Defaults to None.
  is_superuser (bool | None, optional): 是否超级管理员过滤. Defaults to None.
  is_active (bool | None, optional): 是否启用过滤. Defaults to None.

Returns:
ResponseBase[PaginatedResponse[UserResponse]]: 分页后的用户列表。

#### Requests Parameters (Query/Path)

| 参数名         | 位置    | 类型      | 必填 | 描述         | Default |
| :------------- | :------ | :-------- | :--- | :----------- | :------ |
| `page`         | `query` | `integer` | 否   | Page         | 1       |
| `page_size`    | `query` | `integer` | 否   | Page Size    | 20      |
| `keyword`      | `query` | `string`  | 否   | Keyword      |         |
| `is_superuser` | `query` | `string`  | 否   | Is Superuser |         |
| `is_active`    | `query` | `string`  | 否   | Is Active    |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                              | 必填 | 描述    |
| :-------- | :-------------------------------- | :--- | :------ |
| `code`    | `integer`                         | 否   | Code    |
| `message` | `string`                          | 否   | Message |
| `data`    | `PaginatedResponse_UserResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取特定用户信息

**URL**: `/api/v1/users/{user_id}`

**Method**: `GET`

**Description**:

获取特定用户的详细信息 (管理员)。

Args:
user\*id (UUID): 目标用户 ID。

- (User): 权限依赖（需要 user:list）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[UserResponse]: 用户详细信息。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新用户信息 (管理员)

**URL**: `/api/v1/users/{user_id}`

**Method**: `PUT`

**Description**:

管理员更新用户信息。

允许具备权限的管理员修改任意用户的资料 (昵称、手机号、邮箱、状态等)。
不包含密码修改 (请使用重置密码接口)。

Args:
user\*id (UUID): 目标用户 ID。
user_in (UserUpdate): 更新的用户数据。

- (User): 权限依赖（需要 user:update）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[UserResponse]: 更新后的用户信息。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Request Body (application/json)

| 参数名         | 类型      | 必填 | 描述         |
| :------------- | :-------- | :--- | :----------- |
| `username`     | `string`  | 否   | Username     |
| `email`        | `string`  | 否   | Email        |
| `phone`        | `string`  | 否   | Phone        |
| `nickname`     | `string`  | 否   | Nickname     |
| `gender`       | `string`  | 否   | Gender       |
| `is_active`    | `boolean` | 否   | Is Active    |
| `is_superuser` | `boolean` | 否   | Is Superuser |
| `dept_id`      | `string`  | 否   | Dept Id      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量恢复用户

**URL**: `/api/v1/users/batch/restore`

**Method**: `POST`

**Description**:

批量恢复用户。

从回收站中批量恢复软删除用户。

Args:
request (BatchRestoreRequest): 批量恢复请求体 (包含 ID 列表)。
current\*user (User): 当前登录用户。

- (User): 权限依赖（需要 user:restore）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[BatchOperationResult]: 批量恢复结果。

#### Request Body (application/json)

| 参数名 | 类型            | 必填 | 描述             |
| :----- | :-------------- | :--- | :--------------- |
| `ids`  | `Array[string]` | 是   | 要恢复的 ID 列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                   | 必填 | 描述    |
| :-------- | :--------------------- | :--- | :------ |
| `code`    | `integer`              | 否   | Code    |
| `message` | `string`               | 否   | Message |
| `data`    | `BatchOperationResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 恢复已删除用户

**URL**: `/api/v1/users/{user_id}/restore`

**Method**: `POST`

**Description**:

恢复已删除用户。

从回收站中恢复指定用户。
需要用户-恢复权限。

Args:
user\*id (UUID): 目标用户 ID。

- (User): 权限依赖（需要 user:restore）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[UserResponse]: 恢复后的用户信息。

Raises:
UnauthorizedException: 未登录或令牌无效时。
ForbiddenException: 权限不足时。
NotFoundException: 用户不存在时。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型           | 必填 | 描述    |
| :-------- | :------------- | :--- | :------ |
| `code`    | `integer`      | 否   | Code    |
| `message` | `string`       | 否   | Message |
| `data`    | `UserResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取用户角色

**URL**: `/api/v1/users/{user_id}/roles`

**Method**: `GET`

**Description**:

获取用户已绑定的角色列表。

Args:
user\*id (UUID): 目标用户 ID。
current_user (User): 当前登录用户。

- (User): 权限依赖（需要 user:roles:list）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[list[RoleResponse]]: 用户已绑定的角色列表。

Raises:
UnauthorizedException: 未登录或令牌无效时。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 设置用户角色

**URL**: `/api/v1/users/{user_id}/roles`

**Method**: `PUT`

**Description**:

设置用户角色（全量覆盖，幂等）。

Args:
user\*id (UUID): 目标用户 ID。
req (UserRolesUpdateRequest): 用户角色更新请求体 (包含角色 ID 列表)。
current_user (User): 当前登录用户。

- (User): 权限依赖（需要 user:roles:update）。
  user_service (UserService): 用户服务依赖。

Returns:
ResponseBase[list[RoleResponse]]: 用户已绑定的角色列表。

Raises:
UnauthorizedException: 未登录或令牌无效时。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `user_id` | `path` | `string` | 是   | User Id |         |

#### Request Body (application/json)

| 参数名     | 类型            | 必填 | 描述       |
| :--------- | :-------------- | :--- | :--------- |
| `role_ids` | `Array[string]` | 否   | 角色ID列表 |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `array`   | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## 安全批量下发

### 创建下发任务

**URL**: `/api/v1/deploy/deploy/`

**Method**: `POST`

**Description**:

创建批量设备配置下发任务。

通过指定渲染后的配置内容和目标设备，并在正式下发前创建多级审批流。

Args:
body (DeployCreateRequest): 包含任务名称、描述、目标设备及下发内容的请求。
service (DeployService): 下发服务依赖。
user (User): 任务提交人。

Returns:
ResponseBase[DeployTaskResponse]: 包含初始状态及审批进度的任务详情。

#### Request Body (application/json)

| 参数名               | 类型            | 必填 | 描述                             |
| :------------------- | :-------------- | :--- | :------------------------------- |
| `name`               | `string`        | 是   | Name                             |
| `description`        | `string`        | 否   | Description                      |
| `template_id`        | `string`        | 是   | 模板ID                           |
| `template_params`    | `object`        | 否   | 模板参数                         |
| `device_ids`         | `Array[string]` | 是   | 目标设备ID列表                   |
| `change_description` | `string`        | 否   | 变更说明                         |
| `impact_scope`       | `string`        | 否   | 影响范围                         |
| `rollback_plan`      | `string`        | 否   | 回退方案                         |
| `approver_ids`       | `array`         | 否   | 三级审批人ID列表（长度=3，可选） |
| `deploy_plan`        | `DeployPlan`    | 否   |                                  |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 下发任务列表（复用 Task 表）

**URL**: `/api/v1/deploy/deploy/`

**Method**: `GET`

**Description**:

获取所有批量配置下发任务的列表。

Args:
service (DeployService): 下发服务依赖。
page (int): 当前页码。
page_size (int): 每页限制数量。

Returns:
ResponseBase[PaginatedResponse[DeployTaskResponse]]: 分页后的任务概览。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                    | 必填 | 描述    |
| :-------- | :-------------------------------------- | :--- | :------ |
| `code`    | `integer`                               | 否   | Code    |
| `message` | `string`                                | 否   | Message |
| `data`    | `PaginatedResponse_DeployTaskResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 审批(某一级)

**URL**: `/api/v1/deploy/deploy/{task_id}/approve`

**Method**: `POST`

**Description**:

对指定的下发任务进行单级审批操作。

支持多级审批逻辑。如果所有级别均已通过，任务状态将更新为“已审批”。

Args:
task_id (UUID): 任务 ID。
body (DeployApproveRequest): 包含审批级别、审批结论 (通过/拒绝) 及意见。
service (DeployService): 下发服务依赖。
user (User): 当前审批人。

Returns:
ResponseBase[DeployTaskResponse]: 更新后的任务及审批进度。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Request Body (application/json)

| 参数名    | 类型      | 必填 | 描述                 |
| :-------- | :-------- | :--- | :------------------- |
| `level`   | `integer` | 是   | Level                |
| `approve` | `boolean` | 是   | true=通过 false=拒绝 |
| `comment` | `string`  | 否   | Comment              |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 执行下发任务（提交 Celery）

**URL**: `/api/v1/deploy/deploy/{task_id}/execute`

**Method**: `POST`

**Description**:

执行已审批通过的下发任务。

该接口会将执行逻辑委托给 Celery 异步队列，避免前端长连接阻塞。

Args:
task_id (UUID): 任务 ID。
service (DeployService): 下发服务依赖。

Raises:
BadRequestException: 如果任务类型不匹配或任务未处于“已审批”状态。

Returns:
ResponseBase[DeployTaskResponse]: 已绑定 Celery 任务 ID 的详情。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 触发回滚（Celery）

**URL**: `/api/v1/deploy/deploy/{task_id}/rollback`

**Method**: `POST`

**Description**:

对发生故障或需要撤回的下发任务进行回滚操作。

回滚通常通过在设备上执行反向指令或还原历史配置实现（具体视设备支持而定）。

Args:
task_id (UUID): 原下发任务 ID。

Returns:
ResponseBase[DeployRollbackResponse]: 包含回滚 Celery 任务 ID 的响应。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                     | 必填 | 描述    |
| :-------- | :----------------------- | :--- | :------ |
| `code`    | `integer`                | 否   | Code    |
| `message` | `string`                 | 否   | Message |
| `data`    | `DeployRollbackResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 下发任务详情

**URL**: `/api/v1/deploy/deploy/{task_id}`

**Method**: `GET`

**Description**:

获取下发任务的完整详细信息。

Args:
task_id (UUID): 任务 ID。
service (DeployService): 下发服务依赖。

Returns:
ResponseBase[DeployTaskResponse]: 包含设备下发日志及状态的详细数据。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                 | 必填 | 描述    |
| :-------- | :------------------- | :--- | :------ |
| `code`    | `integer`            | 否   | Code    |
| `message` | `string`             | 否   | Message |
| `data`    | `DeployTaskResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## 模板库

### 获取模板列表

**URL**: `/api/v1/templates/templates/`

**Method**: `GET`

**Description**:

分页获取配置模板列表。

Args:
service (TemplateService): 模板服务依赖。
page (int): 当前页码。
page_size (int): 每页大小（1-100）。
vendor (DeviceVendor | None): 按厂商过滤。
template_type (TemplateType | None): 按模板类型过滤。
status (TemplateStatus | None): 按状态过滤。

Returns:
ResponseBase[PaginatedResponse[TemplateResponse]]: 包含模板列表的分页响应。

#### Requests Parameters (Query/Path)

| 参数名          | 位置    | 类型      | 必填 | 描述          | Default |
| :-------------- | :------ | :-------- | :--- | :------------ | :------ |
| `page`          | `query` | `integer` | 否   | Page          | 1       |
| `page_size`     | `query` | `integer` | 否   | Page Size     | 20      |
| `vendor`        | `query` | `string`  | 否   | Vendor        |         |
| `template_type` | `query` | `string`  | 否   | Template Type |         |
| `status`        | `query` | `string`  | 否   | Status        |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                  | 必填 | 描述    |
| :-------- | :------------------------------------ | :--- | :------ |
| `code`    | `integer`                             | 否   | Code    |
| `message` | `string`                              | 否   | Message |
| `data`    | `PaginatedResponse_TemplateResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建模板(草稿)

**URL**: `/api/v1/templates/templates/`

**Method**: `POST`

**Description**:

创建一个新的配置模板草稿。

Args:
data (TemplateCreate): 创建表单数据。
service (TemplateService): 模板服务依赖。
user (User): 创建者信息。

Returns:
ResponseBase[TemplateResponse]: 创建成功的模板信息。

#### Request Body (application/json)

| 参数名          | 类型                  | 必填 | 描述                         |
| :-------------- | :-------------------- | :--- | :--------------------------- |
| `name`          | `string`              | 是   | 模板名称                     |
| `description`   | `string`              | 否   | 模板描述                     |
| `template_type` | `TemplateType`        | 否   | 模板类型                     |
| `content`       | `string`              | 是   | Jinja2 模板内容              |
| `vendors`       | `Array[DeviceVendor]` | 是   | 适用厂商列表                 |
| `device_type`   | `DeviceType`          | 否   | 适用设备类型                 |
| `parameters`    | `string`              | 否   | 参数定义(JSON Schema 字符串) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取模板详情

**URL**: `/api/v1/templates/templates/{template_id}`

**Method**: `GET`

**Description**:

根据 ID 获取模板的详细定义信息。

Args:
template_id (UUID): 模板 ID。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 模板详情。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 更新模板

**URL**: `/api/v1/templates/templates/{template_id}`

**Method**: `PUT`

**Description**:

更新处于草稿或拒绝状态的模板。

Args:
template_id (UUID): 模板 ID。
data (TemplateUpdate): 要更新的字段。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 更新后的模板信息。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名          | 类型             | 必填 | 描述                         |
| :-------------- | :--------------- | :--- | :--------------------------- |
| `name`          | `string`         | 否   | 模板名称                     |
| `description`   | `string`         | 否   | 模板描述                     |
| `template_type` | `TemplateType`   | 否   | 模板类型                     |
| `content`       | `string`         | 否   | Jinja2 模板内容              |
| `vendors`       | `array`          | 否   | 适用厂商列表                 |
| `device_type`   | `DeviceType`     | 否   | 适用设备类型                 |
| `parameters`    | `string`         | 否   | 参数定义(JSON Schema 字符串) |
| `status`        | `TemplateStatus` | 否   | 模板状态                     |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除模板

**URL**: `/api/v1/templates/templates/{template_id}`

**Method**: `DELETE`

**Description**:

删除指定的模板。

Args:
template_id (UUID): 模板 ID。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 被删除的模板信息。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 创建新版本(草稿)

**URL**: `/api/v1/templates/templates/{template_id}/new-version`

**Method**: `POST`

**Description**:

基于现有模板创建一个新的修订版本（初始为草稿）。

Args:
template_id (UUID): 源模板 ID。
body (TemplateNewVersionRequest): 新版本的信息描述。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 新版本的模板详情。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名        | 类型     | 必填 | 描述             |
| :------------ | :------- | :--- | :--------------- |
| `name`        | `string` | 否   | 新版本名称(可选) |
| `description` | `string` | 否   | 新版本描述(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 提交模板审批

**URL**: `/api/v1/templates/templates/{template_id}/submit`

**Method**: `POST`

**Description**:

将草稿状态的模板提交至审批流程。

Args:
template_id (UUID): 模板 ID。
body (TemplateSubmitRequest): 提交备注信息。
service (TemplateService): 模板服务依赖。

Returns:
ResponseBase[TemplateResponse]: 更新状态后的模板详情。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名    | 类型     | 必填 | 描述           |
| :-------- | :------- | :--- | :------------- |
| `comment` | `string` | 否   | 提交说明(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `TemplateResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## 网络拓扑

### 获取拓扑数据

**URL**: `/api/v1/topology/topology/`

**Method**: `GET`

**Description**:

获取完整的网络拓扑数据，用于前端 vis.js 或相关拓扑引擎渲染。

Args:
db (Session): 数据库会话。
topology_service (TopologyService): 拓扑服务依赖。

Returns:
TopologyResponse: 包含节点 (nodes)、边 (edges) 和统计数据的对象。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名  | 类型                  | 必填 | 描述     |
| :------ | :-------------------- | :--- | :------- |
| `nodes` | `Array[TopologyNode]` | 否   | 节点列表 |
| `edges` | `Array[TopologyEdge]` | 否   | 边列表   |
| `stats` | `TopologyStats`       | 否   | 统计信息 |

---

### 获取链路列表

**URL**: `/api/v1/topology/topology/links`

**Method**: `GET`

**Description**:

分页获取所有已发现的网络链路列表。

Args:
db (Session): 数据库会话。
topology_service (TopologyService): 拓扑服务依赖。
page (int): 页码。
page_size (int): 每页条数。

Returns:
dict[str, Any]: 包含 links 列表和分页信息的字典。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 50      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备邻居

**URL**: `/api/v1/topology/topology/device/{device_id}/neighbors`

**Method**: `GET`

**Description**:

获取指定设备的所有直接连接的邻居链路。

Args:
db (Session): 数据库会话。
device_id (UUID): 设备 ID。
topology_service (TopologyService): 拓扑服务依赖。

Returns:
DeviceNeighborsResponse: 邻居链路列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名        | 类型                          | 必填 | 描述         |
| :------------ | :---------------------------- | :--- | :----------- |
| `device_id`   | `string`                      | 是   | 设备ID       |
| `device_name` | `string`                      | 否   | 设备名称     |
| `neighbors`   | `Array[TopologyLinkResponse]` | 否   | 邻居链路列表 |
| `total`       | `integer`                     | 否   | 邻居总数     |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 导出拓扑数据

**URL**: `/api/v1/topology/topology/export`

**Method**: `GET`

**Description**:

导出全量拓扑数据为 JSON 文件。

Args:
db (Session): 数据库会话。
topology_service (TopologyService): 拓扑服务依赖。

Returns:
JSONResponse: 下载响应。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

---

### 刷新拓扑

**URL**: `/api/v1/topology/topology/refresh`

**Method**: `POST`

**Description**:

触发全局或指定范围的拓扑发现任务。

Args:
request (TopologyCollectRequest): 采集请求参数，包括指定设备列表和是否异步。
current_user (User): 当前操作用户。

Returns:
dict[str, Any]: 任务 ID 或同步执行结果。

#### Request Body (application/json)

| 参数名       | 类型      | 必填 | 描述                            |
| :----------- | :-------- | :--- | :------------------------------ |
| `device_ids` | `array`   | 否   | 指定设备ID列表 (为空则采集所有) |
| `async_mode` | `boolean` | 否   | 是否异步执行                    |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 采集单设备拓扑

**URL**: `/api/v1/topology/topology/device/{device_id}/collect`

**Method**: `POST`

**Description**:

针对单个特定设备执行 LLDP 邻居采集。

Args:
device_id (UUID): 设备 ID。
current_user (User): 当前用户。
async_mode (bool): 是否异步模式。

Returns:
dict[str, Any]: 任务 ID 或执行信息。

#### Requests Parameters (Query/Path)

| 参数名       | 位置    | 类型      | 必填 | 描述       | Default |
| :----------- | :------ | :-------- | :--- | :--------- | :------ |
| `device_id`  | `path`  | `string`  | 是   | Device Id  |         |
| `async_mode` | `query` | `boolean` | 否   | Async Mode | True    |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询拓扑任务状态

**URL**: `/api/v1/topology/topology/task/{task_id}`

**Method**: `GET`

**Description**:

查询拓扑采集后台任务的执行实时状态。

Args:
task_id (str): Celery 任务 ID。

Returns:
TopologyTaskStatus: 任务状态和（如有）结果数据。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名     | 类型                    | 必填 | 描述       |
| :--------- | :---------------------- | :--- | :--------- |
| `task_id`  | `string`                | 是   | 任务ID     |
| `status`   | `string`                | 是   | 任务状态   |
| `progress` | `integer`               | 否   | 进度百分比 |
| `result`   | `TopologyCollectResult` | 否   | 采集结果   |
| `error`    | `string`                | 否   | 错误信息   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 重建拓扑缓存

**URL**: `/api/v1/topology/topology/cache/rebuild`

**Method**: `POST`

**Description**:

强制重新从数据库构建拓扑缓存并更新到 Redis。

Args:
current_user (User): 当前用户。

Returns:
dict[str, Any]: 任务 ID 信息。

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

---

## 设备发现

### 触发网络扫描

**URL**: `/api/v1/discovery/discovery/scan`

**Method**: `POST`

**Description**:

触发针对特定网段的网络扫描任务。

通过 Nmap 或 Masscan 发现网络中的在线资产，并识别其开放端口及服务横幅。

Args:
request (ScanRequest): 包含网段、扫描类型、端口、扫描模式（同步/异步）的请求。
current_user (CurrentUser): 当前操作人。

Returns:
dict[str, Any]: 如果是异步模式，返回包含 task_id 的字典；同步模式返回扫描结果。

#### Request Body (application/json)

| 参数名       | 类型            | 必填 | 描述                       |
| :----------- | :-------------- | :--- | :------------------------- |
| `subnets`    | `Array[string]` | 是   | 待扫描网段列表 (CIDR 格式) |
| `scan_type`  | `string`        | 否   | 扫描类型 (nmap/masscan)    |
| `ports`      | `string`        | 否   | 扫描端口 (如 22,23,80,443) |
| `async_mode` | `boolean`       | 否   | 是否异步执行               |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询扫描任务状态

**URL**: `/api/v1/discovery/discovery/scan/task/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 扫描任务的当前进度和最终发现的资产。

Args:
task_id (str): Celery 任务 ID。

Returns:
ScanTaskStatus: 包含状态 (PENDING/SUCCESS) 及匹配记录或错误的详情。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名     | 类型         | 必填 | 描述       |
| :--------- | :----------- | :--- | :--------- |
| `task_id`  | `string`     | 是   | 任务ID     |
| `status`   | `string`     | 是   | 任务状态   |
| `progress` | `integer`    | 否   | 进度百分比 |
| `result`   | `ScanResult` | 否   | 扫描结果   |
| `error`    | `string`     | 否   | 错误信息   |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取发现记录列表

**URL**: `/api/v1/discovery/discovery/`

**Method**: `GET`

**Description**:

获取通过网络扫描发现的所有设备记录。

Args:
db (Session): 数据库会话。
page (int): 当前页码。
page_size (int): 每页限制。
status (DiscoveryStatus | None): 状态过滤（如：NEW, IGNORED, MATCHED）。
keyword (str | None): 匹配 IP、MAC、主机名的搜索关键词。
scan_source (str | None): 识别扫描的具体来源标识。

Returns:
PaginatedResponse[DiscoveryResponse]: 包含发现资产详情的分页响应。

#### Requests Parameters (Query/Path)

| 参数名        | 位置    | 类型      | 必填 | 描述       | Default |
| :------------ | :------ | :-------- | :--- | :--------- | :------ |
| `page`        | `query` | `integer` | 否   | 页码       | 1       |
| `page_size`   | `query` | `integer` | 否   | 每页数量   | 20      |
| `status`      | `query` | `string`  | 否   | 状态筛选   |         |
| `keyword`     | `query` | `string`  | 否   | 关键词搜索 |         |
| `scan_source` | `query` | `string`  | 否   | 扫描来源   |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名      | 类型                       | 必填 | 描述     |
| :---------- | :------------------------- | :--- | :------- |
| `total`     | `integer`                  | 是   | 总记录数 |
| `page`      | `integer`                  | 是   | 当前页码 |
| `page_size` | `integer`                  | 是   | 每页大小 |
| `items`     | `Array[DiscoveryResponse]` | 否   | 数据列表 |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取发现记录详情

**URL**: `/api/v1/discovery/discovery/{discovery_id}`

**Method**: `GET`

**Description**:

获取单个扫描发现记录的完整属性。

Args:
db (Session): 数据库会话。
discovery_id (UUID): 扫描结果主键 ID。

Returns:
DiscoveryResponse: 发现资产及 CMDB 匹配关联信息。

#### Requests Parameters (Query/Path)

| 参数名         | 位置   | 类型     | 必填 | 描述         | Default |
| :------------- | :----- | :------- | :--- | :----------- | :------ |
| `discovery_id` | `path` | `string` | 是   | Discovery Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名                | 类型      | 必填 | 描述              |
| :-------------------- | :-------- | :--- | :---------------- |
| `ip_address`          | `string`  | 是   | IP 地址           |
| `mac_address`         | `string`  | 否   | MAC 地址          |
| `vendor`              | `string`  | 否   | 厂商              |
| `device_type`         | `string`  | 否   | 设备类型          |
| `hostname`            | `string`  | 否   | 主机名            |
| `os_info`             | `string`  | 否   | 操作系统信息      |
| `id`                  | `string`  | 是   | Id                |
| `open_ports`          | `object`  | 否   | Open Ports        |
| `ssh_banner`          | `string`  | 否   | Ssh Banner        |
| `first_seen_at`       | `string`  | 是   | First Seen At     |
| `last_seen_at`        | `string`  | 是   | Last Seen At      |
| `offline_days`        | `integer` | 是   | Offline Days      |
| `status`              | `string`  | 是   | Status            |
| `matched_device_id`   | `string`  | 否   | Matched Device Id |
| `scan_source`         | `string`  | 否   | Scan Source       |
| `created_at`          | `string`  | 是   | Created At        |
| `updated_at`          | `string`  | 是   | Updated At        |
| `matched_device_name` | `string`  | 否   | 匹配设备名称      |
| `matched_device_ip`   | `string`  | 否   | 匹配设备IP        |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除发现记录

**URL**: `/api/v1/discovery/discovery/{discovery_id}`

**Method**: `DELETE`

**Description**:

物理删除或隐藏特定的扫描发现结果。

Args:
db (Session): 数据库会话。
discovery_id (UUID): 扫描记录 ID。
current_user (CurrentUser): 当前执行操作的用户。

Returns:
dict[str, str]: 确认删除的消息。

#### Requests Parameters (Query/Path)

| 参数名         | 位置   | 类型     | 必填 | 描述         | Default |
| :------------- | :----- | :------- | :--- | :----------- | :------ |
| `discovery_id` | `path` | `string` | 是   | Discovery Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 纳管设备

**URL**: `/api/v1/discovery/discovery/{discovery_id}/adopt`

**Method**: `POST`

**Description**:

将扫描结果中的在线资产直接录入为系统正式管理的设备。

录入过程会预填发现的 IP、MAC、厂商等信息，并根据请求配置所属部门和凭据。

Args:
db (Session): 数据库会话。
discovery_id (UUID): 发现记录关联 ID。
request (AdoptDeviceRequest): 纳管配置，包含名称、分组、凭据等。
scan_service (ScanService): 扫描资产服务。
current_user (CurrentUser): 当前操作人。

Returns:
dict[str, Any]: 包含新设备 ID 的确认响应。

#### Requests Parameters (Query/Path)

| 参数名         | 位置   | 类型     | 必填 | 描述         | Default |
| :------------- | :----- | :------- | :--- | :----------- | :------ |
| `discovery_id` | `path` | `string` | 是   | Discovery Id |         |

#### Request Body (application/json)

| 参数名         | 类型     | 必填 | 描述       |
| :------------- | :------- | :--- | :--------- |
| `name`         | `string` | 是   | 设备名称   |
| `vendor`       | `string` | 否   | 设备厂商   |
| `device_group` | `string` | 否   | 设备分组   |
| `dept_id`      | `string` | 否   | 所属部门ID |
| `username`     | `string` | 否   | SSH 用户名 |
| `password`     | `string` | 否   | SSH 密码   |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取影子资产列表

**URL**: `/api/v1/discovery/discovery/shadow`

**Method**: `GET`

**Description**:

获取所有已在线但尚未关联正式 CMDB 的网路资产。

Args:
db (Session): 数据库会话。
scan_service (ScanService): 扫描资产服务依赖。
page (int): 当前页码。
page_size (int): 每页限制。

Returns:
PaginatedResponse[DiscoveryResponse]: 影子资产（未知资产）列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `page`      | `query` | `integer` | 否   | Page      | 1       |
| `page_size` | `query` | `integer` | 否   | Page Size | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名      | 类型                       | 必填 | 描述     |
| :---------- | :------------------------- | :--- | :------- |
| `total`     | `integer`                  | 是   | 总记录数 |
| `page`      | `integer`                  | 是   | 当前页码 |
| `page_size` | `integer`                  | 是   | 每页大小 |
| `items`     | `Array[DiscoveryResponse]` | 否   | 数据列表 |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取离线设备列表

**URL**: `/api/v1/discovery/discovery/offline`

**Method**: `GET`

**Description**:

获取由于长时间未能在扫描中发现而标记为离线的设备列表。

系统会将 CMDB 中的设备与最新的扫描记录比对，若超过阈值天数未出现，则视为离线。

Args:
db (Session): 数据库会话。
scan_service (ScanService): 扫描资产服务。
days_threshold (int): 判定离线的天数阈值（默认为 7 天）。

Returns:
list[OfflineDevice]: 包含设备 ID、名称及其最后一次被扫描到的时间。

#### Requests Parameters (Query/Path)

| 参数名           | 位置    | 类型      | 必填 | 描述         | Default |
| :--------------- | :------ | :-------- | :--- | :----------- | :------ |
| `days_threshold` | `query` | `integer` | 否   | 离线天数阈值 | 7       |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 执行 CMDB 比对

**URL**: `/api/v1/discovery/discovery/compare`

**Method**: `POST`

**Description**:

全量对比当前的扫描发现库与正式 CMDB 设备库。

用于同步状态、识别影子资产和更新离线天数统计。建议在完成全网大规模扫描后执行。

Args:
current_user (CurrentUser): 当前操作人。
async_mode (bool): 是否进入 Celery 异步处理模式。

Returns:
dict[str, Any]: 包含任务状态或同步结果的字典。

#### Requests Parameters (Query/Path)

| 参数名       | 位置    | 类型      | 必填 | 描述         | Default |
| :----------- | :------ | :-------- | :--- | :----------- | :------ |
| `async_mode` | `query` | `boolean` | 否   | 是否异步执行 | True    |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## 配置备份

### 获取备份列表

**URL**: `/api/v1/backups/backups/`

**Method**: `GET`

**Description**:

获取分页过滤的配置备份列表。

#### Requests Parameters (Query/Path)

| 参数名        | 位置    | 类型      | 必填 | 描述         | Default |
| :------------ | :------ | :-------- | :--- | :----------- | :------ |
| `page`        | `query` | `integer` | 否   | 页码         | 1       |
| `page_size`   | `query` | `integer` | 否   | 每页数量     | 20      |
| `device_id`   | `query` | `string`  | 否   | 设备ID筛选   |         |
| `backup_type` | `query` | `string`  | 否   | 备份类型筛选 |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                | 必填 | 描述    |
| :-------- | :---------------------------------- | :--- | :------ |
| `code`    | `integer`                           | 否   | Code    |
| `message` | `string`                            | 否   | Message |
| `data`    | `PaginatedResponse_BackupResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取备份详情

**URL**: `/api/v1/backups/backups/{backup_id}`

**Method**: `GET`

**Description**:

根据 ID 获取备份详情。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `BackupResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 删除备份

**URL**: `/api/v1/backups/backups/{backup_id}`

**Method**: `DELETE`

**Description**:

软删除指定的备份记录。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型      | 必填 | 描述    |
| :-------- | :-------- | :--- | :------ |
| `code`    | `integer` | 否   | Code    |
| `message` | `string`  | 否   | Message |
| `data`    | `object`  | 否   | Data    |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取备份配置内容

**URL**: `/api/v1/backups/backups/{backup_id}/content`

**Method**: `GET`

**Description**:

获取备份的完整配置内容。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                    | 必填 | 描述    |
| :-------- | :---------------------- | :--- | :------ |
| `code`    | `integer`               | 否   | Code    |
| `message` | `string`                | 否   | Message |
| `data`    | `BackupContentResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 手动备份单设备

**URL**: `/api/v1/backups/backups/device/{device_id}`

**Method**: `POST`

**Description**:

立即备份指定设备的配置。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Request Body (application/json)

No properties (Empty Object)

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `BackupResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 批量备份设备

**URL**: `/api/v1/backups/backups/batch`

**Method**: `POST`

**Description**:

批量备份多台设备配置（支持断点续传）。

#### Request Body (application/json)

| 参数名            | 类型            | 必填 | 描述               |
| :---------------- | :-------------- | :--- | :----------------- |
| `device_ids`      | `Array[string]` | 是   | 设备ID列表         |
| `backup_type`     | `BackupType`    | 否   | 备份类型           |
| `resume_task_id`  | `string`        | 否   | 断点续传任务ID     |
| `skip_device_ids` | `array`         | 否   | 跳过已成功的设备ID |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                | 必填 | 描述    |
| :-------- | :------------------ | :--- | :------ |
| `code`    | `integer`           | 否   | Code    |
| `message` | `string`            | 否   | Message |
| `data`    | `BackupBatchResult` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 查询备份任务状态

**URL**: `/api/v1/backups/backups/task/{task_id}`

**Method**: `GET`

**Description**:

查询 Celery 异步备份任务的执行状态。

#### Requests Parameters (Query/Path)

| 参数名    | 位置   | 类型     | 必填 | 描述    | Default |
| :-------- | :----- | :------- | :--- | :------ | :------ |
| `task_id` | `path` | `string` | 是   | Task Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型               | 必填 | 描述    |
| :-------- | :----------------- | :--- | :------ |
| `code`    | `integer`          | 否   | Code    |
| `message` | `string`           | 否   | Message |
| `data`    | `BackupTaskStatus` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备最新备份

**URL**: `/api/v1/backups/backups/device/{device_id}/latest`

**Method**: `GET`

**Description**:

获取指定设备的最新成功备份。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `device_id` | `path` | `string` | 是   | Device Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `BackupResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 获取设备备份历史

**URL**: `/api/v1/backups/backups/device/{device_id}/history`

**Method**: `GET`

**Description**:

获取指定设备的备份历史列表。

#### Requests Parameters (Query/Path)

| 参数名      | 位置    | 类型      | 必填 | 描述      | Default |
| :---------- | :------ | :-------- | :--- | :-------- | :------ |
| `device_id` | `path`  | `string`  | 是   | Device Id |         |
| `page`      | `query` | `integer` | 否   | 页码      | 1       |
| `page_size` | `query` | `integer` | 否   | 每页数量  | 20      |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型                                | 必填 | 描述    |
| :-------- | :---------------------------------- | :--- | :------ |
| `code`    | `integer`                           | 否   | Code    |
| `message` | `string`                            | 否   | Message |
| `data`    | `PaginatedResponse_BackupResponse_` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

### 下载备份配置文件

**URL**: `/api/v1/backups/backups/{backup_id}/download`

**Method**: `GET`

**Description**:

将备份配置内容导出为文件下载。

#### Requests Parameters (Query/Path)

| 参数名      | 位置   | 类型     | 必填 | 描述      | Default |
| :---------- | :----- | :------- | :--- | :-------- | :------ |
| `backup_id` | `path` | `string` | 是   | Backup Id |         |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

No properties (Empty Object)

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---

## 配置渲染

### 模板渲染预览(Dry-Run)

**URL**: `/api/v1/render/render/template/{template_id}`

**Method**: `POST`

**Description**:

在下发前预览 Jinja2 模板渲染后的配置文本。

支持传入空参数或模拟设备上下文（从设备表中提取属性）进行 Dry-Run。

Args:
template_id (UUID): 配置模板 ID。
body (RenderRequest): 包含输入参数及可选设备上下文 ID 的请求。
template_service (TemplateService): 模板管理服务。
db (Session): 数据库会话。
device_crud (CRUDDevice): 设备 CRUD 抽象。
render_service (RenderService): 渲染逻辑核心服务。

Returns:
ResponseBase[RenderResponse]: 包含最终渲染出的配置字符串。

#### Requests Parameters (Query/Path)

| 参数名        | 位置   | 类型     | 必填 | 描述        | Default |
| :------------ | :----- | :------- | :--- | :---------- | :------ |
| `template_id` | `path` | `string` | 是   | Template Id |         |

#### Request Body (application/json)

| 参数名      | 类型     | 必填 | 描述                     |
| :---------- | :------- | :--- | :----------------------- |
| `params`    | `object` | 否   | 模板参数                 |
| `device_id` | `string` | 否   | 用于上下文的设备ID(可选) |

#### Responses

**Status Code**: `200` - Successful Response

Format: `application/json`

| 参数名    | 类型             | 必填 | 描述    |
| :-------- | :--------------- | :--- | :------ |
| `code`    | `integer`        | 否   | Code    |
| `message` | `string`         | 否   | Message |
| `data`    | `RenderResponse` | 否   |         |

**Status Code**: `422` - Validation Error

Format: `application/json`

| 参数名   | 类型                     | 必填 | 描述   |
| :------- | :----------------------- | :--- | :----- |
| `detail` | `Array[ValidationError]` | 否   | Detail |

---
