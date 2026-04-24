#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/spi.h"
#include <math.h>

/* 
   GPIO 16 (pin 21) MISO/spi0_rx-> Unused for MCP4912 (One way communication)
   GPIO 17 (pin 22) Chip select -> Pin 3 (CS)
   GPIO 18 (pin 24) SCK/spi0_sclk -> Pin 4 (SCK)
   GPIO 19 (pin 25) MOSI/spi0_tx -> Pin 5 (SDI)
   3.3v (pin 36) -> VDD
   GND (pin 38)  -> VSS

   Note: SPI devices can have a number of different naming schemes for pins. See
   the Wikipedia page at https://en.wikipedia.org/wiki/Serial_Peripheral_Interface
   for variations.
*/

#define SPI_PORT spi0
#define PIN_CS 17
#define VREF 3.3f

static inline void cs_select(uint cs_pin) {
    asm volatile("nop \n nop \n nop");
    gpio_put(cs_pin, 0);
    asm volatile("nop \n nop \n nop");
}

static inline void cs_deselect(uint cs_pin) {
    asm volatile("nop \n nop \n nop");
    gpio_put(cs_pin, 1);
    asm volatile("nop \n nop \n nop");
}

void writeDAC(int channel, float v) {
    // creat the data instance: 
    uint8_t data[2];
    data[0] = 0b01010000;   // Sets Buffer to 1, Gain to 0 (2x), and SHDN to 1
    // Set the channel bit:
    data[0] = data[0] | ((channel&0b1)<<7);

    // Set the voltage:
    uint16_t currV = (v / VREF) * 1023;        // 0b11111111
    data[0] = data[0] | ((currV>>8)&0b00000011);
    data[1] = currV & 0xFF;             // 0b11111100

    // Send to the DAC:
    cs_select(PIN_CS);
    spi_write_blocking(SPI_PORT, data, 2);
    cs_deselect(PIN_CS);
}


int main() {
    stdio_init_all();
#if !defined(spi_default) || !defined(PICO_DEFAULT_SPI_SCK_PIN) || !defined(PICO_DEFAULT_SPI_TX_PIN) || !defined(PICO_DEFAULT_SPI_RX_PIN) || !defined(PICO_DEFAULT_SPI_CSN_PIN)
#warning MCP4912_spi example requires a board with SPI pins
    puts("Default SPI pins were not defined");
#else
    // This example will use SPI0 at 1MHz.
    spi_init(spi_default, 1000 * 1000);
    gpio_set_function(PICO_DEFAULT_SPI_RX_PIN, GPIO_FUNC_SPI);
    gpio_set_function(PICO_DEFAULT_SPI_SCK_PIN, GPIO_FUNC_SPI);
    gpio_set_function(PICO_DEFAULT_SPI_TX_PIN, GPIO_FUNC_SPI);

    // Initialize the CS PIN:
    gpio_init(PIN_CS);
    gpio_set_dir(PIN_CS, GPIO_OUT);
    gpio_put(PIN_CS, 1);  // deselect by default

    // Create the Sine wave:
    float v_sin[100];
    for (int i=0; i<100; i++) {
        v_sin[i] = (sinf(2*M_PI*i / 100) + 1) / 2 * VREF;
    }

    // Create the Triangle Vave:
    float v_tri[100];
    for (int i=0; i<100; i++) {
        v_tri[i] = (2.0f * i / 100) * VREF;
        if (i > 50) {
            v_tri[i] = (2.0f * (100 - i) / 100) * VREF;
        }
    }

    int t = 0;
    while (1) {
        // Call WriteDAC to write the voltage in a sin-wave and triangle wave pattern:
        writeDAC(0, v_sin[t]);      //DACA
        writeDAC(1, v_tri[t]);      //DACB
        sleep_ms(5);
        t += 1;

        // Reset time counter: 
        if (t >= 100) {
            t = 0;
        }
    }
#endif
}
