#include "ui_view.h"
#include "presenter_main.h"
#include "network_wss_private.h"

void lv_label_set_text(void *label, const char *text);
void network_wss_private_set_state(int state);

void driver_sensor_irq_callback(void *label)
{
    network_wss_private_set_state(1);
    lv_label_set_text(label, "sample ready");
}
