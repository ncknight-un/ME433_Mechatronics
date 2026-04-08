#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "pico/cyw43_arch.h"

// I2C defines
// This example will use I2C0 on GPIO8 (SDA) and GPIO9 (SCL) running at 400KHz.
// Pins can be changed, see the GPIO function select table in the datasheet for information on GPIO assignments
#define I2C_PORT i2c0
#define I2C_SDA 8
#define I2C_SCL 9

#define MCP23008_Address 0x20
#define IODIR 0x00
#define OLAT 0x0A
#define GPIO 0x09

void setPin(unsigned char ADDR, unsigned char reg, unsigned char value) {
    // Implementation to set the information of a pin via I2C:
    uint8_t buf[2];
    buf[0] = reg;
    buf[1] = value;

    // Send the blocking message to write to the address and set the value:
    i2c_write_blocking(i2c_default, ADDR, buf, 2, false);
}

unsigned char readPin(unsigned char ADDR, unsigned char reg) {
    // Create buffer to hold the read information:
    uint8_t buf[1];
    // Implemenation to read the information of a pin via I2C:
    i2c_write_blocking(i2c_default, ADDR, &reg, 1, true);  // true to keep host control of bus
    i2c_read_blocking(i2c_default, ADDR, &buf[0], 1, false);  // false - finished with bus

    // Return the value of the buffer for the requested register:
    return buf[0];
}

int main()
{
    stdio_init_all();

    // Initialize the Wi-Fi module
    if (cyw43_arch_init()) {
        return -1;
    }
    cyw43_arch_enable_sta_mode();

    // I2C Initialisation. Using it at 400Khz.
    i2c_init(I2C_PORT, 400*1000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);

    // Initialize the Chip to have GP7 as output and GP0 as input:
    setPin(MCP23008_Address, IODIR, 0b00000001);

    // Message to hold the current button state:
    unsigned char output;

    while (true) {
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
        sleep_ms(200);

        // I2C Communication Pipeline: 
        // If GP0 is read as high, then turn GP7 high:
        output = readPin(MCP23008_Address, GPIO);

        // Use bit masking to isolate whether GP0 is High:
        unsigned char mask = 0b00000001; 
        int result = (int)(output & mask);
        printf("%d\n", result);
        
        // If the result is returned as 0, then GP0 has been pulled high, and the light is turned off.
        if(result == 0) {
            // Turn GP7 High:
            setPin(MCP23008_Address, OLAT, 0b10000000);
        }
        else {
            // Turn GP7 Low: 
            setPin(MCP23008_Address, OLAT, 0b00000000);
        }

        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);
        sleep_ms(200);
    }
}
