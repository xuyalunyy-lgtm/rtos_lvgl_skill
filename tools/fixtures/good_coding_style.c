/* Good coding style: short function, ASCII filename */
#include <stdio.h>

static int add_numbers(int a, int b) {
    int result = a + b;
    if (result < 0) {
        return 0;
    }
    return result;
}

void print_result(int val) {
    printf("val=%d\n", val);
}
