#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"

#define SERVOPIN 16                             // Servo Pin

uint16_t wrap = 50000;                          // when to rollover, must be less than 65535
uint16_t PWMDIV = 60;                           // how much to divide the clock frequency by, must be between 1 and 255

#define DUTY_MIN 480                            // (480 us) See: https://daniel.springwald.de/post/2023/RCServoCheatSheet
#define DUTY_MAX 2400                           // (2400 us)
#define UPDATE_RATE_MS 1000                      // Update motor every 1s

uint16_t current_pwm_level = DUTY_MIN;          // Start at 0 degrees
uint16_t duty_cycle = 0;                       // Duty cycle to set for the PWM
float pwm_freq = 0;                           // PWM frequency in Hz
    
bool timer_callback(struct repeating_timer *t) {
    // Flip the PWM logic back and forth depending on current position:
    // Feedforward Control for (0 to 180) for corresponding servo motor:
    if(current_pwm_level == DUTY_MIN) { 
        current_pwm_level = DUTY_MAX;
    }
    else {
        current_pwm_level = DUTY_MIN;
    }

    // Update the PWM duty cycle based on the current position:
    pwm_freq = 150000000 / (wrap * PWMDIV); // Calculate the PWM frequency in Hz (50Hz)
    duty_cycle = (current_pwm_level * wrap) / (1000000 / pwm_freq); // Convert from microseconds to duty cycle (Flips from 2.4% to 12% for 0 to 180 degrees)

    // Set the pwm level based on current state:
    pwm_set_gpio_level(SERVOPIN, duty_cycle);
    return true;
}

int init_system(void) {
    // Set the Servo Pin to PWM Control
    gpio_set_function(SERVOPIN, GPIO_FUNC_PWM); // Set the Servo Pin to be PWM
    return PICO_OK;
}

int main()
{
    // Initialize stdio and system:
    stdio_init_all();
    init_system();

    // Turn on the PWM Servo:
    uint slice_num = pwm_gpio_to_slice_num(SERVOPIN); // Get PWM slice number
    // the clock frequency is 150MHz divided by a float from 1 to 255
    pwm_set_clkdiv(slice_num, PWMDIV); // sets the clock speed
    // set the PWM frequency and resolution
    // this sets the PWM frequency to 150MHz / div / wrap = 50Hz (For Servo Motor Control)
    pwm_set_wrap(slice_num, wrap);
    pwm_set_enabled(slice_num, true); // turn on the PWMs

    // Timer callback to change Servo Position every 1 second:
    struct repeating_timer timer;
    // Call every 1 second to update SERVO Position:
    add_repeating_timer_ms(UPDATE_RATE_MS, timer_callback, NULL, &timer);
    
    while (true) {
        // Do nothing in the main loop, all the work is done in the timer callback.
            // Servo should alternate back and forth every second between 0 and 180 degrees.
        tight_loop_contents();
    }
}