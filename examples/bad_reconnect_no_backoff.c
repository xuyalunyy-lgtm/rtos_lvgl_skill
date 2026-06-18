/**
 * 反例 — C20 网络韧性违规
 *
 * 违反约束:
 *   C20.1 — WiFi/WSS 重连无指数退避（tight loop）
 *   C20.2 — 阻塞网络操作无超时
 *
 * 对照正例: network_resilience.txt
 */

#include "app_mvp.h"
#include "esp_wifi.h"

/* ========== 反例 1: WiFi 重连 tight loop (C20.1) ========== */

/* ❌ 断线后立即重连，无退避，可能永远连不上 */
static void bad_wifi_event_handler(void *arg, esp_event_base_t base,
                                    int32_t event_id, void *data)
{
    if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();  /* 立即重连，无延迟 */
    }
}

/* ❌ WSS 重连无退避 */
static void bad_wss_reconnect(void)
{
    while (1) {
        int ret = wss_connect(url);
        if (ret == 0) {
            break;
        }
        /* 无延迟，CPU 空转 */
    }
}

/* ========== 反例 2: 阻塞网络操作无超时 (C20.2) ========== */

/* ❌ recv 使用 portMAX_DELAY，断线后永久阻塞 */
static int bad_recv_data(int sock, uint8_t *buf, size_t len)
{
    return recv(sock, buf, len, 0);  /* 默认可能无超时 */
}

/* ❌ TLS 握手无超时 */
static int bad_tls_handshake(mbedtls_ssl_context *ssl)
{
    return mbedtls_ssl_handshake(ssl);  /* 可能永久阻塞 */
}

/* ========== 正例对照 ========== */

/* ✅ 正确: 指数退避重连 */
#define WIFI_RECONNECT_BASE_MS  1000
#define WIFI_RECONNECT_MAX_MS   60000

static int s_retry_count = 0;

static void good_wifi_event_handler(void *arg, esp_event_base_t base,
                                     int32_t event_id, void *data)
{
    if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_count < 10) {
            uint32_t delay = WIFI_RECONNECT_BASE_MS * (1 << s_retry_count);
            if (delay > WIFI_RECONNECT_MAX_MS) {
                delay = WIFI_RECONNECT_MAX_MS;
            }
            LOG_I(TAG, "WiFi disconnected, retry in %ums", delay);
            vTaskDelay(pdMS_TO_TICKS(delay));
            esp_wifi_connect();
            s_retry_count++;
        } else {
            LOG_E(TAG, "WiFi reconnect failed after %d retries", s_retry_count);
            /* 降级为离线模式 */
        }
    }
}

/* ✅ 正确: 带超时的 recv */
static int good_recv_data(int sock, uint8_t *buf, size_t len)
{
    struct timeval tv = {
        .tv_sec = 10,
        .tv_usec = 0,
    };
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    return recv(sock, buf, len, 0);
}

/* ✅ 正确: WSS 指数退避重连 */
static void good_wss_reconnect(void)
{
    uint32_t delay = 1000;
    const uint32_t max_delay = 60000;

    while (1) {
        int ret = wss_connect(url);
        if (ret == 0) {
            break;
        }
        LOG_W(TAG, "WSS connect failed, retry in %ums", delay);
        vTaskDelay(pdMS_TO_TICKS(delay));
        delay = (delay * 2 > max_delay) ? max_delay : delay * 2;
    }
}
