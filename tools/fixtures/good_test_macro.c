/* Good: no APP_TEST_MODE_ macros outside app_test_config.h */
#include <stdio.h>

#define MY_MODULE_ENABLED 1

void run_feature(void) {
    int x = 42;
    printf("result: %d\n", x);
}
