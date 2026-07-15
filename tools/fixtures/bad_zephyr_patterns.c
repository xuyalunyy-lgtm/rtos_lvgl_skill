#define CONFIG_APPLICATION_WRONG_PLACE y

void init_sensor(void)
{
    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(i2c0));
    i2c_configure(dev, 0);
}

void work_handler(struct k_work *work)
{
    k_msleep(100);
}

K_WORK_DEFINE(sensor_work, work_handler);
