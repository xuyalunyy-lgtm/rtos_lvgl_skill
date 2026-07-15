void network_ready(void)
{
    esp_wifi_connect();
    esp_mqtt_client_start(0);
    esp_mqtt_client_subscribe(0, "device/status", 0);
}

void camera_ready(void)
{
    esp_camera_init(0);
    camera_capture_start();
}
