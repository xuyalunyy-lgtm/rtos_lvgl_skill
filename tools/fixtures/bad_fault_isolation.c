static int reconnect_once(void);

void recover_transport(void)
{
    while (1) {
        reconnect_once();
    }
}
