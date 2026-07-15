void portability_bug(void)
{
    xTaskCreate(worker, "worker", 1024, 0, 5, 0);
    k_thread_create(&thread, stack, 1024, worker, 0, 0, 0, 5, 0, K_NO_WAIT);
}
