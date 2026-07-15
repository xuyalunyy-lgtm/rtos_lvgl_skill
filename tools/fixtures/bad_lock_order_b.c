extern void xSemaphoreTake(void *lock, int timeout);
extern void xSemaphoreGive(void *lock);
extern void *g_lock_a;
extern void *g_lock_b;

/* lock_order: g_lock_b -> g_lock_a */
void worker_b_then_a(void)
{
    xSemaphoreTake(g_lock_b, 10);
    xSemaphoreTake(g_lock_a, 10);
    xSemaphoreGive(g_lock_a);
    xSemaphoreGive(g_lock_b);
}
