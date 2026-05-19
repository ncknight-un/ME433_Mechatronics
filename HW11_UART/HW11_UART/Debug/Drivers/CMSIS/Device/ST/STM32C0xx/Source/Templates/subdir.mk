################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (14.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.c 

OBJS += \
./Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.o 

C_DEPS += \
./Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.d 


# Each subdirectory must supply rules for building sources it contributes
Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/%.o Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/%.su Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/%.cyclo: ../Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/%.c Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m0plus -std=gnu11 -g3 -DDEBUG -DUSE_NUCLEO_64 -DUSE_HAL_DRIVER -DSTM32C092xx -c -I../Core/Inc -I../Drivers/STM32C0xx_HAL_Driver/Inc -I../Drivers/STM32C0xx_HAL_Driver/Inc/Legacy -I../Drivers/BSP/STM32C0xx_Nucleo -I../Drivers/CMSIS/Device/ST/STM32C0xx/Include -I../Drivers/CMSIS/Include -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfloat-abi=soft -mthumb -o "$@"

clean: clean-Drivers-2f-CMSIS-2f-Device-2f-ST-2f-STM32C0xx-2f-Source-2f-Templates

clean-Drivers-2f-CMSIS-2f-Device-2f-ST-2f-STM32C0xx-2f-Source-2f-Templates:
	-$(RM) ./Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.cyclo ./Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.d ./Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.o ./Drivers/CMSIS/Device/ST/STM32C0xx/Source/Templates/system_stm32c0xx.su

.PHONY: clean-Drivers-2f-CMSIS-2f-Device-2f-ST-2f-STM32C0xx-2f-Source-2f-Templates

