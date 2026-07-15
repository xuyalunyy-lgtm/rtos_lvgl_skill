void HAL_UART_RxCpltCallback(void)
{
    xQueueSendFromISR(queue, &event, &woken);
}

void jl_start(void)
{
    thread_fork("worker", 10, 1024, 0, worker, 0);
}

void bk_start(void)
{
    rtos_create_thread(&thread, 5, "worker", worker, 2048, 0);
}
