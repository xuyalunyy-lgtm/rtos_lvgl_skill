void init_sensor(void)
{
    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(i2c0));
    if (!device_is_ready(dev)) {
        return;
    }
    i2c_configure(dev, 0);
}

void work_handler(struct k_work *work)
{
    process_event(work);
}

K_WORK_DEFINE(sensor_work, work_handler);
