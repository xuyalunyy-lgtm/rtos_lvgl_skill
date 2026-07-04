#include "ui_view.h"
#include "network_wss.h"
#include "storage_nvs.h"
#include "audio_i2s.h"

typedef struct {
    int ui_state;
    int net_state;
} app_context_t;

app_context_t g_app_ctx;

void lv_label_set_text(void *label, const char *text);
void network_wss_send(const char *text);
void storage_nvs_write(const char *key, const char *value);
void audio_i2s_start(void);

void network_god_module_tick(void *label)
{
    lv_label_set_text(label, "online");
    network_wss_send("ping");
    storage_nvs_write("last_state", "online");
    audio_i2s_start();
    g_app_ctx.net_state = 1;
}
