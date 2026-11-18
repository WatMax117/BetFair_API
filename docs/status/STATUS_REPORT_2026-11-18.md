# STATUS_REPORT_2026-11-18 — Действително състояние (REQ-STATUS-2026-11-18)

| | |
|---|---|
| ID | `REQ-STATUS-2026-11-18` |
| Дата на отчета | 2026-11-18 |
| Автор | агент `bc-0be83703-b7b5-5aad-a080-5d332369b9f1` |
| Режим | **Само четене**; без промени по код/VPS/DB |
| Repo checkout | `master` @ `39f8190` (`git rev-parse HEAD`) |

## Ограничения на доказателствата (прочетете първо)

| Източник | Резултат на 18.11 |
|---|---|
| SSH `root@158.220.83.195` | `Permission denied (publickey,password)` — команда: `ssh -o BatchMode=yes …` |
| Self-hosted worker | няма свързан (`cursor-cloud list-self-hosted-workers` → 0) |
| Live SQL към `netbet` / `ledger` | **недостъпно** |
| GitHub `master` | няма `docs/ARCHIVE_*`, `SPEC_V2_*`, `ledger/`, `archives/` |
| Дъщерни агенти `bc-162e75aa…`, `bc-9baa837a…` | batch-fetch **недоступни** |
| Координаторски transcript NetBet | последно съдържателно: **2026-10-31 ~10:13 Europe/Sofia** (архивен агент) |

**Правило в този файл:** твърдение без жива проверка на 18.11 → `[непроверено]` или изрично „последно известно 31.10 (архивен агент)“.

Работни извлечения (не са в репото):  
`/cursor/stores/bc-634c86b6-df9f-434b-8514-e3af5bbf20e8/internal/netbet-transcript-status-brief-2026-10-31.md`,  
`…/transcript-deep-extract-brv2-archive.md`,  
`…/betfair-api-code-inventory-2026-11-18.md`.

---

## 0. Спешно — диск VPS

### 0.1 Сега (18.11)

| Метрика | Стойност | Източник |
|---|---|---|
| Заето / свободно / % | **[непроверено на 18.11]** | SSH отказ |
| Ръст/ден последни 7 дни | **[непроверено на 18.11]** | няма `df` / inventory |
| Прогноза до 85% / 95% | **[непроверено на 18.11]** | — |

### 0.2 Последно известно (архивен агент, 2026-10-31)

| Метрика | Стойност | Източник |
|---|---|---|
| Диск | **80% / 39G free** (беше 76%/47G на 26.10) | worker `bc-162e75aa…` detail 31.10 05:48 |
| Наблюдаван ръст | **~1.6 GB/d** | същият; в `ARCHIVE_PROCEDURE` update 06:27 |
| Прогноза до 85% | **~6 дни** от 31.10 при 1.6 GB/d | 06:27 |
| Прогноза до 95% | **не е цитирана** в worker detail | priorities item 5 truncated |
| Extrapolation към 18.11 | ако темпото е останало ~1.6 GB/d и няма DROP → **вероятно >>85%** | **[непроверено]** — аритметика върху стара база, не `df` |

### 0.3 Освободено / изтрито след 31.10

| Действие | Статус | Одобрение |
|---|---|---|
| DROP `traded_volume_legacy` | **не е изпълнен** към 31.10 10:13; след това **[непроверено]** | чака A/B след Drive |
| Ladder APPLY (`ladder_levels_20260801`, ~412 MB) | **не е пуснат** към 31.10 | чака собственик |
| BRIN | **не е приложен** | чака одобрение |
| Вдигане `ARCHIVE_THROUGH_YMD` | остава **20261019** към 31.10 | забранено без изрично одобрение |
| Каквото и да е освобождаване след 31.10 | **[непроверено]** | няма transcript / SSH след тази дата |

---

## 1. Структура на базите и параметри

### 1.1 Бази — live на 18.11

| База | Достъп 18.11 | Бележка |
|---|---|---|
| `netbet` (VPS) | **недостъпна** | последно: ~89 GB (31.10) |
| `ledger` / ledger ingest (VPS) | **недостъпна** | последно: ~42 GB; `depth_delta` ~32 GB |
| `ledger_lab` | **недостъпна** | създадена в `netbet-pg-test` на 31.10; restore PASS |
| `netbet_test` | **[непроверено]** | името не се среща; има контейнер/хост `netbet-pg-test` |

Живи `pg_total_relation_size` / `n_live_tup` / `min`/`max` на 18.11: **няма**.

### 1.1b Последно известно (31.10, архивен агент) — ключови обекти

| Обект | Факт | Източник |
|---|---|---|
| `stream_ingest.traded_volume` | RANGE на `publish_time`; parent празен; live → дневни партиции | 05:48 |
| `traded_volume_legacy` | MINVALUE→2026-10-29; **279,382,662** rows; ~50 GB est; min `2026-02-16` max `2026-10-28`; `sum(size_traded)≈241570518721.76`; markets=39299 | 05:48 / 08:25 / 10:13 |
| Daily TV parts 29–31.10 | ~217 / 366 / 92 MB | 05:48 |
| `ladder_levels` | 121 parts; 27→29 GB; oldest **20260801** (~412 MB candidate) | 05:48 / 06:27 |
| Ledger tables @ `T_cut=2026-10-31T07:19:23Z` | `depth_delta` 208,505,457; `traded_cum` 63,437,596; `ltp` 9,177,947; `market_state` 3,381,768; `stream_meta` 2,179,771; `market` 18,233; `runner` 54,699; `settlement` 0 | 08:25 |
| `book_risk_v2_stream` | **0 parts** | 05:48 |
| Миграции V21/V22 на VPS | **[непроверено]** | не се споменават; в repo Flyway спира на **V11** |

### 1.1c Repo (код / Flyway) — не VPS

| | |
|---|---|
| Flyway файлове | `V1`…`V11` в `betfair-streaming-client/src/main/resources/db/migration/` |
| Последна написана | **V11** settlement (`V11__market_settlement_tables.sql`) |
| Написани, но неприложени V12+ | **няма в repo** |
| Compose baseline | `SPRING_FLYWAY_BASELINE_VERSION=5` (`docker-compose.yml`) — V1–V5 се пропускат при migrate |
| `ladder_levels.client_version` разпределение | **[непроверено на VPS]**; код default `1.0` (`application.yml:64`, `PostgresStreamEventSink`) |
| `legacy_cache` vs нова стойност | **[непроверено]** — няма в repo/transcript |

### 1.1d Таблици, изисквани от по-нови спецификации — в GitHub `master`

| Таблица | В repo SQL/Java/Python |
|---|---|
| `book_risk_v2_stream` / `_latest` | **липсва** (0 hits); на VPS спомената с 0 parts на 31.10 |
| `ladder_levels_virtual` | **липсва** |
| `market_backfill_progress` | **липсва** |
| `market_buckets` / `market_indicators` (като таблици) | **липсват** — buckets са read-time в API |

### 1.2 Палитра на параметрите

| Параметър | Къде (repo) | Lab | VPS | Значение | Статус |
|---|---|---|---|---|---|
| `betfair.ladder-levels` / `BETFAIR_LADDER_LEVELS` | `application.yml:31` | default **8** | **[непроверено]** env | нива в абонамента (clamp 1..10) | отворен (live) |
| `betfair.postgres-sink.ladder-levels` | **няма такъв ключ** | — | — | sink ползва `MAX_LEVEL=8` / `MarketCache.DEFAULT_LADDER_LEVELS` | — |
| `conflateMs` / `BETFAIR_CONFLATE_MS` | `application.yml:30` | default **0** | **[непроверено]** | conflation на stream | отворен (live) |
| `virtualise` | **ABSENT** в repo | — | **[непроверено]** | — | отворен / неимплементиран в master |
| Абонамент fields | `SubscriptionManager.java` | `EX_ALL_OFFERS, EX_TRADED_VOL, EX_TRADED, EX_LTP, EX_MARKET_DEF` | **[непроверено]** | | код |
| batch / limit / refresh | compose + yml | batch **177**, limit **0**, refresh **3 min**, subscribe-from-db **true** | **[непроверено]** | | |
| `betfair.book-risk-v2.*` | **ABSENT** | — | **[непроверено]** | | отворен |
| `betfair.postgres-sink.virtual-ladder.enabled` | **ABSENT** | — | — | | отворен |
| `betfair.postgres-sink.enabled` | yml default false; compose **true** | | **[непроверено]** | запис ladder/TV | |
| `client-version` | yml default **1.0** | | **[непроверено]** | колона provenance | |
| `KEEP_DAYS` | **ABSENT** в repo; в команда на архивен агент | — | подготвено **90** (не пускано) | ladder retention | чака APPLY |
| `ARCHIVE_THROUGH_YMD` | **ABSENT** в repo | — | **20261019** (31.10) | таван за archive/retention | отворен / ръчен |
| `LEDGER_ARCHIVE_THROUGH_YMD` | **ABSENT** | — | **[непроверено]** | | |
| `best_offers_l10_v1` / `best_offers_disp_l10_v1` | **ABSENT** | — | **[непроверено]** | ledger config versions | отворен |
| `calc_version` / `calculation_version` | REST `"v1"`; stream `"stream_15min"` / `_bulk` | | **[непроверено]** DB | | код |
| Alarm thresholds | `SPEC.md` lag 200/500/2000 ms; partition horizon 7d/2d | | **[непроверено]** | | частично в код |
| `DISK_WARN_PCT` | скрипт на VPS (цитиран) | — | **85** в prepared cmd | | |
| Purge / backup (repo) | `purge_partitions.sql` **30d**; `backup_db.sh` **7d** | | **[непроверено]** дали вървят | | |

---

## 2. Процедура по архивиране (3-2-1)

> Данните по-долу са от **агента по архивиране** `bc-162e75aa-b86a-4b37-8943-e68046e35b09` чрез координаторския transcript, последно **2026-10-31 10:13**. Файловете `docs/ARCHIVE_PROCEDURE.md`, `LEDGER_RESTORE_CHECK.md`, `archives/MANIFEST.tsv` **не са в GitHub master** — цитират се по имена от worker reports.

### 2.1 Копия по набор

| Набор | Copy1 (local) | Copy2 (външен диск) | Copy3 (Drive) | Дата | sha256 / rclone check |
|---|---|---|---|---|---|
| `traded_volume_20261029.bin.zst` | 3.09 MB; 1,208,108 rows; sha `DFB82634…DED01532` | **няма** | **блокиран** (rclone token empty) | 31.10 | `zstd -t` OK; rclone **не** |
| `traded_volume_20261030.bin.zst` | 5.09 MB; 1,987,827 rows; sha `55CE8796…18EA5C7A` | няма | блокиран | 31.10 | също |
| `traded_volume_legacy.bin.zst` | 703.45 MB; 279,382,662 rows; decomp ~21.51 GB; sha `8E90D7FD…9CCD4ED2` | няма | блокиран | 31.10 | също |
| Ledger base `archives/ledger/base_20261031T0719Z/` | ~2.08 GB zst; COPY\|zstd-3; MANIFEST copy1=ok | няма | блокиран | 31.10 `T_cut=07:19:23Z` | `zstd -t` OK |
| Ladder partitions archive | **[непроверено / не е докладвано като готово]** | — | — | — | — |
| Schema dumps | „написани under archives/“ | — | — | 31.10 | |

Допълнително (05:48): по-стари „two local dumps“ + `G:\My Drive\NetBet_archives` sizes match — **без** външен диск; на VPS тогава няма rclone/zstd/rsync в PATH (локално инсталирани zstd 1.5.7 + rclone 1.75.1 на 31.10).

### 2.2 Тестове за възстановяване

| Тест | Контрол | Резултат | Doc (име) |
|---|---|---|---|
| Ledger → `ledger_lab` | rows, min/max pt, markets exact; float sums ≈ vs VPS snapshot | **PASS** | `docs/LEDGER_RESTORE_CHECK.md` |
| `traded_volume_legacy` → lab `…_restore` | 279,382,662 MATCH; sum/markets/min-max MATCH | **PASS** | worker 10:13 |
| Пълни SHA в transcript | — | само съкратени | |

Забележка: lab schema трябва от VPS `pg_dump` schema (column order), не само `ledger/sql/init`.

### 2.3 `archives/MANIFEST.tsv`

| | |
|---|---|
| Съдържание / последни редове | **не са в transcript** — само „Manifest written“ / `copy1=ok` |
| Пропуски | Copy2/Copy3 колони вероятно празни; **[непроверено]** пълен файл |
| `archives/STATUS_2026-10-31.txt` | обновен според worker; **не в git** |

### 2.4 Автоматизация

| Елемент | Статус |
|---|---|
| Retention cron на VPS | „present“ (31.10) — **без crontab dump** |
| `forecast_headroom.sh` | **липсва на VPS** (31.10) |
| ANALYZE cron | споменат при завършване на partition deploy (`bc-47255e21…`) — **[детайл непроверен]** |
| Telegram / ntfy | **0 споменавания** в transcript |
| Последен успешен прогон на archive scripts | ръчни стъпки 31.10; schedule **[непроверено]** |

### 2.5 `TASK_ARCHIVE_LEDGER_AND_SPACE` §1–§5

Име на задачата в transcript = приоритети/§1–§3 на архивния агент (пълният TASK файл **не е в git**).

| Стъпка (по worker 10:13) | Статус |
|---|---|
| §1 Ledger base archive + restore | **готово** (Copy1); Copy3 чака OAuth |
| §2 traded_volume_legacy archive + lab restore | **готово** (Copy1+lab); DROP **чака одобрение** |
| §3 docs/plans (ARCHIVE_PROCEDURE, LEDGER_RETENTION…, STATUS) | **готово** локално; **не в git master** |
| Ladder APPLY / BRIN | **чака одобрение** |
| Drive / rclone copy3 | **блокиран** |
| Copy2 външен диск | **не е започнато** / липсва носител |
| Вдигане `ARCHIVE_THROUGH` / DROP | **чака одобрение** |

### 2.6 Решения, които чакат собственика

| Решение | Варианти / последствия |
|---|---|
| rclone OAuth | без него няма Copy3 → няма безопасен DROP |
| DROP A vs B (`TRADED_VOLUME_LEGACY_DROP_OPTIONS`) | **A:** DROP след Drive → ~50 GB free; UI volume празни преди 29.10. **B:** Stage3 ~90d daily parts, после DROP |
| Ladder APPLY `20260801` | ~412 MB; `KEEP_DAYS=90` |
| BRIN на ledger | план готов; не приложен |
| Copy2 disk | без него 3-2-1 е непълен |
| Capture NB-4 review | преди C5/C6 |
| SSH ключ / local worker за този Project | без него live статус остава невалидиран |

---

## 3. Актуална логика на индексите (по кода в `master` @ 39f8190)

### 3.1 „v1“ — buckets / indicators

| | Реалност в кода |
|---|---|
| Таблици `market_buckets` / `market_indicators` | **няма** |
| Какво смята | 15-min buckets **на четене** в `risk-analytics-ui/api/app/stream_data.py` |
| Книга | `stream_ingest.ladder_levels`, `side='B'`, `level=0` → time-weighted median odds/size |
| Book risk на stream | `compute_book_risk_from_medians` → `*_book_risk_l3` полета; `calculation_version` = `stream_15min` / `stream_15min_bulk` |
| REST Book Risk L3 | `betfair-rest-client/risk.py` `compute_book_risk_l3`; запис в `public.market_derived_metrics` с `calculation_version: "v1"` |
| Променяна ли е | последната логика е median-only stream path (`docs/BOOK_RISK_MEDIAN_ONLY_IMPLEMENTATION.md`, 2026-02-16) |

### 3.2 Book Risk v2

| Елемент | Статус |
|---|---|
| Java/Python/SQL класове `BookRiskV2*` | **ABSENT** в repo |
| `calc_version` v2 | **ABSENT** |
| Флагове `betfair.book-risk-v2.*` | **ABSENT** |
| Книга (реална/виртуална/`legacy_cache`) | в master: само реален ladder sink; virtual **ABSENT** |
| На живо | таблица `book_risk_v2_stream` на VPS: **0 parts** (31.10); имплементация в git: **няма** |
| Ф1–Ф5 | **не фигурират** в transcript/repo → статус **[непроверено / вероятно не стартирани в master]** |

### 3.3 Разлики спрямо `SPEC_V2_BOOK_RISK_STREAM` 1.1 и `SPEC_STREAM_CAPTURE_FIX` 1.1

Спецификациите **не са в GitHub master** → пълен diff **невъзможен**. От transcript:

| Отклонение / факт | Защо / бележка |
|---|---|
| Production `ladder_levels` „замърсена“ (реални+виртуални) | claim в user assignment; източник `SPEC_STREAM_CAPTURE_FIX` §6 — **[непроверено независимо]** |
| Чиста реална книга = `ledger_ingest` от 09.08.2026 (~208M rows, 42 GB) | същият assignment |
| Capture worker | C0–C4 **локално готови**, чакат review преди C5/C6 (`bc-9baa837a…`) |
| Repo master | няма dual-book / virtual ladder / capture-fix code paths под тези имена |

### 3.4 Тестове §9.1–9.7 (v2) и §5.1–5.4 (capture fix)

| | |
|---|---|
| Последен прогон / pass-fail | **няма данни** в достъпните източници |
| Маркиране | **[непроверено]** |

### 3.5 Етапи

| Етап | Статус | Блокер |
|---|---|---|
| BRV2 Ф1–Ф5 | **[непроверено]** / липсват в master | няма SPEC/код в git; VPS stream 0 parts |
| CAP С0–С4 | **готово локално** (координатор 31.10) | review |
| CAP С5–С6 | **не започнати** | чака review |
| CAP С7 | **не споменат** | — |

### 3.6 Какво показват данните досега

| Метрика | Стойност |
|---|---|
| Дял кръстосана книга след поправка | **[непроверено]** |
| Покритие backfill v2 | **[непроверено]**; `book_risk_v2_stream` = 0 parts на 31.10 |
| Анализ Ф3 | **[непроверено]** |

### 3.7 Отворени въпроси

1. Жив `df` и DB inventory на 18.11 (нужен SSH или local worker).  
2. Къде живеят `SPEC_V2_*`, `ARCHIVE_*`, `ledger/`, `archives/` — само на локалната машина / VPS, не в git?  
3. Какво е реалното `client_version` / dual-book съдържание в `ladder_levels` след 09.08?  
4. Приложен ли е някой DROP/APPLY между 01.11 и 18.11?  
5. Какво точно доставят C0–C4 (код/PR) преди C5?

---

## 4. Документи и промптове

### 4.1 Активни идентификатори (предложение — без преименуване на файлове)

| ID | Съдържание | Файл / артефакт (ако съществува) |
|---|---|---|
| `BRV2-Ф1`…`BRV2-Ф5` | етапи Book Risk v2 | `SPEC_V2_BOOK_RISK_STREAM` — **не в git** |
| `CAP-С0`…`CAP-С7` | stream capture fix | `docs/SPEC_STREAM_CAPTURE_FIX.md` — **не в git**; NB-4 |
| `CAP-С0-RPT` | C0 disk/ledger report | `docs/C0_CAPTURE_DISK_LEDGER_REPORT.md` — **не в git** |
| `ARC-§1` | Ledger base 3-2-1 | `archives/ledger/base_20261031T0719Z/` |
| `ARC-§2` | traded_volume legacy archive + DROP options | `TRADED_VOLUME_LEGACY_DROP_OPTIONS.md` |
| `ARC-§3` | процедура / MANIFEST / STATUS | `ARCHIVE_PROCEDURE.md`, `MANIFEST.tsv`, `STATUS_2026-10-31.txt` |
| `ARC-§4` | BRIN + ledger partition plan | `LEDGER_RETENTION_AND_PARTITION_PLAN.md` |
| `ARC-§5` | Ladder retention APPLY | `vps_disk_and_ladder_retention.sh` |
| `BR-L3` | текущ Book Risk L3 в master | `betfair-rest-client/BOOK_RISK_L3_SPEC.md` |
| `STR-SPEC` | streaming client | `betfair-streaming-client/SPEC.md` |
| `RET-MAT` | retention matrix | `docs/RETENTION_MATRIX.md` |
| `STS-2026-11-18` | този отчет | `docs/status/STATUS_REPORT_2026-11-18.md` |

### 4.2 Документи в GitHub `master` (сбито)

Общо **137** `.md` файла (`find` + `git log -1`). Няма версия в frontmatter за повечето → колона „версия“ = **—**. Статус: **актуален спрямо master**, освен ако е заменен от по-нов deploy/report със същата тема.

Пълен списък с последна commit дата: генериран при този прогон (`git log -1 --format=%ci -- <path>`). Високосигнални:

| Път | Заглавие | Версия | Последна промяна (git) | Статус |
|---|---|---|---|---|
| `betfair-streaming-client/SPEC.md` | Master Technical Specification… | — | 2026-02-05 | актуален (stream client) |
| `betfair-streaming-client/PROJECT_STATUS.md` | Project Status | — | 2026-02-05 | архивен спрямо 2026 ops |
| `betfair-rest-client/BOOK_RISK_L3_SPEC.md` | 3-way Book Risk L3 | — | 2026-02-14 | актуален за L3 v1 |
| `docs/BOOK_RISK_MEDIAN_ONLY_IMPLEMENTATION.md` | Book Risk from medians | — | 2026-02-16 | актуален за stream path |
| `docs/RETENTION_MATRIX.md` | Data retention matrix | — | 2026-02-19 | частично остарял vs 31.10 archive |
| `docs/SETTLEMENT_V11_VERIFY_AND_DEPLOY.md` | Settlement V11 | — | 2026-02-28 | актуален |
| `docs/status/STATUS_REPORT_2026-11-18.md` | този отчет | 2026-11-18 | 2026-11-18 | актуален |
| `docs/ARCHIVE_PROCEDURE.md` и др. от §2 | — | — | **липсват в git** | само локално при архивен агент |

Останалите ~130 md: deploy/diagnosis/UI/stream audit от февруари 2026 — третирай като **архивни отчети**, освен ако собственикът ги ползва като runbook.

### 4.3 `git log --oneline -20` (към прогона)

```
39f8190 docs: add settlement V11 verify-and-deploy runbook (DB, Flyway, manual apply)
ef9347a chore(flyway): track V10 and V11 migrations so JAR includes settlement tables
0b00373 chore: add settlement date-range script and V11 apply runbook for VPS
2baa506 fix(ui): always show Result line below event title
52972e7 fix(ui): show Result line and settlement logging; normalize selection_id in API
e0efcbd fix(api): include 15-min buckets that have ticks only inside bucket
fefa843 fix(api): make event meta settlement query optional; avoid 500 if table missing
b893aed feat(ui): event header winner/tie coloring; API returns runner settlement status
a4710cd fix(ui): accordion sort by event count desc, then competition name A-Z
59e0db5 fix(ui): Tick Audit left-align; bucket buttons fixed width, pale blue when has data
f4f9fe0 fix(ui): Tick Audit - one column per time, merge API rows by publish_time
fdb2400 fix(ui): Tick Audit View - rows Home/Away/Draw, columns publish_time
23d9d4d fix(ui): nginx serve /fonts/ as static; copy DSEG7 in postinstall
ff3cf3c ui: apply DSEG7 Modern Mini Bold Italic to calLine and FHRH
3be7ad6 Remove 200 cap: discovery sync full desired set, streaming client subscribes to all active_markets_to_stream
9d580b4 Add copy-dseg14-font.js for UI web postinstall
d47cebf Add risk-analytics-ui web scripts dir for Dockerfile COPY
13c18f1 Fix UI build: align ExpandedEventsPage API exports and explicit types
f10786c Normalize line endings to LF for Unix-executed files
a36f377 Enforce LF line endings: add .gitattributes and LINE_ENDINGS doc
```

### 4.4 `git status` (преди commit на отчета)

Преди добавяне на този файл: `On branch master` / clean / up to date. След работа: branch `cursor/status-report-2026-11-18-b9f1` + този файл.

### 4.5 Project tracker (`notes.md`)

| Task | Статус |
|---|---|
| NB-1 Archive 3-2-1 | For Review |
| NB-4 Dual-book capture C0–C4 | For Review |
| NB-5 Status 18.11 | In Progress (този агент) |
| NB-2 / NB-3 | Done |

---

## 5. Резюме за собственика

1. **Жив VPS статус на 18.11 не може да се измери** от този агент (няма SSH ключ / local worker).  
2. Към **31.10** дискът е бил **80%/39G**, ръст **~1.6 GB/d**, ~6 дни до 85% — без одобрени DROP/APPLY дотогава; 18 дни по-късно рискът от пълен диск е **висок, но непроверен**.  
3. **3-2-1:** Copy1 + lab restore PASS; Copy2 липсва; Copy3 блокиран на rclone OAuth.  
4. **Индекси в git:** Book Risk L3 + stream medians; **няма** Book Risk v2 имплементация; capture C0–C4 чака review.  
5. Много ops документи от октомври **не са в GitHub** — само в локалния архивен workflow.

---

*Край на отчета. Без пароли/токени. За пълни live числа: прикачете SSH ключ или стартирайте self-hosted worker, после поискайте refresh на §0–§1.*
