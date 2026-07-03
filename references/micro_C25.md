# C25 A/V 管线微分片

> ~800 tokens。完整规则见 `constraint_media.md`。

## 典型症状

- 音视频不同步
- 视频掉帧
- 音频爆音

## 危险模式

```c
// ❌ 回调中分配内存
void lcd_flush_cb(lv_disp_drv_t *drv, const lv_area_t *area, lv_color_t *buf) {
    lv_color_t *fb = malloc(fb_size);  // 禁止！
    // ...
}
```

## A/V 管线规则

1. Audio clock master，Video 跟随
2. 回调中禁止 malloc/printf/锁
3. 队列满时丢旧帧，不阻塞
4. DMA buffer 必须对齐

## 相关 Checker

- `av_pipeline_checker.py` — 自动检测

## 升级到完整 Shard

需要 PTS 同步、jitter buffer、codec 生命周期细节时 → 加载 `constraint_media.md`
