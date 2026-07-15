extern void *g_shared_queue;

void app_resources_deinit(void)
{
    vQueueDelete(g_shared_queue);
    g_shared_queue = 0;
}
