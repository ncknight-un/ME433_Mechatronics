#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/uart.h"

// UART defines
// By default the stdout UART is `uart0`, so we will use the second one
#define UART_ID uart1
#define BAUD_RATE 115200

// Use pins 4 and 5 for UART1
// Pins can be changed, see the GPIO function select table in the datasheet for information on GPIO assignments
#define UART_TX_PIN 4
#define UART_RX_PIN 5

int main()
{
    stdio_init_all();

    // Set up our UART
    uart_init(UART_ID, BAUD_RATE);

    // Set the TX and RX pins by using the function select on the GPIO
    // Set datasheet for more information on function select
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
    
    // Initialize Medssage to hold from computer and ST32:
    int pc_char;
    uint8_t st32_char;

    while (true) {
        // Read from computer over USB Serial:
        pc_char = getchar_timeout_us(1);
        if (pc_char != PICO_ERROR_TIMEOUT)
        {
            // Send to ST32 over UART:
            uart_putc(UART_ID, pc_char);
        }

        // Read from ST32 over UART:
        if (uart_is_readable(UART_ID))
        {
            st32_char = uart_getc(UART_ID);
            // Send to computer over USB Serial:
            printf("%c", st32_char);
        }
    }
}