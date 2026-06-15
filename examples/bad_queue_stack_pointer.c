/**
 * @file bad_queue_stack_pointer.c
 * @brief ❌ 反例：Queue payload 指向栈 buffer — Presenter 收到悬空指针 → HardFault
 *
 * 铁律 #2：禁止向 Queue 传递栈指针；cJSON* 须在解析函数内 Delete，不得进 Queue。
 *
 * 典型后果:
 *   - Presenter 在另一任务读 payload → 栈帧已失效 → 随机 HardFault
 *   - 低概率复现，量产最难查的 bug 之一
 *
 * 正确做法: good_presenter_consumer.c + good_wss_json_parse.c
 *   → Model pvPortMalloc payload → xQueueSend 拷贝 evt 结构体 → Presenter vPortFree
 */

#include "app_mvp.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "cJSON.h"
#include <string.h>
#include <stdio.h>

static QueueHandle_t s_net_evt_queue = NULL;

/* ❌ 错误 1：栈 buffer 赋给 payload，xQueueSend 只拷贝 evt 结构体，不拷贝栈内容 */
static void model_emit_stack_payload_bad(const char *text)
{
    char stack_copy[128];

    if (text == NULL || s_net_evt_queue == NULL) {
        return;
    }
    strncpy(stack_copy, text, sizeof(stack_copy) - 1);
    stack_copy[sizeof(stack_copy) - 1] = '\0';

    net_evt_t evt = {
        .type    = NET_EVT_DATA,
        .payload = stack_copy,   /* ❌ 栈指针进 Queue */
        .len     = strlen(stack_copy),
    };

    xQueueSend(s_net_evt_queue, &evt, pdMS_TO_TICKS(50));
    /* 函数返回后 stack_copy 失效，Presenter 读 msg.payload → 悬空 */
}

/* ❌ 错误 2：cJSON root 指针塞进 Queue */
static void model_emit_cjson_root_bad(const char *json_str)
{
    cJSON *root = cJSON_Parse(json_str);
    if (root == NULL || s_net_evt_queue == NULL) {
        return;
    }

    net_evt_t evt = {
        .type    = NET_EVT_DATA,
        .payload = (char *)root,   /* ❌ cJSON* 伪装成 char* 进 Queue */
        .len     = 0,
    };

    xQueueSend(s_net_evt_queue, &evt, pdMS_TO_TICKS(50));
    /* Presenter 无法安全 cJSON_Delete；且跨任务所有权混乱 */
}

/* ❌ 错误 3：xQueueSend 直接传栈上 evt 的指针字段地址（sizeof=指针的 Queue） */
static void model_send_stack_ptr_bad(QueueHandle_t ptr_queue)
{
    char local_buf[32] = "ephemeral";
    char *ptr = local_buf;

    xQueueSend(ptr_queue, &ptr, portMAX_DELAY);
    /* ptr_queue 元素为 char* 时，队列存的是栈上 ptr 变量的地址副本，仍指向将失效的 local_buf */
}

void bad_queue_demo_start(void)
{
    s_net_evt_queue = xQueueCreate(4, sizeof(net_evt_t));
    configASSERT(s_net_evt_queue != NULL);

    model_emit_stack_payload_bad("hello");
    model_emit_cjson_root_bad("{\"text\":\"x\"}");
}

/*
 * ══════════════════════════════════════════════════════════
 *  修复清单（铁律 #2）
 * ══════════════════════════════════════════════════════════
 *
 *  [ ] payload 仅 pvPortMalloc / 静态全局（生命周期明确）
 *  [ ] cJSON_Parse 在同函数 cleanup 分支 cJSON_Delete，只把 plain string 进 Queue
 *  [ ] Queue 满时 Model 释放已分配 payload
 *  [ ] Presenter 消费后 vPortFree(payload)
 *  [ ] 运行: python tools/queue_ownership_checker.py 本文件 → 应 FAIL
 */
