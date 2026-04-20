#include <string.h> // for memset
#include "hardware/i2c.h"
#include "pico/stdlib.h"
#include "MPU6050_Library/mpu6050.h"
#include <stdint.h>
#include <math.h>

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