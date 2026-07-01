/**
 * @file bad_stack_alloc.c
 * @brief C7.3 栈分配 self-test 反例 fixture
 */
#include <stdint.h>

/* 反例 C7.3: 证书缓冲区放栈上 */
void bad_tls_connect(void)
{
    char root_ca_pem[2048] = {0};  /* 证书链放栈上 */
    char client_cert[4096] = {0};  /* 客户端证书放栈上 */
    root_ca_pem[0] = 0;
}

/* 反例 C7.3: 大 buffer 放栈上 */
void bad_parse_json(void)
{
    char json_buffer[4096] = {0};  /* 大 JSON 缓冲区放栈上 */
    json_buffer[0] = 0;
}
