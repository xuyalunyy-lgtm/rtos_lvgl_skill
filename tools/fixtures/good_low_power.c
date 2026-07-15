typedef int esp_err_t;
typedef int nvs_handle_t;
esp_err_t nvs_set_u8(nvs_handle_t handle, const char *key, unsigned value);
esp_err_t nvs_commit(nvs_handle_t handle);
int esp_wifi_stop(void);
void esp_deep_sleep_start(void);

void enter_sleep(nvs_handle_t handle)
{
    (void)nvs_set_u8(handle, "sleep", 1);
    (void)nvs_commit(handle);
    (void)esp_wifi_stop();
    esp_deep_sleep_start();
}
