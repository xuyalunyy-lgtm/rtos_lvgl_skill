typedef int esp_err_t;
typedef int nvs_handle_t;
#define ESP_OK 0
esp_err_t nvs_set_u8(nvs_handle_t handle, const char *key, unsigned value);
extern esp_err_t (*nvs_commit)(nvs_handle_t handle);

int save_counter(nvs_handle_t handle, unsigned value)
{
    esp_err_t err = nvs_set_u8(handle, "counter", value);
    if (err != ESP_OK)
        return -1;
    err = nvs_commit(handle);
    if (err != ESP_OK)
        return -1;
    return 0;
}
