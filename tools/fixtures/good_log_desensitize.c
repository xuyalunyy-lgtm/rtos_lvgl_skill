/* Good logging: no sensitive keywords printed */
#include <stdio.h>

#define LOG_I(tag, fmt, ...) printf(fmt "\n", ##__VA_ARGS__)

void connect_wifi(const char *ssid) {
    LOG_I("wifi", "Connecting to %s", ssid);
    printf("Connection established\n");
}
