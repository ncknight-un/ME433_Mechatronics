import board
import pwmio
import time
import digitalio

MIN_DUTY = 480       # 480 us for 0 degrees
MAX_DUTY = 2400      # 2400 us for 180 degrees
MAX_WRAP = 65535       # Max wrap value for 16-bit PWM
PWM_PERIOD = 20000     # 20 ms period for 50 Hz PWM (20,000 us)

# See: https://learn.adafruit.com/circuitpython-essentials/circuitpython-pwm 
# Initialize PWM on the Board for the servo motor:
servo_pwm = pwmio.PWMOut(board.GP16, frequency=50, duty_cycle=0)   # 50Hz for Servo Motor Control

# Turn on the Onboard Led for debugging to make sure signal is recieved (Currently it is):
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True

while True:
    servo_pwm.duty_cycle = int((MIN_DUTY / PWM_PERIOD) * MAX_WRAP)        # 2.4% duty cycle for 0 degrees
    time.sleep(1)                                       # Wait for 1 second
    servo_pwm.duty_cycle = int((MAX_DUTY / PWM_PERIOD) * MAX_WRAP)        # 12% duty cycle for 180 degrees
    time.sleep(1)                                       # Wait for 1 second
