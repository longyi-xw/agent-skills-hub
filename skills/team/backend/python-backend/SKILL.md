---
name: python-backend
description: Python 服务端与数据处理代码的开发规范。当用户要求「写个接口」「加个 API」「FastAPI/Flask/Django 相关改动」「写爬虫」「处理数据/写入数据库」「加个异步任务/定时任务」「优化这段 Python 性能」，或在 Python 项目中新增业务逻辑、数据模型、外部调用时，使用本技能。覆盖项目约定探测、依赖与虚拟环境、类型与错误处理、I/O 与并发选型、数据库访问、配置与密钥、日志与测试。Use this skill for any Python backend, API, scraper, data pipeline, or service-side implementation work.
category: backend
tags: [python, backend, api, fastapi, asyncio, database]
status: verified
summary: Python 服务端：接口分层、同步/异步选型、DB、密钥、日志
---

# Python 后端开发

## 何时使用本技能

- 新增 / 修改 HTTP 接口、后台任务、定时任务
- 数据抓取、清洗、入库
- 数据库模型与查询
- Python 侧性能或稳定性问题

## 第一步永远是探测项目约定

动手前先花 60 秒把这些搞清楚，照着现有的写，不要带入个人偏好：

```
依赖管理    pyproject.toml / requirements.txt / uv.lock / poetry.lock
运行方式    Makefile、scripts/、README 的启动命令
Web 框架    FastAPI / Flask / Django / 无
同步还是异步  搜索 `async def` 的占比 —— 决定你写哪一种
ORM        SQLAlchemy / Django ORM / 裸 SQL / asyncpg
配置        .env / pydantic-settings / config.py
测试        pytest / unittest，测试放哪、怎么跑
日志        logging / loguru / structlog
```

**绝不**在已有虚拟环境的项目里 `pip install` 到全局；用项目自己的 venv / uv / poetry。

## 执行流程

### 1. 接口层

- 入参出参用 Pydantic model（FastAPI）或 serializer（Django），不裸收 `dict`
- 校验失败返回 4xx 且带可读信息；不要把校验塞进业务函数
- 业务逻辑不写在路由函数里，路由只做「解析 → 调 service → 组装响应」
- 幂等性：写接口要么天然幂等，要么接受幂等键

### 2. 同步 / 异步选型

一个进程内不要混用两套 I/O 模型。

| 场景 | 选择 |
|---|---|
| 框架本身是 async（FastAPI） | 全链路 async，DB 用 async 驱动 |
| 大量外部 HTTP 调用 | `asyncio` + `httpx.AsyncClient`，用 `gather` 并发 |
| CPU 密集（解析、加解密、压缩） | `ProcessPoolExecutor`，不要用 asyncio |
| 已有同步代码库 | 保持同步 + 线程池，不要为一个函数把整条链路改异步 |

在 async 函数里调用阻塞库（requests、time.sleep、同步 DB）会卡死整个事件循环——用 `asyncio.to_thread` 包一层。

### 3. 外部调用

- 每个外部请求都要有 **timeout**，没有 timeout 的请求迟早挂住整个服务
- 复用连接：`httpx.Client` / `requests.Session` 做成模块级或依赖注入，不要每次新建
- 重试只对幂等操作做，用指数退避 + 上限；对 4xx 不重试
- 第三方返回的结构一律当作不可信，取字段用 `.get()` 或先校验

### 4. 数据库

- 查询写在 repository / dao 层，不散落在路由里
- N+1 是默认会犯的错：关联数据用 `selectinload` / `select_related` 显式预加载
- 写操作放在显式事务里；跨表写必须同事务
- 迁移用工具（Alembic / Django migrations）生成，不手改线上表
- 分页必须有上限，`limit` 不接受用户传入的任意大值

### 5. 配置与密钥

- 密钥、token、连接串只从环境变量或密钥管理读，**绝不写进代码或提交进 git**
- 配置集中在一个 settings 对象，不在业务代码里散读 `os.environ`
- 本地用 `.env`，且 `.env` 必须在 `.gitignore` 里

### 6. 错误处理与日志

```python
# 不要这样
try:
    do_work()
except Exception:
    pass

# 要这样
try:
    do_work()
except SomeSpecificError as exc:
    logger.warning("处理失败 order_id=%s: %s", order_id, exc)
    raise ServiceError("订单处理失败") from exc
```

- 只捕获你能处理的异常类型；捕获后要么恢复、要么带上下文重抛
- 日志带业务标识（订单号、用户 id），不带密钥与完整身份证/手机号
- 用 `logging` 的懒格式化（`%s` 参数）而不是 f-string，避免无谓开销

### 7. 类型与测试

- 新代码写类型注解；对外函数的参数与返回值必须有
- 测试用 pytest：至少覆盖正常路径 + 一个边界 + 一个失败路径
- 外部依赖在测试里替身掉，不打真实网络

## 自测清单

- [ ] 按项目原有方式跑通了（`make dev` / `uvicorn ...` / `pytest`）
- [ ] 新增依赖已写进依赖文件
- [ ] 所有外部请求都有 timeout
- [ ] 没有裸 `except:` 或空 `except`
- [ ] 没有硬编码密钥、没有 `print` 调试残留
- [ ] 数据库查询检查过 N+1
- [ ] 涉及用户输入的地方检查过注入与越权（详见 `security-audit`）

## 反面案例

| 不要这样 | 要这样 |
|---|---|
| `requests.get(url)` | `client.get(url, timeout=10)` |
| 路由函数里 100 行业务 | 路由 → service → repository |
| `except Exception: pass` | 捕获具体异常并带上下文重抛 |
| async 函数里 `time.sleep(1)` | `await asyncio.sleep(1)` |
| 循环里逐条查库 | 预加载或批量查询 |
| `API_KEY = "sk-..."` | `settings.api_key`（来自环境变量） |
