# 鐜板満缁忛獙鏃ュ織锛堣嚜瀛︿範绯荤粺锛?
Agent 鎴栫淮鎶よ€呭湪鍙戠幇鏂扮殑 anti-pattern 鎴栫幇鍦虹粡楠屾椂杩藉姞鏉＄洰銆?*鏈€鏂板湪涓娿€?*

## 鏉＄洰妯℃澘

```markdown
### YYYY-MM-DD 鈥?绠€鐭爣棰?
- **鏉ユ簮锛?* 鐜板満鏃ュ織 / 鐢ㄦ埛鍙嶉 / CI / 閲忎骇
- **骞冲彴锛?* esp32 | stm32 | jl | bk | zephyr | 閫氱敤
- **鐥囩姸锛?* 涓€鍙ヨ瘽鎻忚堪鐜拌薄
- **鏍瑰洜锛?* 閫氱敤鏍瑰洜鍒嗘瀽
- **淇妯″紡锛?* 閫氱敤淇妯″紡
- **绾︽潫鏄犲皠锛?* C#.# 鎴栥€屽缓璁柊澧?CXX銆?- **棰戠巼锛?* 浣?涓?楂?- **褰卞搷锛?* P0/P1/P2
```

---
### 2026-07-07 - JL LVGL audio page plays but UI advances or freezes

- **Source:** AC792/WL83 field logs during healing-audio page debugging.
- **Platform:** jl
- **Symptom:** The healing audio file can be started by the low-level player, but the LVGL page immediately advances on click, or the page stays busy/frozen while the device itself is still alive.
- **Root cause:** The media business state was not tied to both low-level player state and UI navigation completion. In one failure mode, an unknown/none stream event was interpreted as STOP/ERROR, so the business state returned to idle while audio was still playing and the click handler allowed next-page navigation. In another failure mode, playback completion posted an async UI navigation request but cleared or held busy state at the wrong boundary.
- **Fix pattern:** Use an explicit `IDLE -> STARTING -> PLAYING -> UI_NAV_PENDING -> IDLE` state machine. Treat unknown stream events as ignored/diagnostic, not business errors. Make `is_playing()` consult both the business state and low-level player status. During STARTING/PLAYING/UI_NAV_PENDING, ignore click/back/restart unless cancel behavior is explicitly required. Clear UI/media busy only from the UI task after page reload/navigation returns.
- **Required logs:** `audio start request accepted`, `audio playback observed running`, `audio done, nav next requested`, `ui nav/reload entered`, `ui nav/reload returned`, `audio ui nav done`, `click ignored during audio/transition`.
- **Constraint mapping:** C1.1, C24.1, C25.4, C31.3, C33.1, C36.1, C43.5
- **Frequency:** high
- **Impact:** P0

### 2026-07-07 - JL LVGL full-page switch remains 1 FPS after visual assets are correct

- **Source:** AC792/WL83 field logs and repeated HOME/PUSH/Schedule page switching tests.
- **Platform:** jl
- **Symptom:** UI assets eventually display correctly, but full-page switching still feels stalled and logs show FPS around 1-2 during page changes.
- **Root cause:** Page switching repeatedly decodes large JPEG backgrounds/cards and recreates large LVGL object trees from touch-context navigation. Page object caching alone does not prevent file-image decode cache eviction. Direct per-page `lv_img_set_src(path)` calls prevent common cache/fallback policy from working consistently.
- **Fix pattern:** Move every BG/ICON access behind the common resource layer; cache shared backgrounds and small icon descriptors separately; keep the current and adjacent page containers when RAM permits; restore a cached page's registered background before showing it; make touch callbacks only post navigation and return; add decode timing logs to identify the exact slow asset.
- **Required logs:** `page transition begin/end`, `page cache hit/store/evict`, `asset bg decode begin/end`, `asset bg reuse`, `click ignored during guard`.
- **Constraint mapping:** C1.1, C7.12, C23.6, C25.4, C33.1, C36.1
- **Frequency:** high
- **Impact:** P1

### 2026-07-07 - JL LVGL 椤甸潰鏍?TF 璧勬簮/鏈湴濯掍綋鑱旇皟澶嶅悎鏁呴殰

- **鏉ユ簮锛?* AC792/WL83 鑳屽す灞忕幇鍦烘棩蹇楋紝鐘舵€?HOME/PUSH 椤甸潰銆乀F 鍥剧墖璧勬簮銆佽棰?闊抽鎾斁鑱旇皟
- **骞冲彴锛?* jl
- **鐥囩姸锛?* 椤甸潰鍒囨崲浣?FPS 鎴栧崱椤匡紱PNG/JPEG 閮ㄥ垎璧勬簮涓嶆樉绀猴紱瑙嗛鎾斁涓ら亶鍚庤繘鍏ヤ笅涓€椤垫浘閲嶅惎锛涢煶棰戦〉闊抽宸叉挱鏀句絾椤甸潰浠嶅彲鐐瑰嚮璺宠蛋锛涙棩蹇楀嚭鐜?`Can't set the parent of a screen`銆佸弽澶?`jpeg_dec0_task`銆乣healing audio error: 0` 绛夌嚎绱€?- **鏍瑰洜锛?* 澶氫釜鐢熷懡鍛ㄦ湡杈圭晫娣峰湪涓€璧凤細椤甸潰鍏堝垱寤轰负 screen 鍐?reparent 鍒板唴瀹瑰眰锛涢〉闈㈠璞＄紦瀛樻病鏈夊悓姝ユ仮澶嶅叕鍏辫儗鏅紱480脳800 JPEG 琚儗鏅拰鍗＄墖鍙嶅鎶㈠崰 LVGL 鍥剧墖缂撳瓨锛涘簳灞?`STREAM_EVENT_NONE` 琚粯璁ゆ槧灏勬垚涓氬姟 ERROR锛屽鑷撮煶棰戜笟鍔＄姸鎬佹彁鍓?idle銆?- **淇妯″紡锛?* 椤甸潰 factory 鎺ユ敹 `content_layer` parent锛屾櫘閫氶〉闈㈠彧 `lv_obj_create(parent)`锛涘叕鍏辫儗鏅眰璁板綍姣忎釜椤甸潰鐨?path/fallback锛屾樉绀虹紦瀛橀〉鏃舵仮澶嶈儗鏅紱鑳屾櫙璧板叕鍏辫祫婧愬眰 lazy load锛屽皬缁勪欢浼樺厛 PNG/RAW descriptor锛孞PEG fallback锛涘獟浣撶姸鎬佹満蹇呴』鏈?`PLAYING -> UI_NAV_PENDING -> IDLE` 杈圭晫锛涢煶棰戜簨浠跺彧瀵规槑纭?START/STOP/END/鐪熷疄鏁呴殰鏀圭姸鎬侊紝鏈煡 stream event 涓嶄笂鎶?ERROR锛沗is_playing()` 鍚屾椂鍙傝€冧笟鍔＄姸鎬佸拰搴曞眰 player銆?- **绾︽潫鏄犲皠锛?* C1.1, C1.2, C13.1, C25.3, C25.4, C31.3, C33.1, C34.1, C36.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-07 - JL LVGL 瑙嗛缁撴潫鍒板紓姝ラ〉闈㈠垏鎹㈢殑閲嶅叆绔炴€?
- **鏉ユ簮锛?* AC792/WL83 鐜板満鏃ュ織锛岃棰戞挱鏀句袱閬嶅悗鍒囬〉/閲嶅惎璋冭瘯
- **骞冲彴锛?* jl
- **鐥囩姸锛?* 瑙嗛鍙互鎾斁锛屼絾鎾斁缁撴潫鍚庡垏鍒颁笅涓€涓?LVGL 椤甸潰鏃讹紝璁惧鍙兘閲嶅惎銆佽Е鎽稿け鏁堬紝鎴栦笅涓€椤靛嚭鐜版棫鏍囬/缁勪欢鍙犲姞銆?- **鏍瑰洜锛?* 瑙嗛浠诲姟鎶娾€滄挱鏀剧粨鏉熲€濈瓑鍚屼簬鈥淯I 鍒囨崲瀹屾垚鈥濄€傚綋鍓?SDK 涓?UI 鎭㈠/椤甸潰璺宠浆璧板紓姝?UI RPC/LVGL 浠诲姟璺緞锛屽鏋滃湪 UI 鍥炶皟鐪熸瀹屾垚鍓嶆竻鎺?playing/busy 鏍囧織锛岃Е鎽搞€佽繑鍥炴垨閲嶅鎾斁灏卞彲鑳介噸鍏ラ〉闈㈠垱寤恒€佸獟浣撳惎鍔ㄦ垨瀵硅薄鍒犻櫎銆?- **淇妯″紡锛?* 鎶婂熬娈靛缓鎴愬畬鏁寸姸鎬佹満锛歚IDLE -> PLAYING -> UI_NAV_PENDING -> IDLE`銆傚獟浣撳惊鐜繑鍥炲悗杩涘叆 `UI_NAV_PENDING`锛涚姸鎬侀潪 `IDLE` 鏃跺睆钄借Е鎽搞€佽繑鍥炲拰閲嶅鎾斁锛涘彧鏈?UI 绾跨▼鍥炶皟涓?`ui_main_reset_to_next_page()` 鎴?reload 鐪熸杩斿洖鍚庯紝鎵嶆竻鍥?`IDLE`銆傜敤 `video done, nav next` 鍜?`video ui nav done` 涓や釜鏃ュ織璇佹槑椤哄簭銆?- **绾︽潫鏄犲皠锛?* C1.1, C24.1, C31.3, C33.1, C36.1, C43.5
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-07 - JL LVGL 鎾斁瑙嗛鏃跺叧闂?閲嶅紑 fb0 瀵艰嚧鏄剧ず鐢熷懡鍛ㄦ湡鏁呴殰

- **鏉ユ簮锛?* AC792/WL83 鐜板満鏃ュ織锛岃棰戞挱鏀惧畬鎴愬悗鍑虹幇 `fb0` 閲嶅紑澶辫触涓?hmem access exception
- **骞冲彴锛?* jl
- **鐥囩姸锛?* 瑙嗛鍦ㄧ嫭绔?framebuffer/layer 涓婅兘鎾斁锛屼絾杩斿洖 LVGL 鍚庡嚭鐜颁綆甯х巼銆侀〉闈笉鏄剧ず銆乣fb0 open failed`锛屾垨鏄剧ず鎭㈠鍚庨噸鍚€?- **鏍瑰洜锛?* 鐭棰戞挱鏀鹃€氳繃 suspend LVGL 骞跺叧闂?閲嶅紑 LVGL 涓?framebuffer (`fb0`) 瀹炵幇銆傚湪 JL display combine/layer 璺緞涓嬶紝杩欎細璁?LVGL flush銆佹樉绀洪┍鍔?reopen銆佽棰戝眰 teardown 涔嬮棿浜х敓鐢熷懡鍛ㄦ湡绔炴€侊紝鏁呴殰閫氬父鍑虹幇鍦ㄨ棰戠粨鏉熷悗銆?- **淇妯″紡锛?* 鐭棰戣鐩栨挱鏀炬椂淇濇寔 LVGL 鍜?`fb0` 甯搁┗锛涜棰戜娇鐢ㄤ笓鐢ㄩ《灞?framebuffer/layer锛屼緥濡?`fb4`锛屽苟淇濊瘉 z-order 楂樹簬 LVGL锛涙挱鏀剧粨鏉熷悗鍙€氳繃 UI 浠诲姟璇锋眰 reload/nav銆傚獟浣撳洖璋冧腑绂佹鐩存帴鎿嶄綔 LVGL 瀵硅薄銆?- **绾︽潫鏄犲皠锛?* C1.1, C23.6, C24.1, C25.4, C31.3, C33.1
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P0
### 2026-07-07 - JL LVGL fb0 close/reopen during video overlay causes display lifecycle fault

- **Source:** AC792/WL83 field log, video playback completion followed by `fb0` reopen failure and hmem access exception
- **Platform:** jl
- **Symptom:** Video plays on a separate framebuffer/layer, then returning to LVGL triggers low FPS, missing page, `fb0 open failed`, or reboot after display restore.
- **Root cause:** Short video playback was implemented by suspending LVGL and closing/reopening the LVGL framebuffer (`fb0`). On JL display combine/layer paths this creates a lifecycle race between LVGL flush, display driver reopen, and video layer teardown. The failure may appear after the video, not at video start.
- **Fix pattern:** Keep LVGL and `fb0` alive for short overlay playback. Put video on a dedicated top layer/framebuffer such as `fb4`, force its z-order above LVGL, and only request UI reload/navigation through the UI task after playback ends. Do not call LVGL object APIs from media callbacks.
- **Constraint mapping:** C1.1, C23.6, C24.1, C25.4, C31.3, C33.1
- **Frequency:** medium
- **Impact:** P0
### 2026-07-03 鈥?BK 澶т綋绉?TF binfont 鏀惧ぇ WSS 鏂嚎閿€姣?assert

- **鏉ユ簮锛?* BK7258 app_paltte 鏇挎崲 TF 涓枃瀛楀簱鍚庣幇鍦洪噸鍚棩蹇?- **骞冲彴锛?* BK
- **鐥囩姸锛?* 灏嗙害 270KB 鐨?`my_font_16.bin` 鏇挎崲涓虹害 2.3MB 瀛楀簱鍚庯紝璁惧鍚姩鍚?WiFi 鏂紑骞惰繘鍏?WSS disconnect锛岄殢鍚?FreeRTOS `Assert at: xTaskPriorityDisinherit` 閲嶅惎
- **鏍瑰洜锛?* LVGL binfont 鍔犺浇浼氭妸瀛椾綋鍏冩暟鎹?浣嶅浘鏀惧叆杩愯鍐呭瓨锛孴F 鏂囦欢浣撶Н浼氱洿鎺ユ秷鑰?PSRAM/heap锛涘ぇ璧勬簮闄嶄綆鍐呭瓨浣欓噺鍚庯紝缃戠粶鏂嚎璺緞涓寔搴旂敤 mutex 璋冪敤 websocket destroy/free锛屽鏄撴斁澶?SDK websocket task 涓庡洖璋冪殑閿?鐢熷懡鍛ㄦ湡绔炴€?- **淇妯″紡锛?* 澶栭儴 UI 璧勬簮鍔犺浇鍓嶅厛 stat 鏂囦欢澶у皬骞惰缃?Kconfig 涓婇檺锛岃秴闄愰檷绾у埌鍐呯疆瀛椾綋锛涘姞杞藉墠鍚庤褰?heap/PSRAM 浣欓噺锛沇SS RX/TX buffer 蹇呴』鎸夊崗璁崟甯ч渶姹傞厤缃紝涓嶈榛樿 64KB 澶?buffer 涓庡瓧浣?鍥剧墖浜?PSRAM锛沇SS disconnect/reconnect/deinit 鍏堝湪搴旂敤閿佸唴 detach 褰撳墠 client 骞惰 stale event 澶辨晥锛屽啀鍦ㄩ攣澶栨墽琛屽彲鑳介樆濉炵殑 SDK destroy锛涙柇缃?閲嶈繛浣滀负鍥炲綊鐢ㄤ緥
- **绾︽潫鏄犲皠锛?* C7.12, C20.5, C31.3, C33.1, C38.1, C43.1
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P0

### 2026-07-03 鈥?BK 褰曢煶缁撴潫鎭㈠ STA 鐪佺數瑙﹀彂 IPC 蹇冭烦閲嶅惎

- **鏉ユ簮锛?* BK7258 app_paltte 褰曢煶鍋滄鍚庨噸鍚幇鍦烘棩蹇?- **骞冲彴锛?* BK
- **鐥囩姸锛?* AI 褰曢煶 stop / `CLIENT_AUDIO_FINISH` 鍚庣害 8s 閲嶅惎锛屾棩蹇楀嚭鐜?`IPC[1]heartbeat timeout ...` 涓?`Assert at: mb_ipc_task:275`锛屾棤 HardFault锛涜嫢寮鸿 stop/restart voice read锛岀浜岃疆褰曢煶鍙兘鍒?`AEL_IO_ABORT`
- **鏍瑰洜锛?* 褰曢煶缁撴潫绔嬪嵆璋冪敤 `bk_wifi_sta_pm_enable()` 鎭㈠ STA power save锛屼娇 WiFi/闊抽/IPC 璺ㄦ牳鐘舵€佸垏鎹㈡椂 CPU1 蹇冭烦鍋滄锛汢K CP 渚?`CONFIG_INT_WDT_PERIOD_MS=8000` 鍒版湡鍚?assert 閲嶅惎
- **淇妯″紡锛?* 褰曢煶鏈熼棿 `bk_wifi_sta_pm_disable()` 鍚庯紝涓嶈鍦?capture stop 绔嬪嵆鎭㈠ STA 鐪佺數锛涗繚鎸?voice/read handle 鍙繘鍏?gated idle锛岄伩鍏?stop 鍚庨噸鍚?reader锛涘彧鍦?deinit 鎴栫粡闀挎祴楠岃瘉鐨勫畨鍏ㄧ獥鍙ｆ仮澶?PM锛涢獙鏀舵棩蹇楄姹傛棤 `IPC heartbeat timeout`銆佹棤 `AEL_IO_ABORT` 杩炲埛锛屼笖澶氳疆 `CLIENT_AUDIO_FINISH ok=1`
- **绾︽潫鏄犲皠锛?* C8.3, C20.1, C24.4, C31.3, C33.1, C38.4
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P0

### 2026-07-02 鈥?WSS 閿€姣佸悗寮傛浠诲姟浠嶈闂?client

- **鏉ユ簮锛?* BK7258 app_paltte 鐜板満閲嶅惎涓庢彁浜ゅ墠瀹℃煡
- **骞冲彴锛?* BK
- **鐥囩姸锛?* WiFi 鏂嚎銆佽闊冲瓙绯荤粺 stop 鎴?WSS 閲嶈繛鍚庯紝璁惧鍋跺彂閲嶅惎銆佸爢寮傚父鎴?stale event
- **鏍瑰洜锛?* WebSocket SDK 浠诲姟灏氭湭閫€鍑烘椂 destroy/free client 鎴?config锛泂ocket 鏈富鍔ㄥ敜閱掞紝鍥炶皟缂哄皯褰撳墠 client/generation 杩囨护锛屼换鍔′笌 destroy 璺緞鎵€鏈夋潈杈圭晫涓嶆竻
- **淇妯″紡锛?* 涓?WSS client 寤虹珛鏄惧紡 state/generation锛沝estroy 鍏堟爣璁?disconnecting 骞?abort/close fd 鍞ら啋浠诲姟锛屽啀鏈夌晫绛夊緟 task exit锛涘彧鍏佽涓€涓矾寰勯噴鏀?client/config锛涘洖璋冭繃婊?stale client锛涢攣鍐呬笉鍋氬彲鑳介樆濉炵殑 close/send
- **绾︽潫鏄犲皠锛?* C24.1, C31.3, C33.1, C36.1, C43.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-02 鈥?TTS/speaker 鐑矾寰勭己灏戞睜闃叉姢鍜屽彲涓柇鍙嶅帇

- **鏉ユ簮锛?* BK7258 app_paltte 闊抽閾捐矾鐜板満閲嶅惎
- **骞冲彴锛?* BK
- **鐥囩姸锛?* 澶氳疆 TTS銆佹墦鏂垨 speaker stop 鍚庡嚭鐜伴殢鏈洪噸鍚€乸ayload/PCM 瓒婄晫銆佹挱鏀炬嫋浣?stop
- **鏍瑰洜锛?* 闊抽 queue payload 鎵€鏈夋潈鍜屾睜 slot 鐢熷懡鍛ㄦ湡涓嶅纭紱鍙橀暱 TTS payload/PCM 缂哄皯棣栧熬 guard锛泂peaker 鍐欏叆鐑矾寰勬寔閿佽皟鐢ㄥ簳灞傞樆濉?API锛宻top/interruption 鏃犳硶鍙婃椂鎶㈠崰
- **淇妯″紡锛?* 鍥哄畾姹?slot 鍔?head/tail canary锛屽叆闃?鍑洪槦/free 鍓嶆牎楠岋紱璁板綍 queued/played/dropped/backpressure/high-water锛泂peaker 鍐欏叆浣跨敤 generation interrupt銆佺煭瓒呮椂閿佸拰鏈夐檺閲嶈瘯锛泂top 鍙姹備换鍔￠€€鍑哄苟鏈夌晫绛夊緟
- **绾︽潫鏄犲皠锛?* C2.1, C31.1, C33.1, C43.5, C44.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-02 鈥?LVGL deinit API 瀛樺湪浣嗛厤缃煩闃垫湭閾炬帴

- **鏉ユ簮锛?* BK7258 app_paltte 鎻愪氦鍓嶇紪璇?- **骞冲彴锛?* BK
- **鐥囩姸锛?* 涓鸿ˉ鐢熷懡鍛ㄦ湡瀵圭О鎬ц皟鐢?`lv_deinit()` 鍚庯紝閾炬帴澶辫触锛歚undefined reference to lv_mem_deinit`
- **鏍瑰洜锛?* LVGL 澶存枃浠跺鍑轰簡 `lv_deinit()`锛屼絾褰撳墠 `LV_USE_STDLIB_MALLOC=LV_STDLIB_CUSTOM` 閰嶇疆娌℃湁鎻愪緵 `lv_mem_deinit()` 瀹炵幇锛涘彧鐪嬫簮鐮?API 浼氳鍒ゅ彲鐢ㄦ€?- **淇妯″紡锛?* LVGL 鍏ㄥ眬 deinit 蹇呴』缁忚繃鐩爣宸ョ▼閾炬帴楠岃瘉锛涜嫢鍐呭瓨 backend 涓嶅畬鏁达紝搴旂敤灞傚彧鍒犻櫎 display/object 骞跺仠姝㈠钩鍙?display driver锛涗笉瑕佷负閫氳繃 checker 纭皟鐢ㄦ湭闂悎鐨?SDK API
- **绾︽潫鏄犲皠锛?* C1.2, C24.1, C36.1, C39.1
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P1

### 2026-07-02 鈥?Kconfig secret overlay 涓庢彁浜ら厤缃竟鐣?
- **鏉ユ簮锛?* BK7258 app_paltte secret scan 涓庢瀯寤鸿剼鏈?- **骞冲彴锛?* 閫氱敤
- **鐥囩姸锛?* secret scan 鍚屾椂鎶ュ嚭宸叉彁浜?`config` 鍜屾湰鍦?`config.secrets` 涓殑浜戠瀵嗛挜
- **鏍瑰洜锛?* 鐪熷疄鍑嵁鏇捐惤鍏?tracked Kconfig锛涙湰鍦?overlay 铏借 ignore锛屼絾鎵弿鍣ㄩ粯璁や粛浼氭壂鍒?ignored 鏂囦欢锛屽鏄撴妸鈥滃彲鏋勫缓鏈湴瀵嗛挜鈥濆拰鈥滃叆搴撴硠婕忊€濇贩鍦ㄤ竴璧?- **淇妯″紡锛?* tracked `config` 涓晱鎰?Kconfig 姘歌繙涓虹┖锛涚湡瀹炲€煎彧鏀?ignored `config.secrets`锛岀敱鏋勫缓鑴氭湰涓存椂 overlay 骞跺湪缁撴潫鍚庢仮澶嶏紱鎻愪氦鍓嶅繀椤绘鏌?`git check-ignore`銆乣git ls-files`銆乻taged diff锛屽苟杞崲鏇惧叆搴撶殑瀵嗛挜
- **绾︽潫鏄犲皠锛?* C9.1, C9.6, C36.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-01 鈥?OTA 鏂數鍥炴粴澶辫触

- **鏉ユ簮锛?* 閲忎骇璁惧 OTA 鍗囩骇鍚庢柇鐢碉紝閲嶅惎鍚庢棤娉曞洖婊?- **骞冲彴锛?* ESP32
- **鐥囩姸锛?* OTA 鍗囩骇鍚庢柇鐢碉紝璁惧閲嶅惎鍚庡仠鐣欏湪鏂板浐浠朵絾鍔熻兘寮傚父
- **鏍瑰洜锛?* 鏈皟鐢?`esp_ota_mark_app_valid_cancel_rollback()`锛宐ootloader 璁や负鏂板浐浠舵棤鏁堜絾鏃犳棫鍥轰欢鍙洖婊?- **淇妯″紡锛?* 棣栨鍚姩鍚庡仛 health check锛岄€氳繃鍚庤皟鐢?mark_valid_cancel_rollback
- **绾︽潫鏄犲皠锛?* C22.2
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-01 鈥?闊抽鎵撴柇鍚?MIC 澶辨晥

- **鏉ユ簮锛?* BK7258 AI 闂归挓锛孴TS 鎵撴柇鍚?MIC 涓嶅啀閲囬泦
- **骞冲彴锛?* BK
- **鐥囩姸锛?* 鐢ㄦ埛鎵撴柇 TTS 鍚庯紝ASR 涓嶅啀鏀跺埌闊抽鏁版嵁
- **鏍瑰洜锛?* speaker stop 鏃堕敊璇?deinit 浜嗗叡浜殑 audio backend锛屽鑷?capture 璺緞涔熻閲婃斁
- **淇妯″紡锛?* 鍖哄垎 idle 涓?deinit锛宻top playback 鍙繘 idle锛屼笉閲婃斁鍏变韩 backend
- **绾︽潫鏄犲皠锛?* C24.4, C10.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-01 鈥?LVGL 璺ㄧ嚎绋?HardFault

- **鏉ユ簮锛?* WSS 鍥炶皟鐩存帴璋冪敤 lv_label_set_text
- **骞冲彴锛?* 閫氱敤
- **鐥囩姸锛?* 缃戠粶娑堟伅鍒拌揪鏃跺伓鍙?HardFault 鎴栧睆骞曡姳灞?- **鏍瑰洜锛?* WSS 浠诲姟涓婁笅鏂囩洿鎺ヨ皟鐢?LVGL API锛屾棤 mutex 淇濇姢
- **淇妯″紡锛?* 浣跨敤 lv_async_call 鎴?Queue 鈫?Presenter 鈫?View 妯″紡
- **绾︽潫鏄犲皠锛?* C1.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-01 鈥?cJSON 娉勬紡瀵艰嚧 heap 鑰楀敖

- **鏉ユ簮锛?* WSS JSON 瑙ｆ瀽鍚?early return 鏈?Delete
- **骞冲彴锛?* 閫氱敤
- **鐥囩姸锛?* 璁惧杩愯鏁板皬鏃跺悗 malloc 澶辫触
- **鏍瑰洜锛?* cJSON_Parse 鍚庡湪閿欒璺緞 early return锛屾湭璋冪敤 cJSON_Delete
- **淇妯″紡锛?* 浣跨敤 goto cleanup 妯″紡锛岀粺涓€ cJSON_Delete
- **绾︽潫鏄犲皠锛?* C3.1, C3.2
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-01 鈥?DMA cache 鑴忔暟鎹鑷磋姳灞?
- **鏉ユ簮锛?* Camera preview 鍋跺彂鑺卞睆鎴栨棫甯?- **骞冲彴锛?* ESP32
- **鐥囩姸锛?* LCD 鏄剧ず鍋跺彂鑺卞睆銆侀鑹查敊涔辨垨鏄剧ず鏃у抚
- **鏍瑰洜锛?* DMA 鍐欏叆鍚?CPU 璇诲墠鏈?invalidate锛孋PU 璇诲埌 cache 涓殑鏃ф暟鎹?- **淇妯″紡锛?* DMA 鍐欏悗 CPU 璇诲墠 invalidate锛孋PU 鍐欏悗 DMA 璇诲墠 clean
- **绾︽潫鏄犲皠锛?* C28.2
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P0

### 2026-07-01 鈥?浼樺厛绾у弽杞鑷撮煶棰戝崱椤?
- **鏉ユ簮锛?* 浣庝紭鍏堢骇浠诲姟鎸?mutex 鏃惰涓紭鍏堢骇浠诲姟鎶㈠崰
- **骞冲彴锛?* 閫氱敤
- **鐥囩姸锛?* 闊抽鍋跺彂鍗￠】锛屾棩蹇楁樉绀?I2S underrun
- **鏍瑰洜锛?* 鍏变韩璧勬簮鐢?binary semaphore 淇濇姢锛屾棤浼樺厛绾х户鎵?- **淇妯″紡锛?* 浣跨敤 xSemaphoreCreateMutex锛堝甫浼樺厛绾х户鎵匡級
- **绾︽潫鏄犲皠锛?* C15.2
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P1

### 2026-07-01 鈥?缃戠粶閲嶈繛椋庢毚

- **鏉ユ簮锛?* WiFi 鏂嚎鍚?tight loop 閲嶈繛
- **骞冲彴锛?* 閫氱敤
- **鐥囩姸锛?* WiFi 鏂嚎鍚?CPU 100%锛屽叾浠栦换鍔￠ゥ楗?- **鏍瑰洜锛?* 閲嶈繛鏃犳寚鏁伴€€閬匡紝绔嬪嵆閲嶈瘯
- **淇妯″紡锛?* 鎸囨暟閫€閬匡紙1s鈫?s鈫掆€︹啋60s cap锛?- **绾︽潫鏄犲皠锛?* C20.1
- **棰戠巼锛?* 楂?- **褰卞搷锛?* P0

### 2026-07-01 鈥?娣辩潯鐪犲悗鐘舵€佷涪澶?
- **鏉ユ簮锛?* 璁惧娣辩潯鐪犲敜閱掑悗閲嶆柊鍒濆鍖栨墍鏈夌姸鎬?- **骞冲彴锛?* ESP32
- **鐥囩姸锛?* 鍞ら啋鍚庝涪澶辩敤鎴疯缃€佽繛鎺ョ姸鎬佺瓑
- **鏍瑰洜锛?* 娣辩潯鐪犲墠鏈繚瀛樼姸鎬佸埌 NVS
- **淇妯″紡锛?* 娣辩潯鐪犲墠 nvs_commit 淇濆瓨鍏抽敭鐘舵€?- **绾︽潫鏄犲皠锛?* C21.1
- **棰戠巼锛?* 涓?- **褰卞搷锛?* P0

---

## 缁忛獙缁熻

| 绾︽潫鍩?| 缁忛獙鏁?| 棰戠巼 | 璇存槑 |
|--------|--------|------|------|
| C1 LVGL | 2 | 楂?| 璺ㄧ嚎绋嬭皟鐢?/ deinit 閰嶇疆鐭╅樀 |
| C3 cJSON | 1 | 楂?| 娉勬紡 |
| C9 secrets | 1 | 楂?| Kconfig secret overlay |
| C10 璇煶 | 1 | 楂?| 鎵撴柇鍚庡け鏁?|
| C15 浼樺厛绾?| 1 | 涓?| 浼樺厛绾у弽杞?|
| C20 缃戠粶 | 1 | 楂?| 閲嶈繛椋庢毚 |
| C21 浣庡姛鑰?| 1 | 涓?| 鐘舵€佷涪澶?|
| C22 OTA | 1 | 楂?| 鏂數鍥炴粴 |
| C24 澶栬鍏抽棴 | 3 | 楂?| 鍏变韩 backend / WSS task / LVGL display |
| C31 鏈夌晫绛夊緟 | 2 | 楂?| WSS/audio stop 鏈夌晫鍖?|
| C33 鐢熷懡鍛ㄦ湡 | 2 | 楂?| 浠诲姟閫€鍑轰笌 stop/deinit 瀵圭О |
| C36 閰嶇疆鐭╅樀 | 3 | 楂?| secret overlay / SDK API 閾炬帴楠岃瘉 |
| C43 閿侀绠?| 2 | 楂?| WSS close/send / speaker write 鐑矾寰?|
| C44 涓寸晫璺緞 | 1 | 楂?| speaker 鍙嶅帇鍙腑鏂?|
| C28 DMA | 1 | 涓?| cache 鑴忔暟鎹?|

