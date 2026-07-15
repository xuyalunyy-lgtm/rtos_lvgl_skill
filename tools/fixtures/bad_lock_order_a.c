extern void xSemaphoreTake(void *lock, int timeout);
extern void xSemaphoreGive(void *lock);
extern void *g_lock_a;
extern void *g_lock_b;

/* lock_order: g_lock_a -> g_lock_b */
void worker_a_then_b(void)
{
    xSemaphoreTake(g_lock_a, 10);
    xSemaphoreTake(g_lock_b, 10);
    xSemaphoreGive(g_lock_b);
    xSemaphoreGive(g_lock_a);
}
