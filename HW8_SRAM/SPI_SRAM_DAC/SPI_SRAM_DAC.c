#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/binary_info.h"
#include "hardware/spi.h"
#include <math.h>

// SPI Defines
/* 
   GPIO 16 (pin 21) MISO/spi0_rx-> Unused for MCP4912 (One way communication)
   GPIO 17 (pin 22) Chip select -> Pin 3 (CS)
   GPIO 18 (pin 24) SCK/spi0_sclk -> Pin 4 (SCK)
   GPIO 19 (pin 25) MOSI/spi0_tx -> Pin 5 (SDI)
   3.3v (pin 36) -> VDD
   GND (pin 38)  -> VSS
*/
#define SPI_PORT spi0
#define PIN_MISO 16
#define PIN_CS_DAC   17
#define PIN_CS_SRAM 15
#define PIN_SCK  18
#define PIN_MOSI 19
#define VREF 3.3f
#define dimension 1000

// Function to CS Select:
static inline void cs_select(uint cs_pin) {
    asm volatile("nop \n nop \n nop");
    gpio_put(cs_pin, 0);
    asm volatile("nop \n nop \n nop");
}

// Function for DC Deselect:
static inline void cs_deselect(uint cs_pin) {
    asm volatile("nop \n nop \n nop");
    gpio_put(cs_pin, 1);
    asm volatile("nop \n nop \n nop");
}

// Initialize the RAM to Sequential mode:
void spi_ram_init() {
    // Set the SRAM Chip to Sequential Mode:
    uint8_t data[2];
    data[0] = 0b00000001;
    data[1] = 0b01000000;   // Sequential mode
    // Send the sequential mode message:
    cs_select(PIN_CS_SRAM);
    spi_write_blocking(SPI_PORT, data, 2);
    cs_deselect(PIN_CS_SRAM);
}

// Function to Read from the RAM chip:
void readSPI_SRAM(uint16_t address, uint8_t * data, int length) {
    // Read from the SRAM Chip:
    uint8_t packet[5];
    packet[0] = 0b00000011; // Read instruction
    packet[1] = (address >> 8) & 0xFF;  // High byte
    packet[2] = address & 0xFF;          // Low byte
    packet[3] = 0;
    packet[4] = 0;

    uint8_t received[5];
    // Send the packet over SPI to the SRAM:
    cs_select(PIN_CS_SRAM);
    spi_write_read_blocking(SPI_PORT, packet, received, 5);
    cs_deselect(PIN_CS_SRAM);

    // Extract the datar from the received message:
    data[0] = received[3];
    data[1] = received[4];
}

// Function to write to the RAM chip:
void writeSPI_SRAM(uint16_t address, uint8_t * data, int length) {
    // Write to the SRAM Chip:
    uint8_t packet[5];
    packet[0] = 0b00000010; // Write instruction
    packet[1] = (address >> 8) & 0xFF;  // High byte
    packet[2] = address & 0xFF;          // Low byte
    packet[3] = data[0]; 
    packet[4] = data[1];

    // Send the packet over SPI to the SRAM:
    cs_select(PIN_CS_SRAM);
    spi_write_blocking(SPI_PORT, packet, 5);
    cs_deselect(PIN_CS_SRAM);
}

// Function to write a Sine Wave to the SRAM Chip:
void SRAM_Write_Sin(int dim) {
    uint8_t data[2]; 
    uint16_t data_short = 0; 
    uint8_t channel = 0b0; 
    float voltage = 0;
    uint16_t addr = 0;

    // Create the Sine wave:
    for (int i = 0; i<dim; i++) {
        data_short = (channel&0b1)<<15; // Signal will go to DAC channel A
        data_short = data_short | (0b111<<12);  // Set the Gains to defualt

        voltage = (sin(2.0*M_PI*i / dim) + 1.0) * 511.5f;
        uint16_t v = voltage;

        data_short = data_short | (0x03FF & v);
        data[0] = data_short >> 8;
        data[1] = data_short & 0xFF; 
        
        // Write the value to the address in RAM:
        writeSPI_SRAM(addr, data, 2); 
        addr += 2;  // Move to the next 2 addresses to write to.
    }
}

// Function to Write to the DAC from Raspberry PI:
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
    cs_select(PIN_CS_DAC);
    spi_write_blocking(SPI_PORT, data, 2);
    cs_deselect(PIN_CS_DAC);
}

// Function to Write to the DAC from RAM:
void writeDACFromSRAM(int index) {
    // creat the data instance: 
    uint8_t data[2];

    // Read in the data from the RAM chip:
    readSPI_SRAM(index, data, 2);

    // Send to the DAC:
    cs_select(PIN_CS_DAC);
    spi_write_blocking(SPI_PORT, data, 2);
    cs_deselect(PIN_CS_DAC);
}

int main()
{
    stdio_init_all();

    // Chip select is active-low, so we'll initialise it to a driven-high state
    // DAC CS Init:
    gpio_init(PIN_CS_DAC);
    gpio_set_dir(PIN_CS_DAC, GPIO_OUT);
    gpio_put(PIN_CS_DAC, 1);
    // SRAM CS Init:
    gpio_init(PIN_CS_SRAM);
    gpio_set_dir(PIN_CS_SRAM, GPIO_OUT);
    gpio_put(PIN_CS_SRAM, 1);

    // SPI initialisation. This example will use SPI at 1MHz.
    spi_init(SPI_PORT, 1000*1000);
    gpio_set_function(PIN_MISO, GPIO_FUNC_SPI);
    gpio_set_function(PIN_CS_DAC,   GPIO_FUNC_SIO);
    gpio_set_function(PIN_CS_SRAM,   GPIO_FUNC_SIO);
    gpio_set_function(PIN_SCK,  GPIO_FUNC_SPI);
    gpio_set_function(PIN_MOSI, GPIO_FUNC_SPI);

    // Initialize the SRAM chip in Sequenctial Mode:
    spi_ram_init();

    // Create the Sine wave with dimension 1000 and send to the RAM chip:
    SRAM_Write_Sin(dimension);

    int index = 0;
    while (true) {
        // Read from the SRAM and send to the DAC:
        writeDACFromSRAM(index);
        index += 2;

        // If index is greater than dimension restart the reading:
        if (index >= dimension * 2) {
            index = 0;
        }
        sleep_ms(1);
    }
}
