typedef struct {
    unsigned char bytes[4096];
} video_frame_t;

typedef void *QueueHandle_t;
void *pvPortMalloc(unsigned int size);
void memcpy(void *dst, const void *src, unsigned int size);
int xQueueSend(QueueHandle_t q, const void *item, int timeout);
QueueHandle_t xQueueCreate(int depth, int item_size);
int reconnect_socket(void);
int send_packet(void);

#define portMAX_DELAY 0xffffffff

static QueueHandle_t s_video_q;

void bad_frame_process(video_frame_t *frame)
{
    video_frame_t *copy = pvPortMalloc(sizeof(video_frame_t));
    memcpy(copy, frame, sizeof(video_frame_t));
    xQueueSend(s_video_q, frame, portMAX_DELAY);
}

void bad_queue_create(void)
{
    s_video_q = xQueueCreate(4, sizeof(video_frame_t));
}

void bad_reconnect_loop(void)
{
    while (1) {
        reconnect_socket();
        send_packet();
    }
}
