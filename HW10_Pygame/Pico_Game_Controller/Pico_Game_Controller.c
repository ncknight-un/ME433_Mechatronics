#include <stdio.h>
#include "pico/stdlib.h"

#define PinA 19
#define PinW 18
#define PinS 17
#define PinD 16


void init_buttons() {
    gpio_init(PinA);
    gpio_set_dir(PinA, GPIO_IN);
    gpio_init(PinS);
    gpio_set_dir(PinS, GPIO_IN);
    gpio_init(PinD);
    gpio_set_dir(PinD, GPIO_IN);
    gpio_init(PinW);
    gpio_set_dir(PinW, GPIO_IN);
}

int main()
{
    stdio_init_all();

    // Initialize all the Control Pins: 
    init_buttons();

    while (true) {
        // Print the keyboard character to serial usb, so pygame can update frog's position.
        if (!gpio_get(PinA))
            printf("%c", 'a');
        if (!gpio_get(PinD))
            printf("%c", 'd');
        if (!gpio_get(PinS))
            printf("%c", 's');
        if (!gpio_get(PinW))
            printf("%c", 'w');
        
        // Delay to slow down reading:
        sleep_ms(250);
    }
}
