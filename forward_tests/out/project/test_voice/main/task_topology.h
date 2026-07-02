/**
 * @file task_topology.h
 * @brief test_voice 任务拓扑表（C30）
 *
 * 自动生成 — 描述任务/队列/信号量的拓扑关系。
 */

#ifndef TEST_VOICE_TASK_TOPOLOGY_H
#define TEST_VOICE_TASK_TOPOLOGY_H

#ifdef __cplusplus
extern "C" {
#endif

/* ── 任务拓扑表 ── */
/*  任务名           | 栈(B) | 优先级 | Core | 描述 */
/*  main_task            |  4096 |      5 | Any  | 主逻辑任务 */
/*  ui_task              |  8192 |      3 | Core 1 | LVGL UI 渲染任务 */
/*  audio_task           |  4096 |      6 | Core 1 | 音频采集/播放任务 */
/*  network_task         |  8192 |      4 | Core 0 | WSS/TLS 网络任务 */
/*  ota_task             |  4096 |      2 | Any  | OTA 升级任务（按需创建） */

/* ── 队列拓扑表 ── */
/*  队列名           | item_size | depth | 描述 */
/*  ui_cmd_queue         |        16 |     8 | UI 命令队列 */
/*  audio_frame_queue    |       128 |     4 | 音频帧队列 */

#ifdef __cplusplus
}
#endif

#endif /* TEST_VOICE_TASK_TOPOLOGY_H */