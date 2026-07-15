void ble_start_bad(void)
{
    bt_enable(0);
    bt_conn_le_create(0, 0, 0, 0);
    int mtu = 247;
    (void)mtu;
}
