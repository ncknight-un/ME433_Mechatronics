#include <stdio.h>
#include "pico/stdlib.h"
#include <stdlib.h>

// Define GPIO Pins for Clock and Data for Amplifier: 
#define amp_clk 2
#define amp_data 3

// IIR filter coefficient: 
// output = alpha*new + (1-alpha)*prev
#define IIR_ALPHA 0.10f
 
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

int main() {
    stdio_init_all();

    // Wait for USB serial to connect:
    while (!stdio_usb_connected()) {
        tight_loop_contents();
    }
    sleep_ms(500);
    
    // Init HX711 pins:
    initHX711();
 
    // Target is 40 Hz, so one sample every 25 ms
    const uint32_t SAMPLE_PERIOD_MS = 25;
 
    // Set maximum samples allowed for data acquisition:
    #define MAX_SAMPLES 2000
 
    static int32_t  raw_data[MAX_SAMPLES];
    static float    filt_data[MAX_SAMPLES];
    static uint32_t time_ms[MAX_SAMPLES];
 
    while (true) {
        printf("READY\n");
        fflush(stdout);
        sleep_ms(500);

        // Check if anything came in
        int c = getchar_timeout_us(0);
        if (c == PICO_ERROR_TIMEOUT) {
            continue;
        }

        // Got first character, read the rest of the number
        char buf[16];
        int idx = 0;
        if (c != '\n' && c != '\r') {
            buf[idx++] = (char)c;
        }
        while (idx < (int)(sizeof(buf) - 1)) {
            int c2 = getchar_timeout_us(100000);
            if (c2 == PICO_ERROR_TIMEOUT || c2 == '\n' || c2 == '\r') break;
            buf[idx++] = (char)c2;
        }
        buf[idx] = '\0';

        int n_samples = atoi(buf);
        if (n_samples <= 0 || n_samples > MAX_SAMPLES) {
            printf("ERROR: invalid sample count %d (max %d)\n", n_samples, MAX_SAMPLES);
            continue;
        }

        // Collect samples from requested value:
        float filtered = (float)readHX711();
        for (int i = 0; i < n_samples; i++) {
            uint32_t t_start = to_ms_since_boot(get_absolute_time());
            int32_t sample = readHX711();
            filtered = IIR_ALPHA * (float)sample + (1.0f - IIR_ALPHA) * filtered;
            raw_data[i]  = sample;
            filt_data[i] = filtered;
            time_ms[i]   = t_start;
            uint32_t elapsed = to_ms_since_boot(get_absolute_time()) - t_start;
            if (elapsed < SAMPLE_PERIOD_MS) {
                sleep_ms(SAMPLE_PERIOD_MS - elapsed);
            }
        }

        // After Collection, print all data back:
        printf("BEGIN %d\n", n_samples);
        for (int i = 0; i < n_samples; i++) {
            printf("DATA %lu %ld %.2f\n",
                (unsigned long)time_ms[i],
                (long)raw_data[i],
                (double)filt_data[i]);
        }
        printf("END\n");
        fflush(stdout);
    }
}
