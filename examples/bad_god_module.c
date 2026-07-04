#include "ui_view.h"
#include "network_wss.h"
#include "storage_nvs.h"
#include "audio_i2s.h"
#include "gpio_driver.h"

typedef struct {
    int ui_state;
    int net_state;
    int audio_state;
} app_context_t;

app_context_t g_app_ctx;

void lv_label_set_text(void *label, const char *text);
void network_wss_send(const char *text);
void storage_nvs_write(const char *key, const char *value);
void audio_i2s_start(void);
void gpio_set_led(int on);

void network_god_tick(void *label)
{
    lv_label_set_text(label, "online");
    network_wss_send("ping");
    storage_nvs_write("last_state", "online");
    audio_i2s_start();
    gpio_set_led(1);
    g_app_ctx.net_state = 1;
}
