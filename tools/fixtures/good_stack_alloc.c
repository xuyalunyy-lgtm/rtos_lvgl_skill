/**
 * @file good_stack_alloc.c
 * @brief C7.3 栈分配 self-test 正例 fixture
 */
#include <stdint.h>
#include <stdlib.h>

void good_parse_json(const char *json)
{
    /* 正例: 小缓冲区放栈上 */
    char tag[32] = {0};
    tag[0] = 'a';

    /* 正例: 大缓冲区用堆分配 */
    char *buf = malloc(1024);
    if (buf == NULL) return;
    buf[0] = 0;
    free(buf);
}
