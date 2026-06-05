#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include <math.h>

// I2C defines
// This example will use I2C0 on GPIO8 (SDA) and GPIO9 (SCL) running at 400KHz.
// Pins can be changed, see the GPIO function select table in the datasheet for information on GPIO assignments
#define I2C_PORT i2c0
#define I2C_SDA 16
#define I2C_SCL 17
#define ENCODER_ADDR 0x36

// Define GPIO Pins for Clock and Data for Amplifier: 
#define amp_clk 2
#define amp_data 3

// IIR filter coefficient: 
// output = alpha*new + (1-alpha)*prev
#define IIR_ALPHA 0.10f

#define DEG_MULTIPLIER (360.0f / 4096.0f) 

uint16_t encoder_read_angle() {
    uint8_t reg = 0x0C; // 
    uint8_t buf[2];

    i2c_write_blocking(I2C_PORT, ENCODER_ADDR, &reg, 1, true);
    i2c_read_blocking(I2C_PORT, ENCODER_ADDR, buf, 2, false);

    uint16_t angle = (buf[0] << 8) | buf[1];

    return angle;
}

float to_degrees(uint16_t raw_value) {
    return (float)raw_value * DEG_MULTIPLIER;
}

float to_radians(uint16_t raw_value) {
    return ((float)raw_value / 4096.0f) * (2.0f * M_PI);
}


// Initialize HX711 GPIO pins
void initHX711() {
    // Initialize the clock to be output and start off:
    gpio_init(amp_clk);
    gpio_set_dir(amp_clk, GPIO_OUT);
    gpio_put(amp_clk, 0);  
    
    // Initialize the data pin to input:
    gpio_init(amp_data);
    gpio_set_dir(amp_data, GPIO_IN);
    gpio_pull_up(amp_data);
}

// Read one 24-bit sample from the HX711.
int32_t readHX711() {
    // Wait until DT goes LOW:
    while (gpio_get(amp_data) == 1) {
        tight_loop_contents();
    }
 
    uint32_t raw = 0;
    // Read in 24 bits and convert to signed int:
    for (int i = 0; i < 25; i++) {
        gpio_put(amp_clk, 1);
        sleep_us(1);
 
        if (i < 24) {
            // Read DT on the HIGH phase of each of the first 24 clocks:
            raw = (raw << 1) | gpio_get(amp_data);
        }
        
        // turn the clock back off:
        gpio_put(amp_clk, 0);
        sleep_us(1);
    }
 
    // sign-extend 24-bit two's complement to 32-bit signed int
    if (raw & 0x800000) {
        raw |= 0xFF000000;
    }
    return (int32_t)raw;
}

int main()
{
    stdio_init_all();
    
    // Wait for USB serial to connect:
    while (!stdio_usb_connected()) {
        tight_loop_contents();
    }
    sleep_ms(500);
    
    // Init HX711 pins:
    initHX711();

    // I2C Initialisation. Using it at 400Khz.
    i2c_init(I2C_PORT, 400*1000);
    
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);

    // Read first two Sensor value for filter init:
    int32_t sample_m1 = readHX711(); 
    int32_t sample_0 = readHX711();
    float filtered_force = IIR_ALPHA * (float)sample_0 + (1.0f - IIR_ALPHA) * sample_m1;

    while (true) {
        // Read in the Force Sensor Data:
        int32_t sample = readHX711();
        filtered_force = IIR_ALPHA * (float)sample + (1.0f - IIR_ALPHA) * filtered_force;

        // Read in the Encoder Values:
        uint16_t encoder = encoder_read_angle();
        encoder = to_degrees(encoder);

        // Print out the Sensor and Encoder Values: 
        printf("Output: %.2f %.1d \n", filtered_force, encoder);
    
    }
}
