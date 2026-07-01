/* Bad: APP_TEST_MODE_ macro defined outside app_test_config.h */
#include <stdio.h>

#ifdef APP_TEST_MODE_SENSOR
void sensor_test(void) {
    printf("sensor test\n");
}
#endif

void normal_func(void) {
    printf("normal\n");
}
