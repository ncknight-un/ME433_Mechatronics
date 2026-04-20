#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "pico/cyw43_arch.h"
#include "ssd1306_Library/ssd1306.h"
#include "math.h"

// config registers
#define CONFIG 0x1A
#define GYRO_CONFIG 0x1B
#define ACCEL_CONFIG 0x1C
#define PWR_MGMT_1 0x6B
#define PWR_MGMT_2 0x6C
// sensor data registers:
#define ACCEL_XOUT_H 0x3B
#define ACCEL_XOUT_L 0x3C
#define ACCEL_YOUT_H 0x3D
#define ACCEL_YOUT_L 0x3E
#define ACCEL_ZOUT_H 0x3F
#define ACCEL_ZOUT_L 0x40
#define TEMP_OUT_H   0x41
#define TEMP_OUT_L   0x42
#define GYRO_XOUT_H  0x43
#define GYRO_XOUT_L  0x44
#define GYRO_YOUT_H  0x45
#define GYRO_YOUT_L  0x46
#define GYRO_ZOUT_H  0x47
#define GYRO_ZOUT_L  0x48
#define WHO_AM_I     0x75
#define MPU6050_ADDR 0x68

// I2C defines
// This example will use I2C0 on GPIO8 (SDA) and GPIO9 (SCL) running at 400KHz.
// Pins can be changed, see the GPIO function select table in the datasheet for information on GPIO assignments
#define I2C_PORT i2c0
#define I2C_SDA 8
#define I2C_SCL 9


typedef struct {
    float accel_x, accel_y, accel_z;
    float temp;
    float gyro_x, gyro_y, gyro_z;
} IMUData;

void setPin(unsigned char ADDR, unsigned char reg, unsigned char value) {
    // Implementation to set the information of a pin via I2C:
    uint8_t buf[2];
    buf[0] = reg;
    buf[1] = value;

    // Send the blocking message to write to the address and set the value:
    i2c_write_blocking(I2C_PORT, ADDR, buf, 2, false);
}

unsigned char readPin(unsigned char ADDR, unsigned char reg, uint8_t *buf, int buf_len) {
    // Implemenation to read the information of a pin via I2C for the length of the buffer:
    i2c_write_blocking(I2C_PORT, ADDR, &reg, 1, true);         // true to keep host control of bus
    i2c_read_blocking(I2C_PORT, ADDR, &buf[0], buf_len, false);      // false - finished with bus

    // Return the value of the data buffer for the requested register:
    return buf[0];
}

void init_MPU6050() {
    // Turn on the Chip:
    setPin(MPU6050_ADDR, PWR_MGMT_1, 0x00);
    // Set the Accelerometer to 2g:
    setPin(MPU6050_ADDR, ACCEL_CONFIG, 0x00);
    // Enable the Gyroscope:
    setPin(MPU6050_ADDR, GYRO_CONFIG, 0x18);
}

void readIMU(uint8_t *data) {
    // Read 14 bytes starting at ACCEL_XOUT_H (0x3B) and save to data pointer:
    readPin(MPU6050_ADDR, 0x3B, data, 14);
}

IMUData cleanIMUdata(uint8_t *rawdata) {
    // Perform bitwise operations on each 2 pairs of bytes to determine clean IMU readings.
    IMUData data;
    
    // Acceleration Decoding:
    data.accel_x = (int16_t)((rawdata[0]  << 8) | rawdata[1]);
    data.accel_y = (int16_t)((rawdata[2]  << 8) | rawdata[3]);
    data.accel_z = (int16_t)((rawdata[4]  << 8) | rawdata[5]);
    // Scale to g:
    data.accel_x *= 0.000061f;
    data.accel_y *= 0.000061f;
    data.accel_z *= 0.000061f;

    // Temp Decoding: 
    data.temp = (int16_t)((rawdata[6]  << 8) | rawdata[7]);
    // Convert to Deg Celsius:
    data.temp = (data.temp / 340.00f) + 36.53f;

    // Gyro Decoding: 
    data.gyro_x  = (int16_t)((rawdata[8]  << 8) | rawdata[9]);
    data.gyro_y  = (int16_t)((rawdata[10] << 8) | rawdata[11]);
    data.gyro_z  = (int16_t)((rawdata[12] << 8) | rawdata[13]);
    // Scale to deg/sec:
    data.gyro_x *= 0.007630f;
    data.gyro_y *= 0.007630f;
    data.gyro_z *= 0.007630f;

    return data;
}

void drawAccel(float x_accel, float y_accel) {
    // Draw the Acceleration Vectors at the center of the OLED screen:
    // Case 1: Both x and y accel are near zero: (0.1 used for system noise)
    if (fabs(x_accel) < 0.10 && fabs(y_accel) < 0.10) {
        // Plot a dot at the center of the screen:
        ssd1306_drawMessage(64,16, ".");
    }
    // Case 2: x_accel or y_accel is not zero:
    else {
        // Plot the x vector factored by magnitude:
        if (fabs(x_accel) > 0.1) {
            // Create pixel multiplier for axis:
            int mult = fabs(x_accel) / 0.1;
            mult *= 10;

            for (int i = 0; i < mult; i++){
                if (x_accel < 0)    // x axes flipped on my IMU.
                    ssd1306_drawPixel(64 + i,16, 1);    // Turn on the pixel by magnitude:
                else 
                    ssd1306_drawPixel(64 - i,16, 1);    // Turn on the pixel by magnitude:
            }
            if (x_accel < 0)
                ssd1306_drawLetter(64 + (mult-2),13, '>');
            else
                ssd1306_drawLetter(64  - (mult-2),13, '<');    
        }
        // Plot the y vector factored by magnitude:
        if (fabs(y_accel) > 0.1) {
            // Create pixel multiplier for axis:
            int mult = fabs(y_accel) / 0.1;
            mult *= 3;      // multiplier to make line more visable.

            for (int i = 0; i < mult; i++){
                if (y_accel > 0)
                    ssd1306_drawPixel(64,16 - i, 1);    // Turn on the pixel by magnitude:
                else 
                    ssd1306_drawPixel(64,16 + i, 1);    // Turn on the pixel by magnitude:
            }
            if (y_accel < 0)
                ssd1306_drawLetter(64,16 + (mult-2), 'v');
            else
                ssd1306_drawLetter(64, 16 - (mult-2), '^');    
        }
    }
}


int main()
{
    stdio_init_all();

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

    // Initialize the IMU:
    init_MPU6050();
    // Initialize the OLED Screen:
    ssd1306_setup();

    // Determine when the Pico2 W was turned on:
    uint64_t start_t = to_us_since_boot(get_absolute_time()); 
    uint64_t end_t = to_us_since_boot(get_absolute_time()); 
    double time_change = 0;
    // Create counter to toggle LED:
    double LED_t = 0; 
    double IMU_t = 0;
    uint8_t toggle = 0;

    while (true) {
        // Get the start time: 
        start_t = to_us_since_boot(get_absolute_time()); 

        // Read in the IMU data and store it as a pointer array:
        uint8_t imu_data[14];
        // Read the IMU at a rate of 100Hz.
        IMU_t += time_change;
        if (IMU_t > 0.1) {
            readIMU(imu_data);
        }

        // Clean the IMU data for use (Accel(X,Y,Z), Temp(T), Gyro(X,Y,Z)):
        IMUData clean_data = cleanIMUdata(imu_data);
        
        // Print the current raw data:
        printf("IMU: ");
        printf("\n");
        printf("Acceleration: (%f, %f, %f)", clean_data.accel_x, clean_data.accel_y, clean_data.accel_z);
        printf("\n");
        printf("Temperature: (%f)", clean_data.temp);
        printf("\n");
        printf("Gyration (%f, %f, %f)", clean_data.gyro_x, clean_data.gyro_y, clean_data.gyro_z);
        printf("\n");
        fflush(stdout);     // Cleans print out at high speeds

        // I2C Communication Pipeline for OLED Screen:
        drawAccel(clean_data.accel_x, clean_data.accel_y);
        ssd1306_update();

        // Clear previous Message: 
        ssd1306_clear();

        // Determine the FPS and print to the screen:
        end_t = to_us_since_boot(get_absolute_time()); 
        time_change = (end_t - start_t) / 1000000.0 ;      // Convert to seconds
        // Toggle the LED based on Current Time_stamp:
        LED_t += (time_change);
        if (LED_t > 1) {
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
    }
}
