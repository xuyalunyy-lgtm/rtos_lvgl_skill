# Field Experience Log

This file records production incidents, anti-patterns, and reusable fix patterns discovered during reviews or device bring-up. Keep newest entries first. Each entry should be searchable by platform, symptom, root cause, and constraint ID.

## Entry Template

```markdown
### YYYY-MM-DD - Short title
- **Source:** field log / user report / CI / production
- **Platform:** esp32 | stm32 | jl | bk | zephyr | generic
- **Symptom:** one-sentence observable behavior
- **Root cause:** generalizable cause
- **Fix pattern:** reusable fix approach
- **Constraint mapping:** C#.# list
- **Frequency:** low | medium | high
- **Impact:** P0 | P1 | P2
```

---

### 2026-07-07 - JL LVGL audio page plays but UI advances or freezes

- **Source:** AC792/WL83 field logs during healing-audio page debugging.
- **Platform:** jl
- **Symptom:** The healing audio file starts in the low-level player, but the LVGL page immediately advances on click, or the page stays busy/frozen while the device remains alive.
- **Root cause:** Media business state was not tied to both low-level player state and UI navigation completion. Unknown stream events were treated as STOP/ERROR, or busy state was cleared before async UI navigation actually finished.
- **Fix pattern:** Use an explicit `IDLE -> STARTING -> PLAYING -> UI_NAV_PENDING -> IDLE` state machine. Unknown stream events are diagnostics, not business errors. `is_playing()` must check both business state and low-level player status. Clear busy state only from the UI task after navigation returns.
- **Required logs:** `audio start request accepted`, `audio playback observed running`, `audio done, nav next requested`, `ui nav/reload entered`, `ui nav/reload returned`, `audio ui nav done`, `click ignored during audio/transition`.
- **Constraint mapping:** C1.1, C24.1, C25.4, C31.3, C33.1, C36.1, C43.5
- **Frequency:** high
- **Impact:** P0

### 2026-07-07 - JL LVGL full-page switch remains 1 FPS after visual assets are correct

- **Source:** AC792/WL83 HOME/PUSH/Schedule page-switch tests.
- **Platform:** jl
- **Symptom:** UI assets display correctly, but full-page transitions remain around 1-2 FPS.
- **Root cause:** Page switching repeatedly decodes large JPEG backgrounds/cards and recreates large object trees from touch callbacks. Page object caching alone does not prevent file-image decode cache eviction.
- **Fix pattern:** Route all BG/ICON access through the common resource layer; cache shared backgrounds and small icon descriptors separately; keep current and adjacent pages when RAM permits; touch callbacks only post navigation and return.
- **Required logs:** `page transition begin/end`, `page cache hit/store/evict`, `asset bg decode begin/end`, `asset bg reuse`, `click ignored during guard`.
- **Constraint mapping:** C1.1, C7.12, C23.6, C25.4, C33.1, C36.1
- **Frequency:** high
- **Impact:** P1

### 2026-07-07 - JL LVGL TF resources and local media lifecycle interact badly

- **Source:** AC792/WL83 display field logs involving HOME/PUSH pages, TF image resources, video, and audio playback.
- **Platform:** jl
- **Symptom:** Page switching is slow, PNG/JPEG resources sometimes disappear, video playback can reboot after the second run, and an audio page can be clicked away while audio is still playing.
- **Root cause:** Several lifecycle boundaries were mixed: pages were created as screens and then reparented, shared backgrounds were not restored for cached pages, large JPEGs fought for LVGL image cache, and low-level `STREAM_EVENT_NONE` was mapped to a business error.
- **Fix pattern:** Page factories receive `content_layer` and create normal child objects only. Shared backgrounds record path/fallback and restore on cached page show. Large resources go through lazy common loading. Media state uses `PLAYING -> UI_NAV_PENDING -> IDLE`; unknown stream events do not force ERROR.
- **Constraint mapping:** C1.1, C1.2, C13.1, C25.3, C25.4, C31.3, C33.1, C34.1, C36.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-07 - JL video-end async page navigation is reentrant

- **Source:** AC792/WL83 video playback completion followed by page switch/reboot debugging.
- **Platform:** jl
- **Symptom:** Video plays, but after playback ends and the app switches to the next LVGL page, the device may reboot, touch may stop working, or old title/components are duplicated.
- **Root cause:** The video task treated playback completion as UI navigation completion. Busy/playing flags were cleared before the async UI RPC or LVGL task truly returned, allowing touch/back/replay to reenter page creation or object deletion.
- **Fix pattern:** Use `IDLE -> PLAYING -> UI_NAV_PENDING -> IDLE`. Media completion requests navigation and enters `UI_NAV_PENDING`; only the UI task clears to `IDLE` after `ui_main_reset_to_next_page()` or reload returns.
- **Constraint mapping:** C1.1, C24.1, C31.3, C33.1, C36.1, C43.5
- **Frequency:** high
- **Impact:** P0

### 2026-07-07 - JL fb0 close/reopen during video overlay causes display lifecycle fault

- **Source:** AC792/WL83 video playback completion followed by `fb0` reopen failure and hmem access exception.
- **Platform:** jl
- **Symptom:** Video plays on a separate framebuffer/layer, then returning to LVGL triggers low FPS, a missing page, `fb0 open failed`, or reboot after display restore.
- **Root cause:** Short video playback suspended LVGL and closed/reopened the LVGL framebuffer (`fb0`). On JL display combine/layer paths this creates a race between LVGL flush, display driver reopen, and video layer teardown.
- **Fix pattern:** Keep LVGL and `fb0` alive for short overlay playback. Put video on a dedicated top layer/framebuffer such as `fb4`, force z-order above LVGL, and request UI reload/navigation through the UI task after playback ends.
- **Constraint mapping:** C1.1, C23.6, C24.1, C25.4, C31.3, C33.1
- **Frequency:** medium
- **Impact:** P0

### 2026-07-03 - BK large TF binfont amplifies WSS disconnect assert

- **Source:** BK7258 app_palette field reboot after replacing a TF Chinese font.
- **Platform:** bk
- **Symptom:** Replacing a 270 KB `my_font_16.bin` with a 2.3 MB font causes WiFi disconnect/WSS disconnect and then FreeRTOS `Assert at: xTaskPriorityDisinherit`.
- **Root cause:** LVGL binfont metadata/bitmaps consume runtime heap/PSRAM. Lower memory headroom exposes a WebSocket destroy/free lifecycle race while an application mutex is held.
- **Fix pattern:** Stat external UI resource size before loading and enforce a Kconfig limit. Log heap/PSRAM before and after load. Keep WSS RX/TX buffers sized to protocol need. Detach stale clients under lock, then call blocking SDK destroy outside the lock.
- **Constraint mapping:** C7.12, C20.5, C31.3, C33.1, C38.1, C43.1
- **Frequency:** medium
- **Impact:** P0

### 2026-07-03 - BK restoring STA power save after recording stop triggers IPC reboot

- **Source:** BK7258 app_palette recording-stop reboot logs.
- **Platform:** bk
- **Symptom:** About 8 seconds after `CLIENT_AUDIO_FINISH`, logs show `IPC heartbeat timeout` and `Assert at: mb_ipc_task:275` without HardFault.
- **Root cause:** Recording stop immediately calls `bk_wifi_sta_pm_enable()`, switching WiFi/audio/IPC cross-core state while CPU1 heartbeat stalls until the 8 second WDT expires.
- **Fix pattern:** Disable STA power save during capture, but do not restore it at capture stop. Keep voice/read handle in gated idle and restore PM only during deinit or a validated safe window.
- **Constraint mapping:** C8.3, C20.1, C24.4, C31.3, C33.1, C38.4
- **Frequency:** medium
- **Impact:** P0

### 2026-07-02 - WSS async task touches client after destroy

- **Source:** BK7258 app_palette reboot and pre-submit review.
- **Platform:** bk
- **Symptom:** WiFi disconnect, voice subsystem stop, or WSS reconnect can cause reboot, heap exception, or stale event handling.
- **Root cause:** WebSocket SDK tasks still run while the client/config is destroyed or freed. Callbacks lack current-client/generation filtering, and task ownership boundaries are unclear.
- **Fix pattern:** Give each WSS client explicit state/generation. Destroy first marks disconnecting and aborts/closes fd to wake tasks, then waits boundedly for task exit. Only one path frees client/config; callbacks drop stale generations.
- **Constraint mapping:** C24.1, C31.3, C33.1, C36.1, C43.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-02 - TTS/speaker hot path lacks pool guard and interruptible backpressure

- **Source:** BK7258 app_palette audio pipeline reboot.
- **Platform:** bk
- **Symptom:** Multiple TTS rounds, interruption, or speaker stop can lead to random reboot, payload/PCM overrun, or delayed stop.
- **Root cause:** Queue payload ownership and pool slot lifecycle are weak. Variable-length payload/PCM lacks head/tail guards. The speaker write hot path holds locks while calling blocking lower-level APIs.
- **Fix pattern:** Use fixed pool slots with head/tail canaries; verify before enqueue, dequeue, and free. Track queued/played/dropped/backpressure/high-water. Speaker writes use generation interrupt, short timeout locks, and bounded retry.
- **Constraint mapping:** C2.1, C31.1, C33.1, C43.5, C44.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-02 - LVGL deinit API exists but target config does not link it

- **Source:** BK7258 app_palette pre-submit build.
- **Platform:** bk
- **Symptom:** Calling `lv_deinit()` to make lifecycle symmetric fails to link with `undefined reference to lv_mem_deinit`.
- **Root cause:** LVGL headers expose `lv_deinit()`, but current `LV_USE_STDLIB_MALLOC=LV_STDLIB_CUSTOM` does not provide the required memory backend deinit implementation.
- **Fix pattern:** Global LVGL deinit must be link-verified in the target project. If the backend is incomplete, delete app displays/objects and stop platform display drivers instead of forcing an unclosed SDK API.
- **Constraint mapping:** C1.2, C24.1, C36.1, C39.1
- **Frequency:** medium
- **Impact:** P1

### 2026-07-02 - Kconfig secret overlay boundary is unclear

- **Source:** BK7258 app_palette secret scan and build scripts.
- **Platform:** generic
- **Symptom:** Secret scan reports both tracked `config` and local ignored `config.secrets` keys.
- **Root cause:** Real credentials had previously landed in tracked Kconfig, while the local overlay is intentionally ignored but still scanned by default.
- **Fix pattern:** Tracked `config` keeps sensitive Kconfig values empty. Real values live only in ignored `config.secrets`, applied by build scripts as a temporary overlay and restored afterward. Pre-submit checks include `git check-ignore`, `git ls-files`, and staged diff review.
- **Constraint mapping:** C9.1, C9.6, C36.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-01 - OTA rollback after power loss fails

- **Source:** Production OTA power-loss incident.
- **Platform:** esp32
- **Symptom:** Device loses power after OTA, then boots into faulty new firmware and cannot roll back.
- **Root cause:** Health check and `esp_ota_mark_app_valid_cancel_rollback()` were not used correctly, so bootloader state did not preserve a reliable rollback path.
- **Fix pattern:** On first boot after OTA, run a bounded health check; mark app valid only after required peripherals/network/storage checks pass.
- **Constraint mapping:** C22.2
- **Frequency:** high
- **Impact:** P0

### 2026-07-01 - Audio interruption leaves MIC invalid

- **Source:** BK7258 AI alarm clock TTS interruption.
- **Platform:** bk
- **Symptom:** After user interrupts TTS, ASR no longer receives microphone data.
- **Root cause:** Speaker stop deinitialized a shared audio backend also used by capture.
- **Fix pattern:** Separate idle from deinit. Stopping playback only enters playback idle; shared backend release is reserved for full audio subsystem teardown.
- **Constraint mapping:** C24.4, C10.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-01 - LVGL cross-thread HardFault

- **Source:** WSS callback directly calling `lv_label_set_text`.
- **Platform:** generic
- **Symptom:** Network message arrival occasionally causes HardFault or screen corruption.
- **Root cause:** Non-UI task calls LVGL APIs directly without LVGL task serialization.
- **Fix pattern:** Use `lv_async_call` or Queue -> Presenter -> View. Only the LVGL/UI task mutates LVGL objects.
- **Constraint mapping:** C1.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-01 - cJSON leak exhausts heap

- **Source:** WSS JSON parsing with early return.
- **Platform:** generic
- **Symptom:** Device runs for hours and then malloc fails.
- **Root cause:** Error paths return after `cJSON_Parse()` without `cJSON_Delete()`.
- **Fix pattern:** Use a single cleanup label or ownership wrapper so every parsed object is deleted exactly once.
- **Constraint mapping:** C3.1, C3.2
- **Frequency:** high
- **Impact:** P0

### 2026-07-01 - DMA cache stale data causes corrupted display

- **Source:** Camera/LCD preview intermittently shows old frames or color corruption.
- **Platform:** esp32
- **Symptom:** LCD sometimes shows tearing, wrong colors, or stale frames.
- **Root cause:** DMA writes memory, but CPU reads without invalidating cache; or CPU writes memory and DMA reads without cleaning cache.
- **Fix pattern:** After DMA write and before CPU read, invalidate cache. After CPU write and before DMA read, clean cache. Keep buffers aligned and in DMA-capable memory.
- **Constraint mapping:** C28.2
- **Frequency:** medium
- **Impact:** P0

### 2026-07-01 - Priority inversion causes audio stutter

- **Source:** Low-priority task holds shared resource while mid-priority tasks preempt it.
- **Platform:** generic
- **Symptom:** Audio intermittently underruns while logs show I2S starvation.
- **Root cause:** Shared resource is protected with a binary semaphore instead of a mutex with priority inheritance.
- **Fix pattern:** Use `xSemaphoreCreateMutex()` for shared resource locks that may block higher-priority tasks.
- **Constraint mapping:** C15.2
- **Frequency:** medium
- **Impact:** P1

### 2026-07-01 - Network reconnect storm starves other tasks

- **Source:** WiFi disconnect followed by tight reconnect loop.
- **Platform:** generic
- **Symptom:** CPU reaches 100 percent after disconnect and other tasks starve.
- **Root cause:** Reconnect loop retries immediately without exponential backoff or jitter.
- **Fix pattern:** Use exponential backoff with cap and jitter, for example 1s -> 2s -> 4s up to 60s.
- **Constraint mapping:** C20.1
- **Frequency:** high
- **Impact:** P0

### 2026-07-01 - Deep sleep wake loses state

- **Source:** Device wakes from deep sleep and reinitializes all state.
- **Platform:** esp32
- **Symptom:** User settings and connection state are lost after wake.
- **Root cause:** Critical state is not committed to NVS before sleep.
- **Fix pattern:** Before entering deep sleep, persist required state and verify commit result.
- **Constraint mapping:** C21.1
- **Frequency:** medium
- **Impact:** P0

---

## Experience Statistics

| Constraint area | Count | Frequency | Notes |
|---|---:|---|---|
| C1 LVGL thread/display lifecycle | 6 | high | Cross-thread calls, page factory ownership, deinit/link matrix, display restore |
| C3 cJSON | 1 | high | Cleanup on all parse paths |
| C7 resources | 2 | high | Large image/font resources and cache pressure |
| C9 secrets | 1 | high | Kconfig secret overlay boundary |
| C10 audio | 1 | high | Playback stop must not deinit shared capture backend |
| C15 priority | 1 | medium | Priority inheritance mutexes |
| C20 network | 2 | high | Reconnect backoff and WSS lifecycle |
| C21 low power | 1 | medium | State persistence before sleep |
| C22 OTA | 1 | high | Health check before marking valid |
| C23 display | 2 | high | Framebuffer lifecycle and LVGL display driver ownership |
| C24 peripheral shutdown | 5 | high | Shared backend and async task shutdown |
| C25 media pipeline | 3 | high | Page/media/resource coordination |
| C28 DMA/cache | 1 | medium | Cache maintenance around DMA |
| C31 bounded wait | 6 | high | WSS/audio/video teardown waits |
| C33 lifecycle | 7 | high | Explicit state/generation ownership |
| C36 config/link matrix | 5 | high | SDK API and config compatibility |
| C43 locks/backpressure | 4 | high | Do not block while holding hot-path locks |
| C44 interruptible hot path | 1 | high | Speaker stop and backpressure |
