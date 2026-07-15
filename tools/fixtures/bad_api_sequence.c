void bad_network_ready(void)
{
    esp_mqtt_client_subscribe(0, "device/status", 0);
    esp_mqtt_client_start(0);
    esp_wifi_connect();
}

void bad_camera_ready(void)
{
    camera_capture_start();
    esp_camera_init(0);
}
