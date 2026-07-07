# FreeRTOS Quick Guide

- Task creation: `xTaskCreate` / `xTaskCreatePinnedToCore`
- Synchronization: `xSemaphore`, `xQueue`, `EventGroup`
- Heap checks: `uxTaskGetSystemState`, stack watermark
- ISR boundary: no blocking calls in ISRs, use `FromISR` APIs
