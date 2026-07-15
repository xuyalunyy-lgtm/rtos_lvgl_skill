void *g_shared_queue;

void app_resources_init(void)
{
    g_shared_queue = xQueueCreate(4, sizeof(int));
}
