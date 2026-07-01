/* Good board resource: gpio_set_level with matching gpio_config */
#include <stdint.h>

typedef int gpio_num_t;
#define GPIO_NUM_2 2

int gpio_config(const void *cfg);
int gpio_set_level(gpio_num_t gpio_num, uint32_t level);

void init_led(void) {
    gpio_set_level(GPIO_NUM_2, 1);
    gpio_config(&(int){0, .pin_bit_mask = (1ULL << GPIO_NUM_2), 0});
}
