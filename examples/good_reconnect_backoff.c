/**
 * @file good_reconnect_backoff.c
 * @brief C20 网络韧性正例：指数退避 + 超时 + DNS fallback
 *
 * 约束覆盖：
 *   C20.1 — WiFi/WSS 断线重连必须有指数退避
 *   C20.2 — 所有阻塞网络操作必须有有限超时
 *   C20.3 — DNS 解析失败必须处理
 */

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

static const char *TAG = "reconnect";

#define RECONNECT_BASE_MS   1000
#define RECONNECT_MAX_MS    60000
#define CONNECT_TIMEOUT_S   10

/**
 * @brief C20.1 — 指数退避重连
 */
esp_err_t good_wifi_reconnect(void)
{
    int retry = 0;
    int delay_ms = RECONNECT_BASE_MS;

    while (retry < 10) {
        ESP_LOGI(TAG, "WiFi reconnect attempt %d (delay=%dms)", retry + 1, delay_ms);

        esp_err_t err = esp_wifi_connect();
        if (err == ESP_OK) {
            ESP_LOGI(TAG, "WiFi connected");
            return ESP_OK;
        }

        /* C20.1: 指数退避，cap 在 60s */
        vTaskDelay(pdMS_TO_TICKS(delay_ms));
        delay_ms = delay_ms * 2;
        if (delay_ms > RECONNECT_MAX_MS) {
            delay_ms = RECONNECT_MAX_MS;
        }
        retry++;
    }

    ESP_LOGE(TAG, "WiFi reconnect failed after %d retries", retry);
    return ESP_FAIL;
}

/**
 * @brief C20.2 + C20.3 — 带超时的 DNS + 连接
 */
int good_tcp_connect(const char *host, int port)
{
    /* C20.3: DNS 解析 + 错误处理 */
    struct addrinfo hints = {
        .ai_family = AF_INET,
        .ai_socktype = SOCK_STREAM,
    };
    struct addrinfo *result = NULL;
    char port_str[8];
    snprintf(port_str, sizeof(port_str), "%d", port);

    int err = getaddrinfo(host, port_str, &hints, &result);
    if (err != 0 || result == NULL) {
        ESP_LOGE(TAG, "DNS resolution failed for %s: %d", host, err);
        return -1;
    }

    int sock = socket(result->ai_family, result->ai_socktype, 0);
    if (sock < 0) {
        ESP_LOGE(TAG, "Socket creation failed");
        freeaddrinfo(result);
        return -1;
    }

    /* C20.2: 设置连接超时 */
    struct timeval tv = {
        .tv_sec = CONNECT_TIMEOUT_S,
        .tv_usec = 0,
    };
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    /* 连接 */
    if (connect(sock, result->ai_addr, result->ai_addrlen) < 0) {
        ESP_LOGE(TAG, "Connection to %s:%d failed (timeout=%ds)", host, port, CONNECT_TIMEOUT_S);
        close(sock);
        freeaddrinfo(result);
        return -1;
    }

    freeaddrinfo(result);
    ESP_LOGI(TAG, "Connected to %s:%d", host, port);
    return sock;
}
