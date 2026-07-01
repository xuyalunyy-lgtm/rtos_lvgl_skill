/* Bad logging: prints sensitive keywords with format specifiers */
#include <stdio.h>

#define LOG_I(tag, fmt, ...) printf(fmt "\n", ##__VA_ARGS__)

void login(const char *user, const char *pass) {
    LOG_I("auth", "password: %s", pass);
    printf("token: %s\n", "abc123");
}
