# NVP 记忆服务器 · 部署与运维手册

让 `novel-video-pipeline` 技能随使用**自我生长**的轻量后端。纯标准库、零依赖、单文件服务，
可跑在一台小服务器（1 CPU / 512MB 即可）。与 skill 本体解耦，可公网部署。

---

## 1. 架构

```
 skill 跑完产线
      │  scripts/collect.py  (POST /ingest)
      ▼
┌─────────────────────────────────────┐
│  NVP 记忆服务器 (memory_server)      │
│  ThreadingHTTPServer + SQLite        │
│  表: productions / feedback /        │
│      failures / priors              │
└─────────────────────────────────────┘
      │  cron: memory_server/growth.py
      ▼
 snapshot/learnings.json  +  priors 表
      │  scripts/load_learnings.py  (GET /snapshot)
      ▼
 skill 侧 .cache/learnings.json
      │  build_storyboard.py 读取
      ▼
 下次生成时提前规避高频失败模式
```

闭环：**采集 → 聚合 → 回灌**。

---

## 2. 本地快速试跑（无需 token）

```bash
cd memory_server
python server.py --no-auth --port 8080
# 另开终端
python growth.py
python ../scripts/collect.py --project /path/to/project --platform bilibili --url http://127.0.0.1:8080
python ../scripts/load_learnings.py --url http://127.0.0.1:8080
```

---

## 3. 公网部署（推荐 Caddy 反向代理做 TLS）

服务本身只跑 HTTP；TLS 交给 Caddy（自动申请/续期 Let's Encrypt 证书）。

### 3.1 配置 token 与启动

```bash
cd /opt/novel-video-pipeline/memory_server
cp .env.example .env
# 编辑 .env，设 NVP_API_TOKEN 为一个长随机串（与 skill 侧一致）
python server.py --host 127.0.0.1 --port 8080
```

> 不设置 token 且不用 `--no-auth` 时，服务会**拒绝所有请求**（安全默认），避免误开裸服务。

### 3.2 Caddyfile（HTTPS 反代）

```Caddyfile
memory.your-domain.com {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
caddy reload
```

Caddy 自动签发证书。skill 侧把 `NVP_MEMORY_URL` 设为 `https://memory.your-domain.com`、
`NVP_API_TOKEN` 设为同一串即可。

### 3.3 systemd 守护（可选）

`/etc/systemd/system/nvp-memory.service`：

```ini
[Unit]
Description=NVP self-growth memory server
After=network.target

[Service]
WorkingDirectory=/opt/novel-video-pipeline/memory_server
EnvironmentFile=/opt/novel-video-pipeline/memory_server/.env
ExecStart=/usr/bin/python3 server.py --host 127.0.0.1 --port 8080
Restart=on-failure
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now nvp-memory
```

### 3.4 定时聚合（cron 每小时）

```cron
0 * * * *  cd /opt/novel-video-pipeline/memory_server && /usr/bin/python3 growth.py >> /var/log/nvp-growth.log 2>&1
```

---

## 4. 数据模型

| 表 | 用途 | 关键字段 |
|----|------|----------|
| `productions` | 每次运行客观指标 | run_id, project, platform, beats, shots, resolved_refs, unresolved_refs, duration_sec |
| `feedback` | 人类评分 | run_id, rating(1-5), aspect, comment |
| `failures` | 失败日志 | run_id, stage, error_type, message, fingerprint |
| `priors` | 风格/知识先验（key 唯一，带 weight） | key, value, weight, source, updated_at |

---

## 5. HTTP 端点

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 否 |
| POST | `/ingest` | body `{"events":[...]}`，批量写入 | 是 |
| GET | `/query?type=failures\|feedback\|productions\|priors` | 聚合查询 | 是 |
| GET | `/snapshot` | 返回最新 `snapshot/learnings.json` | 是 |
| GET | `/export` | 导出全量数据（离线镜像/备份） | 是 |

event `type` 取值：`production` / `feedback` / `failure` / `prior`。

---

## 6. 备份与迁移

- SQLite 文件位于 `memory_server/data/nvp_memory.db`（含 WAL）。整库复制即备份。
- `GET /export` 可导出 JSON 全量，便于离线镜像或换机迁移。
- `snapshot/learnings.json` 由 `growth.py` 生成，属派生数据，不入库。

---

## 7. 安全提醒

- **token 一旦写入过脚本/聊天记录，视为已暴露**，应在 GitHub / 服务器后台轮换（重新生成并设置新 `NVP_API_TOKEN`）。
- 公网务必走 HTTPS（Caddy），**切勿**把 `--no-auth` 用于公网。
- SQLite 单文件并发写足够本场景（小时级写入量）；如未来写入量激增，可换 Postgres（改 `server.py` 连接层）。
