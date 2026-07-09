#include "ui_initial_page.h"

#include <stdbool.h>
#include <stdlib.h>

#if LVGL_VERSION_MAJOR >= 9
#define UI_IMAGE_CREATE      lv_image_create
#define UI_IMAGE_SET_SRC     lv_image_set_src
#define UI_OBJ_DELETE        lv_obj_delete
#else
#define UI_IMAGE_CREATE      lv_img_create
#define UI_IMAGE_SET_SRC     lv_img_set_src
#define UI_OBJ_DELETE        lv_obj_del
#endif

#ifndef UI_IMG_SRC_INITIAL_PAGE_BG
#define UI_IMG_SRC_INITIAL_PAGE_BG "S:/ui/initial_page_bg.jpg"
#endif

#ifndef UI_IMG_SRC_INITIAL_PAGE_PET
#define UI_IMG_SRC_INITIAL_PAGE_PET "S:/ui/initial_page_pet.png"
#endif

#define UI_INITIAL_PAGE_WIDTH 480
#define UI_INITIAL_PAGE_HEIGHT 800
#define UI_INITIAL_PAGE_PET_X 95
#define UI_INITIAL_PAGE_PET_Y 123
#define UI_INITIAL_PAGE_PET_W 305
#define UI_INITIAL_PAGE_PET_H 428

static lv_obj_t *s_page;
static lv_obj_t *s_bg;
static lv_obj_t *s_pet;
static ui_initial_page_state_t s_state = UI_INITIAL_PAGE_STATE_INIT;

uint32_t UI_INITIAL_PAGE_EVENT_SERVER_UPDATE;

#ifndef UI_ASYNC_ALLOC
#define UI_ASYNC_ALLOC malloc
#endif

#ifndef UI_ASYNC_FREE
#define UI_ASYNC_FREE free
#endif

#ifndef UI_ASYNC_CALL
#define UI_ASYNC_CALL(callback, data) lv_async_call((callback), (data))
#endif

typedef struct {
    uint32_t generation;
    void *payload;
} ui_initial_page_server_update_async_t;

static uint32_t s_generation;

static void ui_initial_page_custom_events_init(void)
{
    if (UI_INITIAL_PAGE_EVENT_SERVER_UPDATE == 0U) {
        UI_INITIAL_PAGE_EVENT_SERVER_UPDATE = lv_event_register_id();
    }
}

static void ui_initial_page_server_update_async_cb(void *user_data)
{
    ui_initial_page_server_update_async_t *msg = (ui_initial_page_server_update_async_t *)user_data;
    if (msg == NULL) {
        return;
    }
    if (s_page != NULL &&
        msg->generation == s_generation &&
        UI_INITIAL_PAGE_EVENT_SERVER_UPDATE != 0U) {
        lv_event_send(s_page, UI_INITIAL_PAGE_EVENT_SERVER_UPDATE, msg->payload);
    }
    UI_ASYNC_FREE(msg);
}

static void ui_initial_page_server_update_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    if ((uint32_t)code == UI_INITIAL_PAGE_EVENT_SERVER_UPDATE) {
        void *server_payload = lv_event_get_param(e);
        (void)server_payload;
        return;
    }
    if ((uint32_t)code > (uint32_t)LV_EVENT_LAST) {
        /* Project-specific custom events can be handled here on the LVGL/UI task. */
    }
}

void ui_initial_page_post_server_update(void *payload)
{
    ui_initial_page_server_update_async_t *msg = (ui_initial_page_server_update_async_t *)UI_ASYNC_ALLOC(sizeof(*msg));
    if (msg == NULL) {
        return;
    }
    msg->generation = s_generation;
    msg->payload = payload;
    UI_ASYNC_CALL(ui_initial_page_server_update_async_cb, msg);
}

void ui_initial_page_set_state(ui_initial_page_state_t state)
{
    switch (state) {
    case UI_INITIAL_PAGE_STATE_INIT:
    case UI_INITIAL_PAGE_STATE_READY:
    case UI_INITIAL_PAGE_STATE_ERROR:
        s_state = state;
        break;
    default:
        s_state = UI_INITIAL_PAGE_STATE_INIT;
        break;
    }
}

lv_obj_t *ui_initial_page_create(lv_obj_t *parent)
{
    if (s_page != NULL) {
        return s_page;
    }

    s_generation++;
    if (s_generation == 0U) {
        s_generation = 1U;
    }

    s_page = lv_obj_create(parent);
    lv_obj_set_size(s_page, UI_INITIAL_PAGE_WIDTH, UI_INITIAL_PAGE_HEIGHT);
    lv_obj_clear_flag(s_page, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_border_width(s_page, 0, 0);
    lv_obj_set_style_pad_all(s_page, 0, 0);
    lv_obj_set_style_bg_opa(s_page, LV_OPA_TRANSP, 0);

    ui_initial_page_custom_events_init();
    lv_obj_add_event_cb(s_page, ui_initial_page_server_update_cb, LV_EVENT_ALL, NULL);

    s_bg = UI_IMAGE_CREATE(s_page);
    UI_IMAGE_SET_SRC(s_bg, UI_IMG_SRC_INITIAL_PAGE_BG);
    /* LVGL_LAYOUT_EXCEPTION: full-screen supplied background cutout. */
    lv_obj_set_pos(s_bg, 0, 0);
    lv_obj_set_size(s_bg, UI_INITIAL_PAGE_WIDTH, UI_INITIAL_PAGE_HEIGHT);

    s_pet = UI_IMAGE_CREATE(s_page);
    UI_IMAGE_SET_SRC(s_pet, UI_IMG_SRC_INITIAL_PAGE_PET);
    /* LVGL_LAYOUT_EXCEPTION: pet cutout placement matches the generated initial page reference. */
    lv_obj_set_pos(s_pet, UI_INITIAL_PAGE_PET_X, UI_INITIAL_PAGE_PET_Y);
    lv_obj_set_size(s_pet, UI_INITIAL_PAGE_PET_W, UI_INITIAL_PAGE_PET_H);

    ui_initial_page_set_state(UI_INITIAL_PAGE_STATE_READY);

    return s_page;
}

void ui_initial_page_destroy(void)
{
    if (s_page != NULL) {
        s_generation++;
        if (s_generation == 0U) {
            s_generation = 1U;
        }
        UI_OBJ_DELETE(s_page);
        s_page = NULL;
        s_bg = NULL;
        s_pet = NULL;
        s_state = UI_INITIAL_PAGE_STATE_INIT;
    }
}
