// C34 bad: hot path contains forbidden operations
#include "FreeRTOS.h"
#include "task.h"
#include "cJSON.h"
#include <stdio.h>
#include <stdlib.h>

// LVGL flush callback — has malloc and printf (C34.1, C34.2)
static void my_lvgl_flush(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    uint8_t *buf = malloc(1024);  // C34.1: malloc in hot path
    printf("flush called\n");     // C34.2: printf in hot path
    memcpy(buf, px_map, 1024);
    free(buf);                     // C34.1: free in hot path
}

// Audio decode callback — has cJSON_Parse and portMAX_DELAY (C34.3, C34.4)
static void audio_decode_cb(void *data, size_t len)
{
    cJSON *json = cJSON_Parse((char *)data);  // C34.4: cJSON parse in hot path
    xSemaphoreTake(mutex, portMAX_DELAY);     // C34.3: portMAX_DELAY in hot path
    if (json) {
        cJSON_Delete(json);
    }
}

// ISR handler — has printf (C34.2)
void SPI0_IRQHandler(void)
{
    printf("SPI interrupt\n");  // C34.2: printf in ISR
}
