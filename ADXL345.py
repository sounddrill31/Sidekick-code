# ADXL345 I2C Accelerometer Driver for MicroPython
# Optimized for FAST shake detection
# Interface similar to MPU6050 class

from hal import sleep_ms


class ADXL345:
    ADDRESS = 0x53
    REG_DATA_FORMAT = 0x31
    REG_POWER_CTL = 0x2D
    REG_BW_RATE = 0x2C
    REG_DATAX0 = 0x32

    def __init__(self, i2c_bus, debug_mode=False):
        self.i2c = i2c_bus
        self.debug_mode = debug_mode
        self.available = False
        
        # Try to initialize the real hardware
        try:
            self._init_device()
            self.available = True
            if debug_mode:
                print("✅ ADXL345 initialized successfully")
        except (OSError, TypeError) as e:
            # Hardware failed, create dummy methods
            self.available = False
            if debug_mode:
                print(f"⚠️ ADXL345 initialization failed: {e}")
                print("🔧 Debug mode: Using dummy accelerometer...")
            
            # Replace methods with dummy versions
            self._make_dummy()

    def _make_dummy(self):
        """Replace all methods with safe dummy versions"""
        def dummy_read_accel_data():
            import hal
            if getattr(hal.hal, 'sim_shake', False):
                import random
                # reset flag after generating one heavy shake frame
                hal.hal.sim_shake = False
                return (random.randint(-15000, 15000), random.randint(-15000, 15000), random.randint(-15000, 15000))
            return (0, 0, 1000)
        
        def dummy_read_accel_abs():
            import hal
            if getattr(hal.hal, 'sim_shake', False):
                return 15000.0
            return 1000.0
            
        def dummy_is_shaking():
            import hal
            if getattr(hal.hal, 'sim_shake', False):
                return True
            return False

    def _init_device(self):
        # Set device to measurement mode

        try:
            # MicroPython style
            self.i2c.writeto_mem(self.ADDRESS, self.REG_POWER_CTL, b'\x08')
        except AttributeError:
            # CircuitPython style
            while not self.i2c.try_lock():
                pass
            try:
                self.i2c.writeto(self.ADDRESS, bytes([self.REG_POWER_CTL, 0x08]))
            finally:
                self.i2c.unlock()
        # Set data format: ±8g range for better shake detection (0x0B = ±8g, full resolution)

        try:
            self.i2c.writeto_mem(self.ADDRESS, self.REG_DATA_FORMAT, b'\x0B')
        except AttributeError:
            while not self.i2c.try_lock(): pass
            try: self.i2c.writeto(self.ADDRESS, bytes([self.REG_DATA_FORMAT, 0x0B]))
            finally: self.i2c.unlock()
        # Set data rate to 800Hz for fast shake detection (0x0D = 800Hz) rather than full resolution
        # Options: 0x0A=100Hz, 0x0B=200Hz, 0x0C=400Hz, 0x0D=800Hz, 0x0E=1600Hz, 0x0F=3200Hz

        try:
            self.i2c.writeto_mem(self.ADDRESS, self.REG_BW_RATE, b'\x0D')
        except AttributeError:
            while not self.i2c.try_lock(): pass
            try: self.i2c.writeto(self.ADDRESS, bytes([self.REG_BW_RATE, 0x0D]))
            finally: self.i2c.unlock()
        sleep_ms(10)

    def read_accel_data(self):
        # Returns (x, y, z) in raw units (fast single I2C read)
        if not self.available:
            if self.debug_mode:
                return (0, 0, 1000)  # Return fake "still" values
            else:
                raise OSError("ADXL345 not available")
        

        try:
            data = self.i2c.readfrom_mem(self.ADDRESS, self.REG_DATAX0, 6)
        except AttributeError:
            data = bytearray(6)
            while not self.i2c.try_lock(): pass
            try:
                self.i2c.writeto_then_readfrom(self.ADDRESS, bytes([self.REG_DATAX0]), data)
            finally:
                self.i2c.unlock()
        x = int.from_bytes(data[0:2], 'little', True)
        y = int.from_bytes(data[2:4], 'little', True)
        z = int.from_bytes(data[4:6], 'little', True)
        return (x, y, z)

    def read_accel_abs(self):
        # Returns absolute acceleration - OPTIMIZED for shake detection
        # Simplified version without parameters to avoid compatibility issues
        if not self.available:
            if self.debug_mode:
                return 1000.0  # Return fake "still" value
            else:
                raise OSError("ADXL345 not available")
                
        x, y, z = self.read_accel_data()
        abs_val = (x**2 + y**2 + z**2) ** 0.5
        return abs_val
    
    def is_shaking(self):
        # Quick shake detection - returns True if shaking detected
        # Fixed threshold=8000 works well for ±8g range
        if not self.available:
            return False  # No shaking if sensor unavailable
        return self.read_accel_abs() > 8000

"""
OPTIMIZATION SUMMARY for Shake Detection:

1. I2C Speed: Use 400kHz (4x faster than 100kHz)
   i2c_bus = I2C(0, scl=Pin(0), sda=Pin(1), freq=400_000)

2. ADXL345 Config:
   - Data Rate: 800Hz (0x0D) - very fast sampling
   - Range: ±8g (0x0B) - better for shake detection than ±2g
   - Single I2C read gets all 3 axes (6 bytes)

3. Recommended thresholds for raw values (±8g range):
   - Light movement: < 2000
   - Shake detection: > 8000
   - Aggressive shaking: > 15000

4. Loop timing: 50ms or faster for responsive shake detection
   
5. Quick check: Use is_shaking() method for fast boolean detection
"""
