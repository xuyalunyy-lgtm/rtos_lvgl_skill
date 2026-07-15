void *g_leaked_queue;

void app_resources_init(void)
{
    g_leaked_queue = xQueueCreate(4, sizeof(int));
}
