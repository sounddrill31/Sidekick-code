from hal import get_pin_value

button_1 = get_pin_value('button_1')
button_2 = get_pin_value('button_2')
buzzer_pin_value = get_pin_value('buzzer')
led_pin_value = get_pin_value('led')
code_debug_pin_value = button_1
code_ok_pin_value = button_2

i2c_scl_pin = get_pin_value('i2c_scl')
i2c_sda_pin = get_pin_value('i2c_sda')
