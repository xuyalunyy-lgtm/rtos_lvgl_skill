/* Good state machine: has named enum state + switch default */
enum app_state {
    STATE_IDLE = 0,
    STATE_RUNNING = 1,
    STATE_ERROR = 2,
};

static void app_task(void *arg) {
    enum app_state state = STATE_IDLE;
    while (1) {
        switch (state) {
        case STATE_IDLE:
            state = STATE_RUNNING;
            break;
        case STATE_RUNNING:
            state = STATE_IDLE;
            break;
        default:
            state = STATE_IDLE;
            break;
        }
    }
}
