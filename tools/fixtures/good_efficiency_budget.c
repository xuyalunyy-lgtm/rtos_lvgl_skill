typedef struct {
    int frame_id;
    void *handle;
} frame_desc_t;

typedef void *QueueHandle_t;
int pdMS_TO_TICKS(int ms);
int xQueueSend(QueueHandle_t q, const void *item, int timeout);
QueueHandle_t xQueueCreate(int depth, int item_size);

static QueueHandle_t s_frame_q;
static int drop_oldest_count;
static int copy_count;

void good_efficiency_budget(void)
{
    frame_desc_t desc = {0};

    /* C36: descriptor only; copy_count=0; producer owns pool, consumer release. */
    s_frame_q = xQueueCreate(8, sizeof(frame_desc_t));

    if (xQueueSend(s_frame_q, &desc, pdMS_TO_TICKS(5)) != 1) {
        drop_oldest_count++;
    }

    copy_count += 0;
}
