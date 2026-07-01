/* Bad state machine: _task without state enum, switch without default */
static void app_task(void *arg) {
    int state = 0;
    while (1) {
        switch (state) {
        case 0:
            state = 1;
            break;
        case 1:
            state = 0;
            break;
        }
    }
}
