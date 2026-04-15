#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "pico/cyw43_arch.h"
#include "ssd1306_Library/ssd1306.h"
#include "hardware/adc.h"

// I2C defines
// This example will use I2C0 on GPIO8 (SDA) and GPIO9 (SCL) running at 400KHz.
// Pins can be changed, see the GPIO function select table in the datasheet for information on GPIO assignments
#define I2C_PORT i2c0
#define I2C_SDA 8
#define I2C_SCL 9

#define ACDCPin 26       // ACD0 Pin

int init_system(void) {
    // Set the ACDC0 Pin to 
    adc_init();
    adc_select_input(0);
    adc_gpio_init(ACDCPin);
    return PICO_OK;
}

double readACD() {
    // Read in the ACD pin:
    double value = 0.0;
    return value;
}

int main()
{   
    // Initialize the system:
    stdio_init_all();
    init_system();

    // I2C Initialisation. Using it at 400Khz.
    i2c_init(I2C_PORT, 400*1000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);

    // Initialize the Wi-Fi module
    if (cyw43_arch_init()) {
        return -1;
    }

    // Initialize the ssd306:
    ssd1306_setup();

    // Determine when the Pico2 W was turned on:
    unsigned int start_t = to_us_since_boot(get_absolute_time()); 
    // Create counter to toggle LED:
    unsigned int LED_t = 0; 
    uint8_t toggle = 0;

    while (true) {
        // Save the start time:
        unsigned int frame_start = start_t;

        // I2C Communication Pipeline for OLED Screen:
        char line1[26]; 
        char line2[26];
        char line3[26];
        char line4[26];

        // Custom message for lines 1 and 2:
        sprintf(line1, "Nolan Knights OLED Screen"); 
        sprintf(line2, "(0_0) LOADING..........."); 

        // Read and print the ACD0 input value: (Currently noise)
        uint16_t ADC_Val = adc_read();
        sprintf(line3, "ACD0 Scan: %d", ADC_Val);

        // Determine the FPS and print to the screen:
        unsigned int end_t = to_us_since_boot(get_absolute_time()); 
        double fps = 1000000 / (double)(end_t - start_t);
        sprintf(line4, "Screen FPS: %.2f", fps);
        // Update start time: 
        start_t = to_us_since_boot(get_absolute_time()); 

        // Draw the lines and update the message:
        ssd1306_drawMessage(0,0,line1); // Draw the first line at (0,0)
        ssd1306_drawMessage(0,8, line2); // Draw the second line at (8,0)
        ssd1306_drawMessage(0,16,line3); // Draw the third line at (16,0)
        ssd1306_drawMessage(0,24, line4); // Draw the fourth line at (24,0)
        ssd1306_update();

        // Toggle the LED based on Current Time_stamp:
        LED_t += (fps);
        if (LED_t > 350) {
            cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, toggle);
            // Flip the toggle:
            if (toggle == 0) {
                toggle = 1; 
            }
            else {
                toggle = 0;
            }
            // Reset LED_t 
            LED_t = 0;
        }
        
        // Update start frame: 
        start_t = end_t;

        // Clear previous Message: 
        ssd1306_clear();
    }
}
