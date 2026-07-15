static int reconnect_once(void);
static void mark_transport_offline(void);

void recover_transport(void)
{
    for (int attempt = 0; attempt < 3; ++attempt) {
        if (reconnect_once() == 0) {
            return;
        }
    }
    mark_transport_offline();
}
