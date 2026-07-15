typedef enum { BLE_IDLE, BLE_CONNECTING, BLE_CONNECTED, BLE_DISCONNECTING } ble_state_t;
static ble_state_t s_ble_state;

void ble_start(void)
{
    bt_enable(0);
    s_ble_state = BLE_CONNECTING;
    bt_conn_le_create(0, 0, 0, 0);
    ble_gattc_exchange_mtu(0, 0, 0);
}

void ble_stop(void)
{
    s_ble_state = BLE_DISCONNECTING;
    bt_disable();
    s_ble_state = BLE_IDLE;
}
