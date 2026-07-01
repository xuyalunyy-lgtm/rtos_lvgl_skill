/* Bad board resource: gpio_set_level without gpio_config */
#include <stdint.h>

typedef int gpio_num_t;
#define GPIO_NUM_2 2
#define GPIO_NUM_4 4

int gpio_config(const void *cfg);
int gpio_set_level(gpio_num_t gpio_num, uint32_t level);

void blink_led(void) {
    gpio_set_level(GPIO_NUM_2, 1);
    gpio_set_level(GPIO_NUM_4, 0);
}
