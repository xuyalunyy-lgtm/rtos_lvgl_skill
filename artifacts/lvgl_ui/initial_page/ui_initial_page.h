#ifndef UI_INITIAL_PAGE_H
#define UI_INITIAL_PAGE_H

#include "lvgl.h"
#include <stdint.h>

typedef enum {
    UI_INITIAL_PAGE_STATE_INIT = 0,
    UI_INITIAL_PAGE_STATE_READY,
    UI_INITIAL_PAGE_STATE_ERROR,
} ui_initial_page_state_t;

extern uint32_t UI_INITIAL_PAGE_EVENT_SERVER_UPDATE;

lv_obj_t *ui_initial_page_create(lv_obj_t *parent);
void ui_initial_page_destroy(void);
void ui_initial_page_set_state(ui_initial_page_state_t state);
void ui_initial_page_post_server_update(void *payload);

#endif /* UI_INITIAL_PAGE_H */
