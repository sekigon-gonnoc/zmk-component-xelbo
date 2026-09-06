/*
 * Copyright (c) 2026 sekigon-gonnoc
 *
 * SPDX-License-Identifier: MIT
 */

#define DT_DRV_COMPAT zmk_ws2812_gpio

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#if IS_ENABLED(CONFIG_XELBO_GPIO_LED_TO_WS2812)
#include <zephyr/drivers/led_strip.h>
#endif

LOG_MODULE_REGISTER(gpio_ws2812, CONFIG_GPIO_LOG_LEVEL);

#define WS2812_GPIO_RED_PIN 0U
#define WS2812_GPIO_GREEN_PIN 1U
#define WS2812_GPIO_BLUE_PIN 2U
#define WS2812_GPIO_PIN_MASK GENMASK(WS2812_GPIO_BLUE_PIN, WS2812_GPIO_RED_PIN)

struct ws2812_gpio_config {
  struct gpio_driver_config common;
#if IS_ENABLED(CONFIG_XELBO_GPIO_LED_TO_WS2812)
  const struct device *strip;
#endif
};

struct ws2812_gpio_data {
  struct gpio_driver_data common;
  struct k_mutex lock;
  gpio_port_value_t state;
};

static int ws2812_gpio_apply(const struct device *port) {
#if IS_ENABLED(CONFIG_XELBO_GPIO_LED_TO_WS2812)
  const struct ws2812_gpio_config *config = port->config;
  const struct ws2812_gpio_data *data = port->data;
  const uint8_t brightness = CONFIG_XELBO_GPIO_LED_BRIGHTNESS;
  struct led_rgb pixel = {
      .r = (data->state & BIT(WS2812_GPIO_RED_PIN)) ? brightness : 0U,
      .g = (data->state & BIT(WS2812_GPIO_GREEN_PIN)) ? brightness : 0U,
      .b = (data->state & BIT(WS2812_GPIO_BLUE_PIN)) ? brightness : 0U,
  };

  return led_strip_update_rgb(config->strip, &pixel, 1U);
#else
  ARG_UNUSED(port);
  return 0;
#endif
}

static int ws2812_gpio_update(const struct device *port, gpio_port_pins_t mask,
                              gpio_port_value_t value) {
  struct ws2812_gpio_data *data = port->data;
  int err;

  if (k_is_in_isr()) {
    return -EWOULDBLOCK;
  }

  mask &= WS2812_GPIO_PIN_MASK;
  value &= mask;

  k_mutex_lock(&data->lock, K_FOREVER);
  data->state = (data->state & ~mask) | value;
  err = ws2812_gpio_apply(port);
  k_mutex_unlock(&data->lock);

  return err;
}

static int ws2812_gpio_pin_configure(const struct device *port, gpio_pin_t pin,
                                     gpio_flags_t flags) {
  gpio_port_pins_t mask = BIT(pin);

  if (pin > WS2812_GPIO_BLUE_PIN) {
    return -EINVAL;
  }

  if ((flags & GPIO_OUTPUT) == 0U || (flags & GPIO_INPUT) != 0U ||
      (flags & (GPIO_PULL_UP | GPIO_PULL_DOWN | GPIO_SINGLE_ENDED)) != 0U) {
    return -ENOTSUP;
  }

  if ((flags & GPIO_OUTPUT_INIT_HIGH) != 0U) {
    return ws2812_gpio_update(port, mask, mask);
  }

  if ((flags & GPIO_OUTPUT_INIT_LOW) != 0U) {
    return ws2812_gpio_update(port, mask, 0U);
  }

  return 0;
}

static int ws2812_gpio_port_get_raw(const struct device *port,
                                    gpio_port_value_t *value) {
  struct ws2812_gpio_data *data = port->data;

  if (k_is_in_isr()) {
    return -EWOULDBLOCK;
  }

  k_mutex_lock(&data->lock, K_FOREVER);
  *value = data->state;
  k_mutex_unlock(&data->lock);

  return 0;
}

static int ws2812_gpio_port_set_masked_raw(const struct device *port,
                                           gpio_port_pins_t mask,
                                           gpio_port_value_t value) {
  return ws2812_gpio_update(port, mask, value);
}

static int ws2812_gpio_port_set_bits_raw(const struct device *port,
                                         gpio_port_pins_t pins) {
  return ws2812_gpio_update(port, pins, pins);
}

static int ws2812_gpio_port_clear_bits_raw(const struct device *port,
                                           gpio_port_pins_t pins) {
  return ws2812_gpio_update(port, pins, 0U);
}

static int ws2812_gpio_port_toggle_bits(const struct device *port,
                                        gpio_port_pins_t pins) {
  struct ws2812_gpio_data *data = port->data;
  int err;

  if (k_is_in_isr()) {
    return -EWOULDBLOCK;
  }

  pins &= WS2812_GPIO_PIN_MASK;

  k_mutex_lock(&data->lock, K_FOREVER);
  data->state ^= pins;
  err = ws2812_gpio_apply(port);
  k_mutex_unlock(&data->lock);

  return err;
}

static int ws2812_gpio_pin_interrupt_configure(const struct device *port,
                                               gpio_pin_t pin,
                                               enum gpio_int_mode mode,
                                               enum gpio_int_trig trig) {
  ARG_UNUSED(port);
  ARG_UNUSED(pin);
  ARG_UNUSED(mode);
  ARG_UNUSED(trig);

  return -ENOTSUP;
}

static int ws2812_gpio_init(const struct device *port) {
  struct ws2812_gpio_data *data = port->data;
  int err;

  k_mutex_init(&data->lock);
  data->state = 0U;

#if IS_ENABLED(CONFIG_XELBO_GPIO_LED_TO_WS2812)
  const struct ws2812_gpio_config *config = port->config;

  if (!device_is_ready(config->strip)) {
    LOG_ERR("LED strip device %s is not ready", config->strip->name);
    return -ENODEV;
  }

  err = ws2812_gpio_apply(port);
  if (err != 0) {
    LOG_ERR("Initial WS2812 update failed: %d", err);
    return err;
  }

  LOG_INF("WS2812 GPIO adapter ready: strip %s, brightness %d",
          config->strip->name, CONFIG_XELBO_GPIO_LED_BRIGHTNESS);
  return 0;
#else
  ARG_UNUSED(err);
  return 0;
#endif
}

static DEVICE_API(gpio, ws2812_gpio_api) = {
    .pin_configure = ws2812_gpio_pin_configure,
    .port_get_raw = ws2812_gpio_port_get_raw,
    .port_set_masked_raw = ws2812_gpio_port_set_masked_raw,
    .port_set_bits_raw = ws2812_gpio_port_set_bits_raw,
    .port_clear_bits_raw = ws2812_gpio_port_clear_bits_raw,
    .port_toggle_bits = ws2812_gpio_port_toggle_bits,
    .pin_interrupt_configure = ws2812_gpio_pin_interrupt_configure,
};

#if IS_ENABLED(CONFIG_XELBO_GPIO_LED_TO_WS2812)
#define WS2812_GPIO_STRIP(inst)                                                \
  .strip = DEVICE_DT_GET(DT_INST_PHANDLE(inst, led_strip)),
#else
#define WS2812_GPIO_STRIP(inst)
#endif

#define WS2812_GPIO_DEVICE(inst)                                               \
  static const struct ws2812_gpio_config ws2812_gpio_config_##inst = {         \
      .common = {.port_pin_mask = WS2812_GPIO_PIN_MASK},                       \
      WS2812_GPIO_STRIP(inst)};                                                \
  static struct ws2812_gpio_data ws2812_gpio_data_##inst;                      \
  DEVICE_DT_INST_DEFINE(inst, ws2812_gpio_init, NULL,                          \
                        &ws2812_gpio_data_##inst, &ws2812_gpio_config_##inst,  \
                        POST_KERNEL, CONFIG_XELBO_GPIO_LED_INIT_PRIORITY,      \
                        &ws2812_gpio_api);

DT_INST_FOREACH_STATUS_OKAY(WS2812_GPIO_DEVICE)
