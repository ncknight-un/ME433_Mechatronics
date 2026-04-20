#ifndef MPU6050_H__
#define MPU6050_H__

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

// Message structure for IMU Data:
typedef struct {
    float accel_x, accel_y, accel_z;
    float temp;
    float gyro_x, gyro_y, gyro_z;
} IMUData;

// ---- Function Declarations ----

/**
 * @brief Write a single byte to a register on an I2C device.
 * @param ADDR  I2C device address
 * @param reg   Target register
 * @param value Byte value to write
 */
void setPin(unsigned char ADDR, unsigned char reg, unsigned char value);
 
/**
 * @brief Read one or more bytes from a register on an I2C device.
 * @param ADDR    I2C device address
 * @param reg     Starting register to read from
 * @param buf     Buffer to store the read bytes
 * @param buf_len Number of bytes to read
 * @return        First byte read from the register
 */
unsigned char readPin(unsigned char ADDR, unsigned char reg, uint8_t *buf, int buf_len);
 
/**
 * @brief Initialize the MPU6050 (power on, configure accel ±2g and gyro ±2000°/s).
 */
void init_MPU6050(void);
 
/**
 * @brief Read 14 raw bytes from the MPU6050 (accel, temp, gyro).
 * @param data Pointer to a buffer of at least 14 bytes
 */
void readIMU(uint8_t *data);
 
/**
 * @brief Parse raw 14-byte IMU data into scaled float values.
 * @param rawdata Pointer to a 14-byte raw data buffer
 * @return        IMUData struct with scaled accel (g), temp (°C), and gyro (deg/s)
 */
IMUData cleanIMUdata(uint8_t *rawdata);

#endif // MPU6050_H