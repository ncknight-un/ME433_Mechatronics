#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/sync.h"
#include <math.h>

#define I2C_PORT i2c0
#define I2C_SDA 16
#define I2C_SCL 17
#define ENCODER_ADDR 0x36

#define I2C1_PORT i2c1
#define I2C1_SDA 14
#define I2C1_SCL 15
#define INA219_ADDR 0x40

#define SCK_PIN 2
#define DT_PIN 3

#define MOTOR_IN1 18
#define MOTOR_IN2 19

#include "hardware/pwm.h"
#include "hardware/timer.h"

#define DEG_MULTIPLIER (360.0f / 4096.0f) 

void setup_i2c() {
    i2c_init(I2C_PORT, 400 * 1000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);

    i2c_init(I2C1_PORT, 400 * 1000);
    gpio_set_function(I2C1_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C1_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C1_SDA);
    gpio_pull_up(I2C1_SCL);
}

void hx711_init(void) {
    gpio_init(SCK_PIN);
    gpio_set_dir(SCK_PIN, GPIO_OUT);
    gpio_init(DT_PIN);
    gpio_set_dir(DT_PIN, GPIO_IN);
}

uint16_t encoder_read_angle() {
    uint8_t reg = 0x0C; // 
    uint8_t buf[2];

    i2c_write_blocking(I2C_PORT, ENCODER_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, ENCODER_ADDR, buf, 2, false);

    uint16_t angle = (buf[0] << 8) | buf[1];

    return angle;
}

int32_t hx711_read(void) {
    while (gpio_get(DT_PIN) == 1) {
        // wait until DT pin is low
    }
    
    // Disable interrupts to prevent the 1kHz timer from firing while SCK is high,
    // which would cause the HX711 to enter power-down mode (>60us SCK high).
    uint32_t ints = save_and_disable_interrupts();
    
    int32_t count = 0;
    for (int i = 0; i < 24; i++) {
        gpio_put(SCK_PIN, 1);
        busy_wait_us(1); // Small delay for clock to settle
        count = count << 1;
        if (gpio_get(DT_PIN)) {
            count++;
        }
        gpio_put(SCK_PIN, 0);
        busy_wait_us(1);
    }
    
    // 25th pulse for gain of 128
    gpio_put(SCK_PIN, 1);
    busy_wait_us(1);
    gpio_put(SCK_PIN, 0);
    busy_wait_us(1);
    
    restore_interrupts(ints);
    
    // sign-extend 24-bit two's complement to 32-bit signed int
    if (count & 0x800000) { 
        count |= 0xFF000000; 
    }
    return count;
}

float to_degrees(uint16_t raw_value) {
    return (float)raw_value * DEG_MULTIPLIER;
}

float to_radians(uint16_t raw_value) {
    return ((float)raw_value / 4096.0f) * (2.0f * M_PI);
}

// ==========================================
// MOTOR & HAPTICS CONTROL
// ==========================================

void setup_motor() {
    gpio_set_function(MOTOR_IN1, GPIO_FUNC_PWM);
    gpio_set_function(MOTOR_IN2, GPIO_FUNC_PWM);
    uint slice_num = pwm_gpio_to_slice_num(MOTOR_IN1);
    pwm_set_wrap(slice_num, 6249); // 125MHz / 20kHz = 6250
    pwm_set_chan_level(slice_num, PWM_CHAN_A, 0);
    pwm_set_chan_level(slice_num, PWM_CHAN_B, 0);
    pwm_set_enabled(slice_num, true);
}

void set_motor_duty(int32_t duty) {
    uint slice_num = pwm_gpio_to_slice_num(MOTOR_IN1);
    if (duty > 6249) duty = 6249;
    if (duty < -6249) duty = -6249;

    if (duty >= 0) {
        pwm_set_gpio_level(MOTOR_IN1, duty);
        pwm_set_gpio_level(MOTOR_IN2, 0);
    } else {
        pwm_set_gpio_level(MOTOR_IN1, 0);
        pwm_set_gpio_level(MOTOR_IN2, -duty);
    }
}

int16_t read_current_sensor() {
    uint8_t reg = 0x01; // Shunt voltage for INA219, Current for INA260
    uint8_t buf[2];
    int w_ret = i2c_write_timeout_us(I2C1_PORT, INA219_ADDR, &reg, 1, true, 2000);
    if (w_ret < 0) return 0; // Prevent hanging if sensor disconnected
    int r_ret = i2c_read_timeout_us(I2C1_PORT, INA219_ADDR, buf, 2, false, 2000);
    if (r_ret < 0) return 0;
    return (int16_t)((buf[0] << 8) | buf[1]);
}

volatile char haptic_state = 'C';
volatile int bump_timer = 0;
volatile float current_error_integral = 0.0f;

void update_haptic_state() {
    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) {
        if (c == 'C' || c == 'L' || c == 'R') {
            haptic_state = c;
        } else if (c == 'B') {
            bump_timer = 200; // 200ms vibration bump
        }
    }
}

bool motor_timer_callback(struct repeating_timer *t) {
    update_haptic_state();
    
    int16_t actual_current = read_current_sensor();
    
    float desired_current = 0.0f;
    if (bump_timer > 0) {
        bump_timer--;
        desired_current = (bump_timer % 20 < 10) ? 3000.0f : -3000.0f; // Vibrate
    } else {
        if (haptic_state == 'L') {
            desired_current = 8000.0f;  // Push right
        } else if (haptic_state == 'R') {
            desired_current = -8000.0f; // Push left
        } else {
            desired_current = 0.0f;    // Center
        }
    }
    
    // PI Controller
    float Kp = 5.0f; 
    float Ki = 0.1f;
    
    float error = desired_current - (float)actual_current;
    current_error_integral += error;
    
    // Anti-windup
    if (current_error_integral > 20000.0f) current_error_integral = 20000.0f;
    if (current_error_integral < -20000.0f) current_error_integral = -20000.0f;
    
    if (desired_current == 0.0f) {
        current_error_integral = 0.0f;
        set_motor_duty(0);
    } else {
        float duty_f = (Kp * error) + (Ki * current_error_integral);
        set_motor_duty((int32_t)duty_f);
    }
    
    return true; // Keep repeating
}

int main()
{
    stdio_init_all();
    setup_i2c();
    hx711_init();
    setup_motor();

    struct repeating_timer timer;
    add_repeating_timer_us(-1000, motor_timer_callback, NULL, &timer);

    float filter_val = 0.0f;
    bool is_first_sample = true;

    while (true) {
        uint16_t angle = encoder_read_angle();
        angle = to_degrees(angle);

        int32_t raw_force = hx711_read();

            if (is_first_sample) {
                filter_val = raw_force;
                is_first_sample = false;
            } else {
                filter_val = 0.9f * filter_val + 0.1f * raw_force;
            }

        int16_t current_val = read_current_sensor();
        printf("Angle: %u\t Force: %d\t State: %c\t Curr: %d\r\n", angle, (int)filter_val, haptic_state, current_val);
    }
}
