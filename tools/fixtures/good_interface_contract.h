#ifndef GOOD_INTERFACE_CONTRACT_H
#define GOOD_INTERFACE_CONTRACT_H

int sensor_configure(const char *name, unsigned int timeout_ms);
void sensor_shutdown(void);

#endif
